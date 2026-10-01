`timescale 1ns/1ps
module tb;
    parameter real PERIOD = 10.0;          // период такта, нс (100 МГц)

    reg clk = 0;
    reg rst = 1;
    always #(PERIOD/2) clk = ~clk;

    reg  [47:0]        ftw;
    reg  signed [31:0] fm_in;
    reg  [15:0]        pm_in;
    reg  [15:0]        am_in;

    wire signed [15:0] dac, held, filt;

    dds_mod  #(48,14,16) u0 (.clk(clk), .rst(rst), .ftw(ftw),
                             .fm_in(fm_in), .pm_in(pm_in), .am_in(am_in),
                             .dac_out(dac));
    deglitch #(16) u1 (.clk(clk), .strobe(1'b1), .din(dac), .dout(held));
    lpf      #(16,4) u2 (.clk(clk), .rst(rst), .din(held), .dout(filt));

    initial begin
        $dumpfile("wave.vcd");
        $dumpvars(0, tb);

        ftw   = 48'd2814749767107;         // ~1 МГц при 100 МГц
        fm_in = 0;
        pm_in = 0;
        am_in = 16'd65535;

        #100 rst = 0;

        // 1. AM: амплитуда падает вдвое
        #20000 am_in = 16'd32768;

        // 2. FM: сдвиг частоты
        #20000 fm_in = 32'sd1100000000;

        // 3. PM: сдвиг фазы на четверть круга
        #20000 pm_in = 16'd16384;
        $display("FM_SHIFT effect: ftw_eff = %h", u0.ftw_eff);
        #20000 $display("t=%0t ftw_eff = %h", $time, u0.ftw_eff);
        #20000 $finish;
    end
endmodule
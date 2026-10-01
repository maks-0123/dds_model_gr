`timescale 1ns/1ps
module tb;
    reg         clk = 0;
    reg         rst = 1;
    reg  [15:0] ftw = 16'd1000;
    wire [15:0] phase;

    phase_acc #(16) dut (.clk(clk), .rst(rst), .ftw(ftw), .phase(phase));

    always #5 clk = ~clk;                 // период 10 нс, 100 МГц

    initial begin
        $dumpfile("wave.vcd");
        $dumpvars(0, tb);
        #22 rst = 0;
        #20000 ftw = 16'd4000;            // меняем частоту на лету
        #20000 $finish;
    end
endmodule

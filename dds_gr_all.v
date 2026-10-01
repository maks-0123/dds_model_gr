module dds_gr #(parameter TEST_MODE = 1)(
    input         clock,
    input         reset,
    input  [31:0] io_in,    
    output [31:0] io_out
);
    wire signed [15:0] dac, held, filt;

    generate 
        if (TEST_MODE == 0) begin : normal_dds
            dds_mod #(.N(48), .AW(14), .DW(16), .FM_SHIFT(25)) u0 (
            .clk(clock), .rst(reset),
            .ftw(48'h080000000000),      
            .fm_in(io_in), .pm_in(16'd0), .am_in(16'hFFFF),
            .dac_out(dac));
        end else begin : dac_test
            assign dac = io_in[15:0]; 
        end
    endgenerate

    deglitch #(16) u1
        (.clk(clock), .strobe(1'b1), .din(dac), .dout(held));
    lpf #(16, 1)   u2 
        (.clk(clock), .rst(reset), .din(held), .dout(filt));

    assign io_out = {{16{filt[15]}}, filt};
endmodule
module dds_mod #(parameter N = 48, AW = 14, DW = 16, FM_SHIFT = 8) (
    input                      clk,
    input                      rst,
    input      [N-1:0]         ftw,
    input signed [31:0]        fm_in,     // частотная модуляция
    input      [15:0]          pm_in,     // фазовая модуляция, 2^16 = полный круг
    input      [15:0]          am_in,     // амплитуда 0..65535 ~ 0..1
    output reg signed [DW-1:0] dac_out
);

    // FM: расширяем знак до N бит, затем сдвигаем на FM_SHIFT
    wire signed [N-1:0] fm_in_x = {{(N-32){fm_in[31]}}, fm_in};
    wire signed [N-1:0] fm_ext  = fm_in_x <<< FM_SHIFT;
    wire        [N-1:0] ftw_eff = ftw + fm_ext;

    // фазовый аккумулятор
    reg [N-1:0] phase;
    always @(posedge clk)
        if (rst) phase <= 0;
        else     phase <= phase + ftw_eff;

    // PM: складываем с верхними 16 битами фазы, потом берём AW старших
    wire [15:0]   ph16 = phase[N-1:N-16] + pm_in;
    wire [AW-1:0] addr = ph16[15:16-AW];    

    wire signed [DW-1:0] s;
    sine_mem #(AW, DW) mem (.clk(clk), .addr(addr), .data(s));

    // AM: 16 x 17 (со знаком) бит
    wire signed [DW+16:0] prod = s * $signed({1'b0, am_in});
    reg  signed [DW-1:0]  am_out;
    always @(posedge clk) am_out <= prod[DW+15:16];
    always @(posedge clk)
        if (rst) dac_out <= 0;
        else     dac_out <= am_out;
endmodule
module sine_mem#(parameter AW = 14, DW = 16) ( 
    input clk,
    input [AW-1:0] addr,
    output reg signed [DW-1: 0] data
);
    reg [DW-1: 0] rom [0:(1<<AW)-1];
    initial $readmemh("/Users/maksimromanuta/Documents/work_on_etalon/icarus_DDS/sine.hex", rom);
    always @(posedge clk) data <= rom[addr];
endmodule
module deglitch #(parameter DW = 16) (
    input                     clk,
    input                     strobe,
    input  signed [DW-1:0]    din,
    output reg signed [DW-1:0] dout
);
    always @(posedge clk)
        if (strobe) dout <= din;
endmodule
module lpf #(parameter DW = 16, K = 4) (
    input                  clk,
    input                  rst,
    input  signed [DW-1:0] din,
    output signed [DW-1:0] dout
);
    reg signed [DW+K-1:0] acc;
    assign dout = acc[DW+K-1:K];

    wire signed [DW+K-1:0] din_x  = {{K{din[DW-1]}},  din};
    wire signed [DW+K-1:0] dout_x = {{K{dout[DW-1]}}, dout};

    always @(posedge clk)
        if (rst) acc <= 0;
        else     acc <= acc + (din_x - dout_x);
endmodule

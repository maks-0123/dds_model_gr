// 
// dds_gr_all.v  -  DDS model for SFDR measurements, DW (DAC width) is a parameter
//
// TEST_MODE: 0 = DDS only, 1 = DAC test from io_in[DW-1:0], 2 = DDS + dac_nonlin
// OUT_SEL  : 0 = raw output, 1 = after deglitch + LPF
// DW       : output word width, 4..16.  Full scale = 2^(DW-1)
// RW       : ROM/multiplier width (16 = high-precision source). The DDS output is
//            rounded ONCE to DW bits, so DW alone sets the quantization.
// AW       : sine ROM address bits (<=16). Keep AW >= DW+2 so phase truncation
//            does not hide the effect of DW.
// Frequency (priority order):
//   FTW_OVERRIDE != 0   -> FTW = FTW_OVERRIDE                (non-coherent)
//   M_FROM_IO = 1       -> M = io_in[31:16]                  (sweep without recompiling)
//   otherwise           -> M = M_CYCLES                      (coherent, M odd)
//   FTW = M << (48 - LOG2N)
// Amplitude: AM_IN = 29274 -> -7 dBFS (independent of DW)
// 
module dds_gr #(
    parameter TEST_MODE = 0,
    parameter OUT_SEL   = 0,
    parameter DW        = 16,
    parameter AW        = 14,
    parameter RW        = 20,   // sine ROM / multiplier width (>= DW); output is rounded to DW
    parameter M_CYCLES  = 2457,
    parameter M_FROM_IO = 0,
    parameter LOG2N     = 15,
    parameter AM_IN     = 29274,
    parameter [47:0] FTW_OVERRIDE = 48'd0
)(
    input         clock,
    input         reset,
    input  [31:0] io_in,
    output [31:0] io_out
);
    localparam N = 48;

    localparam [N-1:0] M_CONST = M_CYCLES;   // implicit zero-extension of the 32-bit parameter
    wire [N-1:0] m_sel = M_FROM_IO ? {{(N-16){1'b0}}, io_in[31:16]} : M_CONST;
    wire [N-1:0] ftw_sel = (FTW_OVERRIDE != 0) ? FTW_OVERRIDE : (m_sel << (N - LOG2N));

    wire signed [DW-1:0] dac, dac_nl, held, filt;

    generate
        if (TEST_MODE == 1) begin : dac_test
            assign dac = io_in[DW-1:0];
        end else begin : normal_dds
            dds_mod #(.N(N), .AW(AW), .DW(DW), .RW(RW), .FM_SHIFT(25)) u0 (
                .clk(clock), .rst(reset),
                .ftw(ftw_sel),
                .fm_in(32'd0), .pm_in(16'd0), .am_in(AM_IN[15:0]),
                .dac_out(dac));
        end
    endgenerate

    generate
        if (TEST_MODE == 2) begin : with_nonlin
            dac_nonlin #(.DW(DW)) u_nl (.clk(clock), .din(dac), .dout(dac_nl));
        end else begin : without_nonlin
            assign dac_nl = dac;
        end
    endgenerate

    deglitch #(DW)    u1 (.clk(clock), .strobe(1'b1), .din(dac_nl), .dout(held));
    lpf      #(DW, 1) u2 (.clk(clock), .rst(reset), .din(held), .dout(filt));

    wire signed [DW-1:0] out_sel = (OUT_SEL == 1) ? filt : dac_nl;
    assign io_out = {{(32-DW){out_sel[DW-1]}}, out_sel};
endmodule



module dac_nonlin #(
    parameter integer DW           = 16,
    parameter integer INL_PEAK_LSB = 8,
    parameter integer DNL_PEAK_LSB = 3,
    parameter integer DNL_PERIOD   = 97
)(
    input                      clk,
    input  signed [DW-1:0]     din,
    output reg signed [DW-1:0] dout
);
    localparam signed [DW:0] CODE_MIN = -(1 <<< (DW-1));
    localparam signed [DW:0] CODE_MAX = (1 <<< (DW-1)) - 1;

    wire signed [DW-1:0]   xf       = din;
    wire signed [2*DW-1:0] x2_full  = xf * xf;
    wire signed [DW-1:0]   x2_norm  = x2_full >>> (DW-1);
    wire signed [2*DW-1:0] x3_full  = x2_norm * xf;
    wire signed [DW-1:0]   x3_norm  = x3_full >>> (DW-1);
    wire signed [DW+8:0]   inl_scaled = x3_norm * INL_PEAK_LSB;
    wire signed [DW:0]     inl_error  = inl_scaled >>> (DW-1);

    wire [DW-1:0] code        = din;
    wire [31:0]   phase       = code % DNL_PERIOD;
    wire [31:0]   half_period = DNL_PERIOD / 2;
    wire signed [DW:0] dnl_error =
        (phase < half_period)
          ? $signed((phase * (2 * DNL_PEAK_LSB)) / half_period) - DNL_PEAK_LSB
          : DNL_PEAK_LSB - $signed(((phase - half_period) * (2 * DNL_PEAK_LSB)) / (DNL_PERIOD - half_period));

    wire signed [DW+1:0] corrected = xf + inl_error + dnl_error;

    always @(posedge clk) begin
        if (corrected > CODE_MAX)      dout <= CODE_MAX[DW-1:0];
        else if (corrected < CODE_MIN) dout <= CODE_MIN[DW-1:0];
        else                           dout <= corrected[DW-1:0];
    end
endmodule



module dds_mod #(parameter N = 48, AW = 16, DW = 16, RW = 16, FM_SHIFT = 8, ROUND = 1) (
    input                      clk,
    input                      rst,
    input      [N-1:0]         ftw,
    input signed [31:0]        fm_in,
    input      [15:0]          pm_in,
    input      [15:0]          am_in,
    output reg signed [DW-1:0] dac_out
);
    wire signed [N-1:0] fm_in_x = {{(N-32){fm_in[31]}}, fm_in};
    wire signed [N-1:0] fm_ext  = fm_in_x <<< FM_SHIFT;
    wire        [N-1:0] ftw_eff = ftw + fm_ext;

    reg [N-1:0] phase;
    always @(posedge clk)
        if (rst) phase <= 0;
        else     phase <= phase + ftw_eff;

    wire [15:0]   ph16 = phase[N-1:N-16] + pm_in;
    wire [AW-1:0] addr = ph16[15:16-AW];

    wire signed [RW-1:0] s;
    sine_mem #(AW, RW) mem (.clk(clk), .addr(addr), .data(s));

    // AM at ROM precision: RW x 17 (signed) bits
    wire signed [RW+16:0] prod = s * $signed({1'b0, am_in});
    reg  signed [RW-1:0]  am_out;
    always @(posedge clk) am_out <= prod[RW+15:16];

    // single quantization RW -> DW (round half up, saturate)
    localparam integer SH = RW - DW;                        // must be >= 0
    localparam signed [RW:0] RND  = (ROUND != 0 && SH > 0) ? (1 <<< ((SH > 0) ? SH-1 : 0)) : 0;
    localparam signed [RW:0] QMAX =  (1 <<< (DW-1)) - 1;
    localparam signed [RW:0] QMIN = -(1 <<< (DW-1));
    wire signed [RW:0] am_r = {am_out[RW-1], am_out} + RND;
    wire signed [RW:0] q    = am_r >>> SH;

    always @(posedge clk)
        if (rst)              dac_out <= 0;
        else if (q > QMAX)    dac_out <= QMAX[DW-1:0];
        else if (q < QMIN)    dac_out <= QMIN[DW-1:0];
        else                  dac_out <= q[DW-1:0];
endmodule



// Sine ROM generated at simulation start (simulation only: uses $sin)

module sine_mem #(parameter AW = 16, DW = 16) (
    input                       clk,
    input      [AW-1:0]         addr,
    output reg signed [DW-1:0]  data
);
    reg signed [DW-1:0] rom [0:(1<<AW)-1];

    integer i;
    integer r;
    real    v, pi;
    initial begin
        pi = 3.14159265358979323846;
        for (i = 0; i < (1<<AW); i = i + 1) begin
            v = $sin(2.0*pi*i/(1<<AW)) * ((1<<(DW-1)) - 1);
            r = $rtoi($floor(v + 0.5));
            rom[i] = r[DW-1:0];
        end
    end

    always @(posedge clk) data <= rom[addr];
endmodule


module deglitch #(parameter DW = 16) (
    input                      clk,
    input                      strobe,
    input  signed [DW-1:0]     din,
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
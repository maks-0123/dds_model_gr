//
// dds_gr_all.v  -  DDS + static DAC nonlinearity model for SFDR / HD2 / HD3 / IMD3 tests
//                  (AD9081 DAC, Table 3: INL 8 LSB, DNL 3.5 LSB, 16 bit)
//
// Top-level ports are unchanged (clock, reset, io_in[31:0], io_out[31:0]),
// so wrapper.cpp and dds.grc keep working.
//
// ---------------------------------------------------------------------------------
// Signal source
//   SRC    : 0 = internal DDS, 1 = external code from io_in[DW-1:0]
//   TONES  : 1 = single tone (AM_1T), 2 = two tones (AM_2T each), M2 = M1 + M_SPACING
//   Both tones are summed at ROM precision (RW bits) and rounded to DW bits ONCE.
//
// Frequency (coherent: F = M * fDAC / 2^LOG2N, M odd, the FFT length is 2^LOG2N)
//   FTW_OVERRIDE != 0 -> FTW1 = FTW_OVERRIDE (non-coherent, rarely needed)
//   M_FROM_IO = 1     -> M1 = io_in[31:16]
//   otherwise         -> M1 = M_CYCLES
//   KEEP AW >= LOG2N: then there is no phase truncation in coherent mode.
//   (AW = 14 with LOG2N = 15 produces phase-truncation spurs at ~-80 dBc,
//    which mask the DAC nonlinearity.)
//
// Amplitude: AM / 65536 of full scale.  AM_1T = 29274 -> -7.0 dBFS (Table 16 SFDR)
//                                        AM_2T = 32768 -> -6.0 dBFS per tone (Table 16 IMD3)
//
// DAC model (NONLIN = 1), errors in units of 1/2^FRAC LSB:
//   INL2_Q   : peak of the even "bow"   e2 = C2 * (1 - x^2)        -> HD2
//   INL3_Q   : peak of the odd "S"      e3 = C3 * 2.598*(x^3 - x)  -> HD3
//              (x^3 - x has peak 0.385 at x = 1/sqrt(3), so the S-curve peak is exactly C3;
//               the linear part is removed, so no gain error and no clipping at full scale)
//   DNL_Q    : max |DNL| of unary MSB segments (current-steering DAC: 2^SEG_BITS segments,
//              each segment has a random weight error; DNL appears at segment boundaries,
//              the cumulative sum of the errors adds a random-walk INL).
//   SEED     : seed of the segment-mismatch pattern (LCG, reproduced bit-exactly in model_ref.py)
//
// Output: io_out = DAC "analog" value with FRAC extra fraction bits,
//         i.e. full scale = 2^(DW-1+FRAC)  (2^19 for DW=16, FRAC=4).
//         FRAC keeps fractional INL/DNL errors instead of re-quantizing them to 1 LSB.
//   OUT_SEL : 0 = DAC output, 1 = after deglitch + 1-pole LPF
//
module dds_gr #(
    parameter integer SRC       = 0,
    parameter integer TONES     = 1,
    parameter integer NONLIN    = 0,
    parameter integer OUT_SEL   = 0,
    parameter integer DW        = 16,
    parameter integer AW        = 16,
    parameter integer RW        = 20,
    parameter integer FRAC      = 4,
    parameter integer LOG2N     = 15,
    parameter integer M_CYCLES  = 2457,
    parameter integer M_SPACING = 2,
    parameter integer M_FROM_IO = 0,
    parameter integer AM_1T     = 29274,
    parameter integer AM_2T     = 32768,
    parameter [47:0]  FTW_OVERRIDE = 48'd0,
    parameter integer INL2_Q    = 48,     // 3.0 LSB bow
    parameter integer INL3_Q    = 48,     // 3.0 LSB S-curve
    parameter integer DNL_Q     = 56,     // 3.5 LSB
    parameter integer SEG_BITS  = 6,
    parameter integer SEED      = 8      // with the defaults: INL -7.9..+5.2 LSB, DNL -3.5..+3.1 LSB
)(
    input         clock,
    input         reset,
    input  [31:0] io_in,
    output [31:0] io_out
);
    localparam integer N  = 48;
    localparam integer OW = DW + FRAC;

    // ---------------- frequency control ----------------
    localparam [N-1:0] M_CONST = M_CYCLES;
    localparam [N-1:0] SPACING = M_SPACING;
    wire [N-1:0] m_sel = (M_FROM_IO != 0) ? {{(N-16){1'b0}}, io_in[31:16]} : M_CONST;
    wire [N-1:0] ftw1  = (FTW_OVERRIDE != 0) ? FTW_OVERRIDE : (m_sel << (N - LOG2N));
    wire [N-1:0] ftw2  = ftw1 + (SPACING << (N - LOG2N));

    localparam [15:0] AM = (TONES == 2) ? AM_2T[15:0] : AM_1T[15:0];

    // ---------------- DDS: tones at RW bits, one rounding to DW ----------------
    wire signed [RW-1:0] t1, t2;
    dds_core #(.N(N), .AW(AW), .RW(RW)) u_t1 (.clk(clock), .rst(reset), .ftw(ftw1), .am(AM), .tone(t1));
    generate
        if (TONES == 2) begin : g_two
            dds_core #(.N(N), .AW(AW), .RW(RW)) u_t2 (.clk(clock), .rst(reset), .ftw(ftw2), .am(AM), .tone(t2));
        end else begin : g_one
            assign t2 = {RW{1'b0}};
        end
    endgenerate

    wire signed [RW:0]   tsum = {t1[RW-1], t1} + {t2[RW-1], t2};
    wire signed [DW-1:0] dds_code;
    quantize #(.IW(RW+1), .DW(DW)) u_q (.clk(clock), .rst(reset), .din(tsum), .dout(dds_code));

    wire signed [DW-1:0] code = (SRC == 1) ? io_in[DW-1:0] : dds_code;

    // ---------------- DAC ----------------
    wire signed [OW-1:0] dac;
    generate
        if (NONLIN != 0) begin : g_nl
            dac_nonlin #(.DW(DW), .FRAC(FRAC), .INL2_Q(INL2_Q), .INL3_Q(INL3_Q),
                         .DNL_Q(DNL_Q), .SEG_BITS(SEG_BITS), .SEED(SEED))
                u_nl (.clk(clock), .din(code), .dout(dac));
        end else begin : g_ideal
            reg signed [OW-1:0] r;
            always @(posedge clock) r <= {code, {FRAC{1'b0}}};
            assign dac = r;
        end
    endgenerate

    wire signed [OW-1:0] held, filt;
    deglitch #(OW)    u_dg  (.clk(clock), .strobe(1'b1), .din(dac), .dout(held));
    lpf      #(OW, 1) u_lpf (.clk(clock), .rst(reset), .din(held), .dout(filt));

    wire signed [OW-1:0] out_sel = (OUT_SEL == 1) ? filt : dac;
    assign io_out = {{(32-OW){out_sel[OW-1]}}, out_sel};
endmodule


// ---------------------------------------------------------------------------------
// Static DAC nonlinearity: polynomial INL (bow + S) + unary-segment mismatch (DNL)
// ---------------------------------------------------------------------------------
module dac_nonlin #(
    parameter integer DW       = 16,
    parameter integer FRAC     = 4,
    parameter integer INL2_Q   = 64,
    parameter integer INL3_Q   = 64,
    parameter integer DNL_Q    = 56,
    parameter integer SEG_BITS = 6,
    parameter integer SEED     = 1
)(
    input                           clk,
    input  signed [DW-1:0]          din,
    output reg signed [DW+FRAC-1:0] dout
);
    localparam integer H    = DW - 1;
    localparam integer OW   = DW + FRAC;
    localparam integer NSEG = 1 << SEG_BITS;
    localparam integer K3   = (INL3_Q * 25981 + 5000) / 10000;   // C3 * 3*sqrt(3)/2

    localparam signed [47:0] ONE  = 48'sd1 <<< H;
    localparam signed [47:0] HALF = 48'sd1 <<< (H - 1);
    localparam signed [47:0] C2   = INL2_Q;
    localparam signed [47:0] C3K  = K3;
    localparam signed [47:0] YMAX =  (48'sd1 <<< (OW - 1)) - 1;
    localparam signed [47:0] YMIN = -(48'sd1 <<< (OW - 1));

    // normalized powers, Q(H): ONE == full scale
    wire signed [47:0] X  = {{(48-DW){din[DW-1]}}, din};
    wire signed [47:0] X2 = (X * X) >>> H;            //  0 .. ONE
    wire signed [47:0] X3 = (X2 * X) >>> H;           // -ONE .. ONE

    // polynomial INL, rounded, in 1/2^FRAC LSB
    wire signed [47:0] E2 = (C2  * (ONE - X2) + HALF) >>> H;
    wire signed [47:0] E3 = (C3K * (X3 - X)   + HALF) >>> H;

    // ---- unary segment mismatch table (built once at elaboration / start) ----
    // eseg[s] = sum of weight errors of the s segments that are ON below code segment s
    reg signed [31:0] eseg [0:NSEG];
    integer dk [0:NSEG-1];
    integer k, j, acc, sum, mean, mx, a;
    reg [31:0] lcg;
    initial begin
        lcg = SEED;
        sum = 0;
        for (k = 0; k < NSEG; k = k + 1) begin
            acc = 0;
            for (j = 0; j < 12; j = j + 1) begin                  // ~ Gaussian: sum of 12 uniforms
                lcg = lcg * 32'd1664525 + 32'd1013904223;
                acc = acc + $signed({20'd0, lcg[31:20]});
            end
            dk[k] = acc - 12 * 2048;
            sum   = sum + dk[k];
        end
        mean = sum / NSEG;                                        // truncation toward zero
        mx   = 1;
        for (k = 0; k < NSEG; k = k + 1) begin
            dk[k] = dk[k] - mean;
            a = (dk[k] < 0) ? -dk[k] : dk[k];
            if (a > mx) mx = a;
        end
        eseg[0] = 0;
        for (k = 0; k < NSEG; k = k + 1) begin
            dk[k] = (dk[k] * DNL_Q) / mx;                         // max |d| = DNL_Q, truncation
            eseg[k+1] = eseg[k] + dk[k];
        end
    end

    // offset-binary code -> number of ON unary segments
    wire [DW-1:0]       ucode = {~din[DW-1], din[DW-2:0]};
    wire [SEG_BITS-1:0] seg   = ucode[DW-1 -: SEG_BITS];
    wire signed [47:0]  ES    = {{16{eseg[seg][31]}}, eseg[seg]};

    wire signed [47:0] Y = (X <<< FRAC) + E2 + E3 + ES;

    always @(posedge clk) begin
        if      (Y > YMAX) dout <= YMAX[OW-1:0];
        else if (Y < YMIN) dout <= YMIN[OW-1:0];
        else               dout <= Y[OW-1:0];
    end
endmodule


// ---------------------------------------------------------------------------------
// Phase accumulator + sine ROM + amplitude, output at RW bits (no rounding here)
// ---------------------------------------------------------------------------------
module dds_core #(parameter integer N = 48, AW = 16, RW = 20) (
    input                      clk,
    input                      rst,
    input      [N-1:0]         ftw,
    input      [15:0]          am,
    output reg signed [RW-1:0] tone
);
    reg [N-1:0] phase;
    always @(posedge clk)
        if (rst) phase <= {N{1'b0}};
        else     phase <= phase + ftw;

    wire [15:0]   ph16 = phase[N-1:N-16];
    wire [AW-1:0] addr = ph16[15 -: AW];

    wire signed [RW-1:0] s;
    sine_mem #(AW, RW) mem (.clk(clk), .addr(addr), .data(s));

    wire signed [RW+16:0] prod = s * $signed({1'b0, am});
    always @(posedge clk)
        if (rst) tone <= {RW{1'b0}};
        else     tone <= prod[RW+15:16];
endmodule


// single rounding IW -> DW (round half up, saturate)
module quantize #(parameter integer IW = 21, DW = 16) (
    input                      clk,
    input                      rst,
    input  signed [IW-1:0]     din,
    output reg signed [DW-1:0] dout
);
    localparam integer SH = IW - 1 - DW;                       // = RW - DW (IW = RW+1 has one headroom bit)
    localparam signed [IW:0] RND  = (SH > 0) ? ({{IW{1'b0}}, 1'b1} <<< (SH - 1)) : 0;
    localparam signed [IW:0] QMAX =  ({{IW{1'b0}}, 1'b1} <<< (DW - 1)) - 1;
    localparam signed [IW:0] QMIN = -({{IW{1'b0}}, 1'b1} <<< (DW - 1));
    wire signed [IW:0] r = {din[IW-1], din} + RND;
    wire signed [IW:0] q = r >>> SH;
    always @(posedge clk)
        if (rst)           dout <= {DW{1'b0}};
        else if (q > QMAX) dout <= QMAX[DW-1:0];
        else if (q < QMIN) dout <= QMIN[DW-1:0];
        else               dout <= q[DW-1:0];
endmodule


// Sine ROM generated at simulation start (simulation only: uses $sin)
module sine_mem #(parameter integer AW = 16, DW = 20) (
    input                       clk,
    input      [AW-1:0]         addr,
    output reg signed [DW-1:0]  data
);
    reg signed [DW-1:0] rom [0:(1<<AW)-1];
    integer i, r;
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


module deglitch #(parameter integer DW = 20) (
    input                      clk,
    input                      strobe,
    input  signed [DW-1:0]     din,
    output reg signed [DW-1:0] dout
);
    always @(posedge clk)
        if (strobe) dout <= din;
endmodule


module lpf #(parameter integer DW = 20, K = 1) (
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
        if (rst) acc <= {(DW+K){1'b0}};
        else     acc <= acc + (din_x - dout_x);
endmodule

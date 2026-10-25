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
    parameter integer SEED      = 8,      // with the defaults: INL -7.9..+5.2 LSB, DNL -3.5..+3.1 LSB
    parameter integer JIT_FS    = 0,      // jitter RMS in fs (1e-15 s)
    parameter integer SHUF      = 0,      // shuffle parameter
    // ---- dynamic (slew-dependent) nonlinearity, dac_dyn: e = (A*|dx| + B*dx*x + C*dx*x^2) / 2^16
    parameter integer DYN_A_Q   = 0,      // edge asymmetry            -> HD2, grows with fOUT
    parameter integer DYN_B_Q   = 0,      // level-dependent glitch    -> HD2, grows with fOUT
    parameter integer DYN_C_Q   = 0,      // cubic glitch              -> HD3 / IMD3
    parameter integer DYN_D_Q   = 0,      // slew^2 charge injection   -> HD2, ~ fOUT^2
    parameter integer DYN_E_Q   = 0,      // odd slew^2 term           -> HD3 / IMD3, ~ fOUT^2
    parameter integer DYN_P2_Q  = 0,      // output stage x^2           -> HD2, flat vs fOUT
    parameter integer DYN_P3_Q  = 0,      // output stage x^3           -> HD3 / IMD3, flat
    parameter integer NOISE_Q   = 0,      // thermal noise floor, rms in 1/2^FRAC LSB
    parameter integer FDAC_MHZ  = 12000   // DAC clock, MHz (jitter scaling)

)(
    input         clock,
    input         reset,
    input  [31:0] io_in,
    output [31:0] io_out
);
    localparam integer N  = 48;
    localparam integer OW = DW + FRAC;

    // frequency control
    localparam [N-1:0] M_CONST = M_CYCLES;
    localparam [N-1:0] SPACING = M_SPACING;
    wire [N-1:0] m_sel = (M_FROM_IO != 0) ? {{(N-16){1'b0}}, io_in[31:16]} : M_CONST;
    wire [N-1:0] ftw1  = (FTW_OVERRIDE != 0) ? FTW_OVERRIDE : (m_sel << (N - LOG2N));
    wire [N-1:0] ftw2  = ftw1 + (SPACING << (N - LOG2N));

    localparam [15:0] AM = (TONES == 2) ? AM_2T[15:0] : AM_1T[15:0];

    //  DDS: tones at RW bits, one rounding to DW
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

    //  DAC
    wire signed [OW-1:0] dac;
    wire signed [OW-1:0] dyn_dac;
    wire signed [OW-1:0] jit_dac;
    wire signed [OW-1:0] out_dac;

    generate
        if (NONLIN != 0) begin : g_nl
            dac_nonlin #(.DW(DW), .FRAC(FRAC), .INL2_Q(INL2_Q), .INL3_Q(INL3_Q),
                        .DNL_Q(DNL_Q), .SEG_BITS(SEG_BITS), .SEED(SEED), .SHUF(SHUF))
                u_nl (.clk(clock), .din(code), .dout(dac));

        end else begin : g_ideal
            reg signed [OW-1:0] r;
            always @(posedge clock) r <= {code, {FRAC{1'b0}}};
            assign dac = r;
        end
    endgenerate
    // dynamic nonlinearity (combinational output: adds no pipeline stage, PIPE/DELAY unchanged)
    dac_dyn #(.DW(DW), .FRAC(FRAC), .A_Q(DYN_A_Q), .B_Q(DYN_B_Q), .C_Q(DYN_C_Q), .D_Q(DYN_D_Q), .E_Q(DYN_E_Q),
                .P2_Q(DYN_P2_Q), .P3_Q(DYN_P3_Q))
                u_dyn (.clk(clock), .din(dac), .dout(dyn_dac));
    dac_jitter #(.SEED(SEED + 1000), .S(36), .JIT_FS(JIT_FS), .DW(DW), .FRAC(FRAC), .FDAC_MHZ(FDAC_MHZ))
                u_jit (.clk(clock), .din(dyn_dac), .out(jit_dac));
    dac_noise  #(.SEED(SEED + 3000), .NOISE_Q(NOISE_Q), .DW(DW), .FRAC(FRAC))
                u_nse (.clk(clock), .din(jit_dac), .out(out_dac));
    wire signed [OW-1:0] held, filt;
    deglitch #(OW)    u_dg  (.clk(clock), .strobe(1'b1), .din(out_dac), .dout(held));
    lpf      #(OW, 1) u_lpf (.clk(clock), .rst(reset), .din(held), .dout(filt));

    wire signed [OW-1:0] out_sel = (OUT_SEL == 1) ? filt : out_dac;
    assign io_out = {{(32-OW){out_sel[OW-1]}}, out_sel};
endmodule


// Static DAC nonlinearity: polynomial INL (bow + S) + unary-segment mismatch (DNL)

module dac_nonlin #(
    parameter integer DW       = 16,
    parameter integer FRAC     = 4,
    parameter integer INL2_Q   = 64,
    parameter integer INL3_Q   = 64,
    parameter integer DNL_Q    = 56,
    parameter integer SEG_BITS = 6,
    parameter integer SEED     = 1,
    parameter integer SHUF     = 0
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
    wire signed [47:0] E2 = (C2  * (ONE - X2) + HALF) >>> H; //сдвигаем 
    wire signed [47:0] E3 = (C3K * (X3 - X)   + HALF) >>> H;

    // eseg[s] = sum of weight errors of the s segments that are ON below code segment s
    reg signed [31:0] eseg [0:NSEG];
    integer dk [0:NSEG-1];
    integer k, j, acc, sum, mean, mx, a;
    reg [31:0] lcg;
    reg [31:0] p;

    initial begin
        lcg = SEED;
        sum = 0;
        for (k = 0; k < NSEG; k = k + 1) begin
            acc = 0;
            for (j = 0; j < 12; j = j + 1) begin                  // ~ Gaussian: sum of 12 uniforms
                lcg = lcg * 32'd1664525 + 32'd1013904223;          // псевдослучайный генератор (LCG) так как отрезается от оч большого числа, 32 бита 
                acc = acc + $signed({20'd0, lcg[31:20]});
            end
            dk[k] = acc - 12 * 2048; // error shifted to zero mean (12*2048 = 24576)

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

    reg [31:0] lcg_r = SEED + 2000;
    reg [SEG_BITS-1:0] ptr = 0;

    wire [SEG_BITS-1:0] p0 = (SHUF == 1) ? lcg_r[31 -: SEG_BITS] :
                            (SHUF == 2) ? ptr : {SEG_BITS{1'b0}};
    
    wire [SEG_BITS:0] ps = {1'b0, p0} + {1'b0 , seg};
    wire [SEG_BITS-1:0] q = ps[SEG_BITS-1:0];
    wire wrap = ps[SEG_BITS];

    wire signed [31:0] ec_q = eseg[q];
    wire signed [31:0] ec_p = eseg[p0];
    wire signed [31:0] ec_t = wrap ? eseg[NSEG] :32'sd0; 
    wire signed [47:0]  ES    =  ec_q - ec_p + ec_t;

    always @(posedge clk) begin 
        lcg_r <= lcg_r * 32'd1664525 + 32'd1013904223; 
        if (SHUF == 2) ptr <= q;
        end 

    wire signed [47:0] Y = (X <<< FRAC) + E2 + E3 + ES;

    always @(posedge clk) begin 
        if (Y > YMAX) dout <= YMAX[OW-1:0];
        else if (Y < YMIN) dout <= YMIN[OW-1:0];
        else dout <= Y[OW-1:0];
    end

endmodule

// ---------------------------------------------------------------------------------
// Dynamic (slew-dependent) DAC nonlinearity.          stage 1, AD9081 Table 16
//
// The static curve (dac_nonlin) does not depend on frequency, so it cannot explain the
// SFDR/IMD3 roll-off of Table 16 (80 dBc at 70 MHz -> 68 dBc at 4.5 GHz).  What does roll
// off is the switching error: every clock the current cells are re-steered, and the charge
// lost in the transition depends on how far and from which level the output moves.
//
//   dx = x[n] - x[n-1]        (one output step; |dx| ~ 2*sin(pi*f/fDAC) * amplitude -> grows with f)
//   e  = ( A*|dx| + B*dx*xn + C*dx*xn^2 + D*|dx|*dxn + E*dx*|dx|n ) / 2^SH,  xn = x / full scale
//        A : edge asymmetry (rise != fall).  |dx| of a sine is |sin| -> even harmonics  -> HD2 ~ f
//        B : level-dependent glitch area.    dx*x = 0.5*d(x^2)/dt               -> HD2 ~ f
//        C : cubic glitch.                   dx*x^2                             -> HD3, IMD3 ~ f
//        D : charge injection ~ slew^2.      |dx|^2 = (1-cos2wt)/2              -> HD2 ~ f^2
//        E : odd slew^2 term.                dx*|dx| (half-wave symmetric)      -> HD3 ~ f^2
//   plus the memoryless distortion of the analog output stage (not the current cells, so it is
//   not limited by the INL of Table 3 and shuffling does not touch it):
//        P2*xn^2 -> HD2, P3*xn^3 -> HD3, both flat in frequency.  They set the low-frequency
//        corner of Table 16 (80 dBc at 70 MHz), where every slew term has died out.
//   (the plan wrote only A and B; dx*x is second order and gives no 2f1-f2 product, so the odd
//    terms C and E are what set IMD3, and the f^2 terms D, E are what give Table 16 its
//    12 dB SFDR roll-off from 70 MHz to 4.5 GHz - a pure ~f model can only bend by 5.6 dB.
//    Coefficients are fitted by scripts/fit_dyn.py)
//
// The output is combinational (only x[n-1] is registered), so the module adds no pipeline
// stage and the PIPE/DELAY alignment of the shuffle reference stays valid.
// ---------------------------------------------------------------------------------
module dac_dyn #(
    parameter integer DW   = 16,
    parameter integer FRAC = 4,
    parameter integer A_Q  = 0,
    parameter integer B_Q  = 0,
    parameter integer C_Q  = 0,
    parameter integer D_Q  = 0,
    parameter integer E_Q  = 0,
    parameter integer P2_Q = 0,
    parameter integer P3_Q = 0
)(
    input                        clk,
    input  signed [DW+FRAC-1:0]  din,
    output signed [DW+FRAC-1:0]  dout
);
    localparam integer OW = DW + FRAC;
    localparam integer H  = OW - 1;                 // full scale = 2^H
    localparam integer SH = 16;                     // coefficient scale: A_Q = 1 -> |dx|/2^16
    localparam signed [63:0] RND  = 64'sd1 <<< (SH - 1);
    localparam signed [63:0] YMAX =  (64'sd1 <<< H) - 1;
    localparam signed [63:0] YMIN = -(64'sd1 <<< H);

    reg signed [OW-1:0] prev = {OW{1'b0}};
    always @(posedge clk) prev <= din;

    wire signed [63:0] X  = {{(64-OW){din[OW-1]}},  din};
    wire signed [63:0] XP = {{(64-OW){prev[OW-1]}}, prev};
    wire signed [63:0] D  = X - XP;
    wire signed [63:0] AD = (D < 0) ? -D : D;

    wire signed [63:0] DX  = (D  * X)  >>> H;       // dx * xn
    wire signed [63:0] DX2 = (DX * X)  >>> H;       // dx * xn^2
    wire signed [63:0] AA  = (AD * AD) >>> H;       // |dx| * |dx|n
    wire signed [63:0] DA  = (D  * AD) >>> H;       // dx  * |dx|n
    wire signed [63:0] XX  = (X  * X)  >>> H;       // xn^2 * full scale
    wire signed [63:0] XXX = (XX * X)  >>> H;       // xn^3 * full scale

    wire signed [63:0] E = (A_Q * AD + B_Q * DX + C_Q * DX2
                            + D_Q * AA + E_Q * DA
                            + P2_Q * XX + P3_Q * XXX + RND) >>> SH;
    wire signed [63:0] Y = X + E;
    assign dout = (Y > YMAX) ? YMAX[OW-1:0] : (Y < YMIN) ? YMIN[OW-1:0] : Y[OW-1:0];
endmodule


module dac_jitter #(
    parameter integer SEED     = 1,
    parameter integer S        = 36,
    parameter integer JIT_FS   = 50 ,
    parameter integer DW       = 16,
    parameter integer FRAC     = 4,
    parameter integer FDAC_MHZ = 12000
)(
    input clk, 
    input signed [DW+FRAC-1:0] din,

    output reg signed [DW+FRAC-1:0] out
);  
    localparam integer OW = DW + FRAC;
    localparam signed [63:0] YMAX =  (64'sd1 <<< (OW - 1)) - 1;
    localparam signed [63:0] YMIN = -(64'sd1 <<< (OW - 1));

    reg signed [DW+FRAC-1:0] dac_prev;
    reg [31:0] lcg;
    reg signed [DW+FRAC:0] dx;
    integer j, err_o;
    localparam real  SIG_TS = JIT_FS * 1.0e-15 * (FDAC_MHZ * 1.0e6);
    localparam signed [63:0] KJ = $rtoi(SIG_TS /4096.0 * (2.0 ** S));

    reg signed [63:0] err, y;

    initial begin lcg = SEED; dac_prev = 0; out = 0;
    end

    always @(posedge clk) begin
        err_o = 0;
        for (j = 0; j < 12; j = j + 1) begin                  // ~ Gaussian: sum of 12 uniforms
            lcg = lcg * 32'd1664525 + 32'd1013904223;          // псевдослучайный генератор (LCG) так как отрезается от оч большого числа, 32 бита 
            err_o = err_o + $signed({20'd0, lcg[31:20]});
        end
        err_o = err_o - 12 * 2048;
        dx = din - dac_prev;
        err = (dx * KJ * err_o) >>> S;
        y   = din - err;
        if      (y > YMAX) out <= YMAX[OW-1:0];               // saturate instead of wrapping
        else if (y < YMIN) out <= YMIN[OW-1:0];
        else               out <= y[OW-1:0];
        dac_prev <= din;  

        end
endmodule

// ---------------------------------------------------------------------------------
// Thermal noise floor of the DAC output stage: white Gaussian, rms = NOISE_Q in 1/2^FRAC LSB.
// NOISE_Q = 115 -> -168 dBc/Hz at 0 dBFS, fDAC = 12 GSPS (AD9081 Table 16 NSD at low fOUT).
// ---------------------------------------------------------------------------------
module dac_noise #(
    parameter integer SEED    = 1,
    parameter integer NOISE_Q = 0,
    parameter integer DW      = 16,
    parameter integer FRAC    = 4
)(
    input clk,
    input signed [DW+FRAC-1:0] din,
    output signed [DW+FRAC-1:0] out
);
    localparam integer OW = DW + FRAC;
    localparam signed [63:0] YMAX =  (64'sd1 <<< (OW - 1)) - 1;
    localparam signed [63:0] YMIN = -(64'sd1 <<< (OW - 1));

    // combinational output (only the generator state is registered): no extra pipeline stage
    reg  [31:0] lcg = SEED;
    integer j;
    reg signed [63:0] acc;
    reg  [31:0] nxt;
    always @(*) begin                                  // 12 fresh uniforms -> ~Gaussian, sigma = 4096
        acc = 0;
        nxt = lcg;
        for (j = 0; j < 12; j = j + 1) begin
            nxt = nxt * 32'd1664525 + 32'd1013904223;
            acc = acc + $signed({20'd0, nxt[31:20]});
        end
        acc = acc - 12 * 2048;
    end
    always @(posedge clk) lcg <= nxt;                  // the next sample uses 12 new values

    wire signed [63:0] X = {{(64-OW){din[OW-1]}}, din};
    wire signed [63:0] Y = (NOISE_Q == 0) ? X : X + ((acc * NOISE_Q) >>> 12);
    assign out = (Y > YMAX) ? YMAX[OW-1:0] : (Y < YMIN) ? YMIN[OW-1:0] : Y[OW-1:0];
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
            r = $rtoi($floor(v + 0.5));                                 //округление ошибка
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
    assign dout = acc[DW+K-1:K];                            //отбрасиваем K младших битов
    wire signed [DW+K-1:0] din_x  = {{K{din[DW-1]}},  din};
    wire signed [DW+K-1:0] dout_x = {{K{dout[DW-1]}}, dout};
    always @(posedge clk)
        if (rst) acc <= {(DW+K){1'b0}};
        else     acc <= acc + (din_x - dout_x);
endmodule
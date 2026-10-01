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

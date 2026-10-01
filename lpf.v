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

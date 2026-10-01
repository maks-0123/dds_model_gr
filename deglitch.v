module deglitch #(parameter DW = 16) (
    input                     clk,
    input                     strobe,
    input  signed [DW-1:0]    din,
    output reg signed [DW-1:0] dout
);
    always @(posedge clk)
        if (strobe) dout <= din;
endmodule

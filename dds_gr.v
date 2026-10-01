module dds_gr(
    input         clock,
    input         reset,
    input  [31:0] io_in,    
    output [31:0] io_out
);
    wire signed [15:0] dac, held, filt;

    dds_mod #(.N(48), .AW(14), .DW(16), .FM_SHIFT(25)) u0 (
    .clk(clock), .rst(reset),
    .ftw(48'h080000000000),      
    .fm_in(io_in), .pm_in(16'd0), .am_in(16'hFFFF),
    .dac_out(dac));

    deglitch #(16) u1
        (.clk(clock), .strobe(1'b1), .din(dac), .dout(held));
    lpf #(16, 1)   u2 
        (.clk(clock), .rst(reset), .din(held), .dout(filt));

    assign io_out = {{16{filt[15]}}, filt};
endmodule

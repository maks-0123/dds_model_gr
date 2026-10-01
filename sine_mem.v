module sine_mem#(parameter AW = 14, DW = 16) ( 
    input clk,
    input [AW-1:0] addr,
    output reg signed [DW-1: 0] data
);
    reg [DW-1: 0] rom [0:(1<<AW)-1];
    initial $readmemh("/Users/maksimromanuta/Documents/work_on_etalon/icarus_DDS/sine.hex", rom);
    always @(posedge clk) data <= rom[addr];
endmodule

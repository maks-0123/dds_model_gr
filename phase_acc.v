module phase_acc #(parameter N = 16) (
    input              clk,
    input              rst,
    input  [N-1:0]     ftw,
    output reg [N-1:0] phase
);
    always @(posedge clk) begin
        if (rst) phase <= 0;
        else     phase <= phase + ftw;   // переполнение = естественный "wrap" фазы
    end
endmodule

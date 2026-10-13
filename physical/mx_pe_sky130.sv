module mx_pe_sky130(
 input wire clk,rst,in_valid, output wire in_ready,
 input wire [63:0] in_a,in_b,
 input wire [7:0] in_scale_a,in_scale_b,
 input wire [2:0] in_fmt, input wire in_bf16, input wire [4:0] in_trunc,
 output wire out_valid,input wire out_ready,
 output wire [31:0] out_data,output wire [4:0] out_flags
);
 mx_pe #(.LANES(8),.PIPE_STAGES(4)) core(.*);
endmodule

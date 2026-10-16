// Bounded single-block numerical refinement. Symbolic values are explicit ports.
module arithmetic_proof #(parameter integer LANES=8, STAGES=5, FMT=4, NEGATIVE_CONTROL=0)(input clk,input [255:0] symbolic_a,symbolic_b,input [7:0] symbolic_sa,symbolic_sb,input symbolic_bf,input [4:0] symbolic_trunc);
reg [255:0] avec,bvec;
reg [7:0] sa,sb;
reg bf;
reg [4:0] trunc;
localparam integer BEATS=32/LANES, END=BEATS+STAGES;
reg [3:0] age=0;
always @(posedge clk) if(age==0) begin
 avec<=NEGATIVE_CONTROL?256'b0:symbolic_a;bvec<=NEGATIVE_CONTROL?256'b0:symbolic_b;sa<=NEGATIVE_CONTROL?8'd127:symbolic_sa;sb<=NEGATIVE_CONTROL?8'd127:symbolic_sb;bf<=NEGATIVE_CONTROL?1'b0:symbolic_bf;trunc<=NEGATIVE_CONTROL?5'b0:symbolic_trunc;
end
wire rst=age==0;
wire valid=(age>=1 && age<=BEATS);
wire [LANES*8-1:0] a=avec[LANES*8*(int'(age)-1)+:LANES*8], b=bvec[LANES*8*(int'(age)-1)+:LANES*8];
wire ready,ov;wire[31:0]data;wire[4:0]flags;
mx_pe #(.LANES(LANES),.PIPE_STAGES(STAGES)) dut(clk,rst,valid,ready,a,b,sa,sb,3'(FMT),bf,trunc,ov,1'b1,data,flags);
always @(posedge clk) if(age<END+1) age<=age+1'b1;
`include "converter_spec.svh"
`include "arithmetic_reference.svh"

always @* if(age==END) begin
 assert(ov);
 assert({flags,data}==(reference_dot(avec,bvec,3'(FMT),sa,sb,bf,trunc)^37'(NEGATIVE_CONTROL)));
end
endmodule

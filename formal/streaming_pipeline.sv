module streaming_proof #(parameter LANES=8,STAGES=5,NEGATIVE_CONTROL=0)(input clk,rst,in_valid,out_ready,input[69:0] term,input[3:0] special,input[LANES*8-1:0] a,b,input[7:0]sa,sb,input[2:0]fmt,input bf,input[4:0]trunc);
localparam BEATS=32/LANES, DELAY=(STAGES==3)?1:2;
wire ir,ov;wire[31:0]data;wire[4:0]flags;
mx_pe #(.LANES(LANES),.PIPE_STAGES(STAGES)) dut(term,special,clk,rst,in_valid,ir,a,b,sa,sb,fmt,bf,trunc,ov,out_ready,data,flags);
typedef struct packed{logic[69:0] running,completed;logic[3:0]rf,cf;logic bf;logic signed[9:0]scale;} state_t;
typedef struct packed{logic last,bf,poison;logic[4:0]trunc;logic[5:0]grid;logic signed[9:0]scale;} meta_t;
function automatic state_t fold(input state_t s,input valid,last,input[69:0] t,input[3:0] f,input outbf,input signed[9:0] sc);
state_t q;begin q=s;if(valid)begin if(last)begin q.completed=s.running+t;q.cf=s.rf|f;q.bf=outbf;q.scale=sc;q.running=0;q.rf=0;end else begin q.running=s.running+t;q.rf=s.rf|f;end end fold=q;end endfunction
function automatic[5:0] grid(input[2:0] f);case(f)0:grid=14;1:grid=0;2:grid=24;3:grid=26;4:grid=30;default:grid=0;endcase endfunction
state_t g,history[STAGES-1],actual;
meta_t held,active,gm1;
reg[2:0] beat=0,heldfmt=0;
reg[STAGES-1:0] vp=0;
reg gv1,gv2;
reg[11:0] gm2;
wire ga=!vp[STAGES-1]||out_ready;
reg past_valid=0;
always_comb begin
active=held;
if(beat==0)begin active.bf=bf;active.trunc=trunc;active.grid=grid(fmt);active.scale=10'(int'(sa)+int'(sb)-254);active.poison=(sa==255)||(sb==255)||(fmt>4);end
active.last=(int'(beat)==BEATS-1);
actual={dut.running,dut.sum3,dut.run_nan,dut.run_pos,dut.run_neg,dut.run_approx,dut.nan3,dut.pos3,dut.neg3,dut.approx3,dut.m3.bf16,dut.m3.scale};
end
generate if(STAGES==3)begin
always_comb begin gv1=in_valid;gm1=active;end
end else begin
always @(posedge clk) if(rst)begin gv1<=0;gm1<='0;end else if(ga)begin gv1<=in_valid;gm1<=active;end
end endgenerate
always @(posedge clk)begin
past_valid<=1;
if(rst)begin
beat<=0;held<=0;heldfmt<=0;g<=0;vp<=0;gv2<=0;gm2<=0;
for(integer i=0;i<STAGES-1;i++)history[i]<=0;
end else if(ga)begin
g<=fold(g,in_valid,active.last,term,special,active.bf,active.scale);
history[0]<=g;
for(integer i=1;i<STAGES-1;i++)history[i]<=history[i-1];
vp<={vp[STAGES-2:0],(in_valid&&active.last)};
gv2<=gv1;gm2<={gm1.last,gm1.bf,gm1.scale};
if(in_valid)begin
if(beat==0)begin held<=active;heldfmt<=fmt;end
if(int'(beat)==BEATS-1)beat<=0;else beat<=beat+1'b1;
end
end
end
always @* begin
if(!past_valid)assume(rst);
if(past_valid)begin
assert(ov==(vp[STAGES-1]^1'(NEGATIVE_CONTROL)));
assert(ir==(ga&&!rst));
assert(dut.beat==beat);assert(dut.held_fmt==heldfmt);assert(dut.held_meta==held);assert(dut.input_meta==active);
assert(dut.v1==gv1);assert(dut.m1==gm1);assert(dut.v2==gv2);assert(dut.m2==gm2);
assert(dut.v3==vp[DELAY]);
if(STAGES==3)assert(vp[0]==(dut.v2&&dut.m2.last));
else begin
assert(vp[0]==(dut.v1&&dut.m1.last));
assert(vp[1]==(dut.v2&&dut.m2.last));
end
assert(actual==history[DELAY-1]);
if(STAGES==3)assert(g==fold(actual,dut.v2,dut.m2.last,dut.proof_sum2,{dut.nan2,dut.pos2,dut.neg2,dut.approx2},dut.m2.bf16,dut.m2.scale));
else begin
assert(history[0]==fold(actual,dut.v2,dut.m2.last,dut.proof_sum2,{dut.nan2,dut.pos2,dut.neg2,dut.approx2},dut.m2.bf16,dut.m2.scale));
assert(g==fold(history[0],dut.v1,dut.m1.last,dut.proof_sum1,dut.proof_flags1,dut.m1.bf16,dut.m1.scale));
end
if(STAGES==5)begin
assert(dut.sum4==history[DELAY].completed);
assert({dut.nan4,dut.pos4,dut.neg4,dut.approx4}==history[DELAY].cf);
assert(dut.m4=={history[DELAY].bf,history[DELAY].scale});
assert(dut.v4==vp[DELAY+1]);
end
end
end
endmodule

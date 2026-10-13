"""Generate checked zero-delay gate activity for post-route OpenSTA power.
Requires Icarus Verilog, the routed netlist, and PDK_ROOT. No SDF/glitch claim.
"""
import argparse,json,os,pathlib,random,re,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.mx import decode,dot,FORMATS
p=argparse.ArgumentParser();p.add_argument('netlist');p.add_argument('--period-ns',type=int,default=200);p.add_argument('--blocks',type=int,default=200);args=p.parse_args()
work=ROOT/'build/gate-power';work.mkdir(parents=True,exist_ok=True)
r=random.Random(20261013);blocks=[];stim=[];expected=[]
for i in range(args.blocks):
 fmt=i%5;bf16=(i//5)%2;trunc=(0,2,7,15)[(i//10)%4];width=sum(FORMATS[fmt][:2])+1
 finite=[x for x in range(1<<width) if decode(x,fmt).kind=='finite']
 a=[r.choice(finite) for _ in range(32)];b=[r.choice(finite) for _ in range(32)]
 sa=r.randrange(120,135);sb=r.randrange(120,135)
 data,flags=dot(a,b,fmt,sa,sb,bf16,trunc);expected.append(f"expected[{i}]=37'h{((flags<<32)|data):010x};")
 for k in range(4):
  av=sum(v<<(8*j) for j,v in enumerate(a[k*8:k*8+8]));bv=sum(v<<(8*j) for j,v in enumerate(b[k*8:k*8+8]))
  stim.append(f"@(negedge clk); in_valid=1; in_a=64'h{av:016x}; in_b=64'h{bv:016x}; in_fmt=3'd{fmt}; in_bf16=1'd{bf16}; in_trunc=5'd{trunc}; in_scale_a=8'd{sa}; in_scale_b=8'd{sb};")
 # Drain and idle after each group to include idle behavior.
 if i%20==19:stim.append('@(negedge clk); in_valid=0; repeat(8) @(negedge clk);')
tb='''`timescale 1ns/1ps
module power_tb;
reg clk=0,rst=1,in_valid=0,out_ready=1; wire in_ready,out_valid;
reg [63:0] in_a=0,in_b=0; reg [7:0] in_scale_a=127,in_scale_b=127;
reg [2:0] in_fmt=0;reg in_bf16=0;reg [4:0] in_trunc=0;
wire [31:0] out_data;wire [4:0] out_flags;
mx_pe_sky130 dut(.*);
reg [36:0] expected[0:BLOCKS-1];integer checked=0;
always #HALFPERIOD clk=~clk;
always @(posedge clk) if(!rst && out_valid && out_ready) begin
 if(checked>=BLOCKS) $fatal(1,"extra result");
 if({out_flags,out_data} !== expected[checked]) $fatal(1,"mismatch %0d got %h expected %h",checked,{out_flags,out_data},expected[checked]);
 checked=checked+1;
end
initial begin
EXPECTED
 repeat(3) @(negedge clk); rst=0;
 $dumpfile("activity.vcd"); $dumpvars(0,dut);
STIM
 @(negedge clk);in_valid=0;
 repeat(12) @(negedge clk);
 if(checked!=BLOCKS) $fatal(1,"missing outputs %0d",checked);
 $display("GATE_PASS checked=%0d",checked);$finish;
end
initial begin #TIMEOUT; $fatal(1,"timeout");end
endmodule
'''.replace('BLOCKS',str(args.blocks)).replace('HALFPERIOD',str(args.period_ns/2)).replace('EXPECTED','\n'.join(expected)).replace('STIM','\n'.join(stim)).replace('TIMEOUT',str(args.period_ns*(args.blocks*5+100)))
(work/'power_tb.sv').write_text(tb)
lib=pathlib.Path(os.environ['PDK_ROOT'])/'sky130A/libs.ref/sky130_fd_sc_hd/verilog'
subprocess.run(['iverilog','-g2012','-DFUNCTIONAL','-DUNIT_DELAY=','-s','power_tb','-o',str(work/'sim.vvp'),str(work/'power_tb.sv'),str(pathlib.Path(args.netlist).resolve()),str(lib/'primitives.v'),str(lib/'sky130_fd_sc_hd.v')],check=True)
with (work/'simulation.log').open('w') as f:subprocess.run(['vvp','sim.vvp'],cwd=work,stdout=f,stderr=subprocess.STDOUT,check=True)
shutil.copy2(work/'simulation.log',ROOT/'reports/gate-simulation.log')
timestamps=[int(x) for x in re.findall(r'^#(\d+)',(work/'activity.vcd').read_text(),re.M)]
duration_ns=(timestamps[-1]-timestamps[0])/1000
meta={'activity_window_ns':duration_ns,'achieved_million_blocks_per_second':args.blocks*1000/duration_ns,'seed':20261013,'blocks_checked':args.blocks,'period_ns':args.period_ns,'frequency_mhz':1000/args.period_ns,'formats':5,'finite_uniform_codes':True,'scale_codes':[120,134],'trunc':[0,2,7,15],'simulation':'zero-delay gate-level; no glitch/SDF power claim','vcd_scope':'power_tb/dut','vcd':str(work/'activity.vcd'),'netlist':str(pathlib.Path(args.netlist).resolve())}
(ROOT/'reports/gate-activity.json').write_text(json.dumps(meta,indent=2)+'\n');print(meta)

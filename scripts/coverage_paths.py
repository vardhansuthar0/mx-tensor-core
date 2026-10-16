"""Prove the four 16-lane accumulation expressions unreachable in their branch.

The product cone is overapproximated by four arbitrary per-cycle flags. Product
data is irrelevant to this control/flag property and is removed. No assumption
is made about those flags. All original valid, ready, metadata and flag state
transitions are retained verbatim. A modulo-two phase conservation invariant
connects the input beat to the pending decode/product pipeline entries.
"""
import hashlib,json,pathlib,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]

def run():
    rtl=(ROOT/'rtl/mx_pe.sv').read_text()
    abstract=rtl.replace('    input wire clk, rst, in_valid,','    input wire [3:0] proof_flags, input wire clk, rst, in_valid,')
    start=abstract.index('    always_comb begin\n        products_comb=')
    end=abstract.index('    always_ff @(posedge clk) begin\n        if(rst) begin v2',start)
    abstract=abstract[:start]+"    always_comb begin products_comb='0; {nan_comb,pos_comb,neg_comb,approx_comb}=proof_flags;mag=0;clipped=0;mant_product=0;alignment=0;cut=0;end\n"+abstract[end:]
    work=ROOT/'reports/coverage-path-harnesses';work.mkdir(parents=True,exist_ok=True)
    source=work/'abstract-pe.sv';source.write_text(abstract)
    yosys=shutil.which('yowasp-yosys')
    results=[]
    for stages in (3,4,5):
        for negative in (False,True):
            label=f'p{stages}'+('-negative' if negative else '')
            parity='phase ^ dut.v2' if stages==3 else 'phase ^ dut.v1 ^ dut.v2'
            predicate='(dut.run_nan || dut.run_pos || dut.run_neg || dut.run_approx)'
            if not negative:predicate='!'+predicate
            header=f'''module coverage_paths(input [3:0] abstract_flags,input clk,rst,in_valid,out_ready,
input [127:0] in_a,in_b,input [7:0] sa,sb,input [2:0] fmt,input bf,input [4:0] trunc);
wire ir,ov;wire [31:0] data;wire [4:0] flags;
mx_pe #(.LANES(16),.PIPE_STAGES({stages})) dut(abstract_flags,clk,rst,in_valid,ir,in_a,in_b,sa,sb,fmt,bf,trunc,ov,out_ready,data,flags);
reg past_valid=0;reg phase=0;
always @(posedge clk) begin
past_valid<=1;
if(rst) phase<=0;else if(dut.advance && dut.v2) phase<=~phase;
end
always @* begin
if(!past_valid) assume(rst);
if(past_valid) begin
'''
            invariants=f'''assert(dut.beat == ({parity}));
if(dut.v1) assert(dut.m1.last == (phase ^ dut.v2));
if(dut.v2) assert(dut.m2.last == phase);
if(!phase) assert(!(dut.run_nan || dut.run_pos || dut.run_neg || dut.run_approx));
'''
            body=header+('' if negative else invariants)+f'if(dut.v2 && !dut.m2.last) assert({predicate});\nend\nend\nendmodule\n'
            harness=work/f'{label}.sv';harness.write_text(body)
            log=ROOT/'reports'/f'coverage-path-{label}.log'
            sat='sat -seq 8 -timeout 20 -set-assumes -prove-asserts -verify' if negative else 'sat -seq 3 -tempinduct -maxsteps 8 -timeout 20 -set-assumes -prove-asserts -verify'
            command=f'read_slang -j 1 -DSYNTHESIS --top coverage_paths rtl/mx_csa.sv {source.relative_to(ROOT)} {harness.relative_to(ROOT)}; prep -top coverage_paths -flatten; chformal -lower; memory_map; opt; dffunmap; '+sat
            with log.open('w') as f:
                try:
                    result=subprocess.run([yosys,'-Q','-T','-p',command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=100)
                    text=log.read_text()
                    passed=(result.returncode!=0 and 'model found: FAIL!' in text) if negative else (result.returncode==0 and 'Induction step proven: SUCCESS!' in text)
                except subprocess.TimeoutExpired:passed=False
            results.append({'stages':stages,'negative_control':negative,'status':'pass' if passed else 'unclosed','log':str(log.relative_to(ROOT)),'harness':str(harness.relative_to(ROOT))})
            print(label,results[-1]['status'],flush=True)
    paths=['rtl/mx_pe.sv','rtl/mx_csa.sv','scripts/coverage_paths.py']
    report={'status':'pass' if all(r['status']=='pass' for r in results) else 'unclosed',
            'scope':'16-lane PE: run_* is zero whenever v2 && !m2.last, all three pipeline depths. Arbitrary product flags and input streams, stalls and resets after initial reset. Not arithmetic equivalence.',
            'abstraction':'Replace only the combinational product cone with arbitrary flags and zero data; property/control cone is independent of product data.',
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'results':results}
    (ROOT/'reports/coverage-paths.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['status']!='pass':raise SystemExit(1)

if __name__=='__main__':run()

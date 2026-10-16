"""Prove production normalization/packet registers and output capture.

The scalar converter is an arbitrary 37-bit oracle. This proves its magnitude
and leading inputs and register binding, not the entire PE.
"""
import hashlib,json,pathlib,resource,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
def extract(rtl):
    lead=rtl[rtl.index('    function automatic integer leading70'):rtl.index('    // Keep the signed-total interface')]
    tail=rtl[rtl.index('    logic signed [69:0] sum4;'):rtl.index(chr(96)+'ifndef SYNTHESIS')]
    binding='convert(sum4,m4.bf16,m4.scale,nan4,pos4,neg4,approx4,converter_mag,converter_lead)'
    if tail.count(binding)!=1:raise RuntimeError('Converter argument binding changed')
    return lead,tail.replace(binding,'conversion_oracle')
def run():
    frontend=shutil.which('yowasp-yosys');backend=shutil.which('yosys')
    if not frontend or not backend:raise SystemExit('Requires both Yosys frontends')
    paths=['rtl/mx_pe.sv','scripts/normalization_formal.py']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    lead,tail=extract((ROOT/'rtl/mx_pe.sv').read_text())
    header="""module normalization_proof #(parameter PIPE_STAGES=5,NEGATIVE=0)(
input clk,rst,advance,input signed[69:0]sum3,input[10:0]meta3,
input nan3,pos3,neg3,approx3,v3,input[36:0]conversion_oracle);
typedef struct packed {logic bf16;logic signed[9:0]scale;}out_meta_t;
out_meta_t m3;
always_comb m3=meta3;
logic out_valid;logic[31:0]out_data;logic[4:0]out_flags;
"""
    checks="""
reg past_valid=0;
reg signed[69:0]saved_sum;
reg[10:0]saved_meta;
reg[3:0]saved_flags;
reg saved_valid;
reg[36:0]gold_result;
reg gold_valid;
wire[69:0]expected_sum=(PIPE_STAGES==5)?saved_sum:sum3;
wire[10:0]expected_meta=(PIPE_STAGES==5)?saved_meta:meta3;
wire[3:0]expected_flags=(PIPE_STAGES==5)?saved_flags:{nan3,pos3,neg3,approx3};
wire expected_valid=(PIPE_STAGES==5)?saved_valid:v3;
wire[69:0]absolute=expected_sum[69]?(~expected_sum+70'd1):expected_sum;
reg[6:0]highest;
always_comb begin highest=0;for(integer k=0;k<70;k++)if(absolute[k])highest=7'(k);end
always @(posedge clk)begin
past_valid<=1;
if(rst)begin saved_sum<=0;saved_meta<=0;saved_flags<=0;saved_valid<=0;gold_result<=0;gold_valid<=0;end
else if(advance)begin
saved_sum<=sum3;saved_meta<=meta3;saved_flags<={nan3,pos3,neg3,approx3};saved_valid<=v3;
gold_valid<=expected_valid;
if(expected_valid)gold_result<=conversion_oracle;
end
end
always @*begin
if(!past_valid)assume(rst);
if(past_valid)begin
assert(sum4==expected_sum);assert(m4==expected_meta);
assert({nan4,pos4,neg4,approx4}==expected_flags);assert(v4==expected_valid);
assert(converter_mag==(absolute^70'(NEGATIVE)));assert(converter_lead==highest);
assert(out_valid==gold_valid);assert({out_flags,out_data}==gold_result);
end
end
endmodule
"""
    source=ROOT/'reports/normalization-harness.sv';source.write_text(header+lead+tail+checks)
    work=ROOT/'build/normalization-formal';work.mkdir(parents=True,exist_ok=True)
    results=[]
    def limit():resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    for stages in (3,4,5):
        for negative in (False,True):
            name=f'p{stages}'+('-negative' if negative else '')
            design=work/(name+'.json');frontlog=ROOT/'reports'/f'normalization-{name}-frontend.log';log=ROOT/'reports'/f'normalization-{name}.log'
            cmd=f'read_slang -j 1 -GPIPE_STAGES={stages} -GNEGATIVE={int(negative)} --top normalization_proof {source.relative_to(ROOT)}; prep -top normalization_proof -flatten; chformal -lower; memory_map; opt; dffunmap; write_json {design.relative_to(ROOT)}'
            with frontlog.open('w') as f:subprocess.run([frontend,'-Q','-T','-p',cmd],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=100)
            ports=json.loads(design.read_text())['modules']['normalization_proof']['ports']
            for port,width in [('sum3',70),('conversion_oracle',37)]:
                bits=ports[port]['bits']
                if len(bits)!=width or not all(type(b) is int for b in bits):raise RuntimeError('Lost symbolic port '+port)
            sat='sat -seq 2 -timeout 60 -set-assumes -prove-asserts' if negative else 'sat -seq 2 -tempinduct -maxsteps 5 -timeout 60 -set-assumes -prove-asserts -verify'
            with log.open('w') as f:
                try:
                    p=subprocess.run([backend,'-Q','-T','-p',f'read_json {design.relative_to(ROOT)}; '+sat],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=240,preexec_fn=limit)
                    text=log.read_text()
                    ok=(p.returncode==0 and ('model found for base case: FAIL!' in text or 'model found: FAIL!' in text)) if negative else (p.returncode==0 and 'Induction step proven: SUCCESS!' in text)
                except subprocess.TimeoutExpired:ok=False
            if negative and not ok:print(log.read_text()[-3500:],flush=True)
            results.append({'stages':stages,'negative_control':negative,'status':'pass' if ok else 'unclosed'})
            print(name,results[-1]['status'],flush=True)
    if any(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h for p,h in hashes.items()):raise RuntimeError('Sources changed')
    report={'status':'pass' if all(x['status']=='pass' for x in results) else 'unclosed',
            'scope':'Production magnitude/leading network, extra packet registers and output capture for arbitrary signed 70-bit sums and arbitrary converter results; scalar converter arithmetic is a separate obligation',
            'method':'Source-extracted production network, independent absolute value/linear leading reference, unbounded induction and inverted-magnitude counterexamples',
            'source_sha256':hashes,'harness_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'results':results}
    (ROOT/'reports/normalization-refinement.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['status']!='pass':raise SystemExit(1)
if __name__=='__main__':run()

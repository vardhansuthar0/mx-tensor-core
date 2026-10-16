"""Unbounded stream/accumulation refinement with abstract beat arithmetic.

Only the product and CSA cones are abstracted. Control, metadata, accumulators
and result packets are the production RTL. This lemma is not a full PE proof.
"""
import hashlib,json,os,pathlib,resource,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]

def run():
    frontend=shutil.which('yowasp-yosys');backend=os.environ.get('YOSYS_NATIVE') or shutil.which('yosys')
    if not frontend or not backend:raise SystemExit('Requires yowasp-yosys and native Yosys')
    rtl=(ROOT/'rtl/mx_pe.sv').read_text()
    abstract=rtl.replace('    input wire clk, rst, in_valid,','    input wire [69:0] proof_sum, input wire [3:0] proof_flags, input wire clk, rst, in_valid,')
    start=abstract.index('    always_comb begin\n        products_comb=')
    end=abstract.index('    always_ff @(posedge clk) begin\n        if(rst) begin v2',start)
    substitute="""logic [69:0] proof_sum1,proof_sum2;
logic [3:0] proof_flags1;
generate if(PIPE_STAGES==3) begin
always_comb begin proof_sum1=proof_sum;proof_flags1=proof_flags;end
end else begin
always_ff @(posedge clk) if(rst) begin proof_sum1<=0;proof_flags1<=0;end else if(advance)begin proof_sum1<=proof_sum;proof_flags1<=proof_flags;end
end endgenerate
always_ff @(posedge clk) if(rst)proof_sum2<=0;else if(advance)proof_sum2<=proof_sum1;
always_comb begin products_comb='0;{nan_comb,pos_comb,neg_comb,approx_comb}=proof_flags1;mag=0;clipped=0;mant_product=0;alignment=0;cut=0;end
"""
    abstract=abstract[:start]+substitute+abstract[end:]
    binding='    mx_csa #(.N(LANES),.W(70)) tree(products,lane_sum);'
    if abstract.count(binding)!=1:raise RuntimeError('CSA binding changed')
    abstract=abstract.replace(binding,'    assign lane_sum=proof_sum2;')
    work=ROOT/'build/streaming-formal';work.mkdir(parents=True,exist_ok=True)
    source=ROOT/'reports/streaming-abstract-pe.sv';source.write_text(abstract)
    paths=['rtl/mx_pe.sv','formal/streaming_pipeline.sv','scripts/streaming_formal.py']
    manifest={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    results=[]
    def limit():resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    for lanes in (8,16,32):
        for stages in (3,4,5):
            for negative in (False,True):
                name=f'l{lanes}_p{stages}'+('-negative' if negative else '')
                design=work/f'{name}.json';frontlog=ROOT/'reports'/f'streaming-{name}-frontend.log';log=ROOT/'reports'/f'streaming-{name}.log'
                cmd=f'read_slang -j 1 -DSYNTHESIS -GLANES={lanes} -GSTAGES={stages} -GNEGATIVE_CONTROL={int(negative)} --top streaming_proof {source.relative_to(ROOT)} formal/streaming_pipeline.sv; prep -top streaming_proof -flatten; chformal -lower; memory_map; opt; dffunmap; write_json {design.relative_to(ROOT)}'
                with frontlog.open('w') as f:subprocess.run([frontend,'-Q','-T','-p',cmd],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=100)
                module=json.loads(design.read_text())['modules']['streaming_proof']
                for port,width in [('term',70),('special',4)]:
                    bits=module['ports'][port]['bits']
                    if len(bits)!=width or not all(type(b) is int for b in bits):raise RuntimeError('Lost symbolic arithmetic input: '+port)
                sat='sat -seq 3 -timeout 30 -set-assumes -prove-asserts -verify' if negative else 'sat -seq 3 -tempinduct -maxsteps 6 -timeout 30 -set-assumes -prove-asserts -verify'
                with log.open('w') as f:
                    try:
                        p=subprocess.run([backend,'-Q','-T','-p',f'read_json {design.relative_to(ROOT)}; '+sat],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=210,preexec_fn=limit)
                        text=log.read_text()
                        passed=(p.returncode!=0 and ('model found for base case: FAIL!' in text or 'model found: FAIL!' in text)) if negative else (p.returncode==0 and 'Induction step proven: SUCCESS!' in text)
                    except subprocess.TimeoutExpired:passed=False
                results.append({'lanes':lanes,'stages':stages,'negative_control':negative,'status':'pass' if passed else 'unclosed','log':str(log.relative_to(ROOT))})
                print(name,results[-1]['status'],flush=True)
    if any(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha for p,sha in manifest.items()):raise SystemExit('Proof sources changed')
    report={'status':'pass' if all(r['status']=='pass' for r in results) else 'unclosed',
            'scope':'Abstract beat sums/flags; arbitrary streams, bubbles, stalls and resets after initial reset. Proves accumulation, first-beat metadata, pending-token conservation, result packets and valid latency. Product/CSA bindings and rounded output equivalence remain separate obligations.',
            'method':'unbounded induction with explicit symbolic input ports and inverted-valid counterexamples',
            'source_sha256':manifest,'abstraction_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'results':results}
    (ROOT/'reports/streaming-refinement.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['status']!='pass':raise SystemExit(1)

if __name__=='__main__':run()

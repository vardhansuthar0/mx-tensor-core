"""Check lane replication and real decode/product registers.

Independent one-lane contracts come from product_exhaustive.py. This lemma
checks their replication, special-flag OR, and temporal binding in real RTL.
It does not certify full PE arithmetic equivalence.
"""
import hashlib,json,pathlib,resource,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
def generate(rtl):
    dec=rtl[rtl.index('    typedef struct packed'):rtl.index('    function automatic integer leading70')]
    cone=rtl[rtl.index('    logic [LANES*70-1:0] products_comb'):rtl.index('    always_ff @(posedge clk) begin\n        if(rst) begin v2')]
    lane="""module lane_contract(input[7:0]a,b,input[2:0]fmt,input[5:0]grid,input[4:0]trunc,input poison,
output[69:0]p,output[3:0]f,output[13:0]qa,qb);
localparam LANES=1;
"""+dec+"""
dec_t da[LANES],db[LANES];meta_t m1;
always_comb begin da[0]=decode(a,fmt);db[0]=decode(b,fmt);m1='0;m1.grid=grid;m1.trunc=trunc;m1.poison=poison;end
"""+cone+"""
assign p=products_comb;assign f={nan_comb,pos_comb,neg_comb,approx_comb};assign qa=da[0];assign qb=db[0];
endmodule
"""
    body=rtl[rtl.index('    assign in_ready=advance && !rst;'):rtl.index('    wire [69:0] lane_sum;')]
    header="""module product_bindings #(parameter LANES=8,PIPE_STAGES=5,NEGATIVE=0)(
input clk,rst,advance,in_valid,input[LANES*8-1:0]in_a,in_b,
input[7:0]in_scale_a,in_scale_b,input[2:0]in_fmt,input in_bf16,input[4:0]in_trunc);
localparam BEATS=32/LANES;
wire in_ready;
"""
    checks="""
logic[LANES*8-1:0]rawa,rawb;
logic[2:0]rawfmt;
logic[5:0]rawgrid;
logic[4:0]rawtrunc;
logic rawpoison,gv1;
generate if(PIPE_STAGES==3)begin
always_comb begin rawa=in_a;rawb=in_b;rawfmt=active_fmt;rawgrid=input_meta.grid;rawtrunc=input_meta.trunc;rawpoison=input_meta.poison;gv1=in_valid;end
end else begin
always @(posedge clk)begin
if(rst)begin rawa<=0;rawb<=0;rawfmt<=0;rawgrid<=0;rawtrunc<=0;rawpoison<=0;gv1<=0;end
else if(advance)begin rawa<=in_a;rawb<=in_b;rawfmt<=active_fmt;rawgrid<=input_meta.grid;rawtrunc<=input_meta.trunc;rawpoison<=input_meta.poison;gv1<=in_valid;end
end
end endgenerate
wire[LANES*70-1:0]gold1;
wire[3:0]lane_flags[LANES];
wire[13:0]decoded_a[LANES],decoded_b[LANES];
for(genvar i=0;i<LANES;i++)begin: reference_lane
lane_contract one(rawa[8*i+:8],rawb[8*i+:8],rawfmt,rawgrid,rawtrunc,rawpoison,
gold1[70*i+:70],lane_flags[i],decoded_a[i],decoded_b[i]);
end
logic[3:0]gold_flags1;
always_comb begin gold_flags1=0;for(integer i=0;i<LANES;i++)gold_flags1=gold_flags1|lane_flags[i];end
reg[LANES*70-1:0]gold2;
reg[3:0]gold_flags2;
reg gv2,past_valid=0;
always @(posedge clk)begin
past_valid<=1;
if(rst)begin gold2<=0;gold_flags2<=0;gv2<=0;end
else if(advance)begin gold2<=gold1;gold_flags2<=gold_flags1;gv2<=gv1;end
end
always @* begin
if(!past_valid)assume(rst);
if(past_valid)begin
assert(v1==gv1);assert(v2==gv2);
if(v1)begin
assert(m1.grid==rawgrid);assert(m1.trunc==rawtrunc);assert(m1.poison==rawpoison);
for(integer i=0;i<LANES;i++)begin assert(da[i]==decoded_a[i]);assert(db[i]==decoded_b[i]);end
assert(products_comb==gold1);assert({nan_comb,pos_comb,neg_comb,approx_comb}==gold_flags1);
end
if(v2)begin
assert(products==(gold2^((LANES*70)'(NEGATIVE))));
assert({nan2,pos2,neg2,approx2}==gold_flags2);
end
end
end
endmodule
"""
    return lane+header+dec+body+checks
def run():
    frontend=shutil.which('yowasp-yosys');backend=shutil.which('yosys')
    if not frontend or not backend:raise SystemExit('Requires both Yosys frontends')
    paths=['rtl/mx_pe.sv','scripts/product_bindings.py']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    source=ROOT/'reports/product-bindings-harness.sv';source.write_text(generate((ROOT/'rtl/mx_pe.sv').read_text()))
    work=ROOT/'build/product-bindings';work.mkdir(parents=True,exist_ok=True)
    results=[]
    def limit():resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    for lanes in (8,16,32):
        for stages in (3,4,5):
            for negative in (False,True):
                name=f'l{lanes}_p{stages}'+('-negative' if negative else '')
                design=work/(name+'.json');frontlog=ROOT/'reports'/f'product-bindings-{name}-frontend.log';log=ROOT/'reports'/f'product-bindings-{name}.log'
                cmd=f'read_slang -j 1 -GLANES={lanes} -GPIPE_STAGES={stages} -GNEGATIVE={int(negative)} --top product_bindings {source.relative_to(ROOT)}; prep -top product_bindings -flatten; chformal -lower; memory_map; opt; dffunmap; write_json {design.relative_to(ROOT)}'
                with frontlog.open('w') as f:
                    p=subprocess.run([frontend,'-Q','-T','-p',cmd],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=150)
                if p.returncode:print(frontlog.read_text()[-4000:],flush=True);raise SystemExit(1)
                ports=json.loads(design.read_text())['modules']['product_bindings']['ports']
                for port in ('in_a','in_b'):
                    bits=ports[port]['bits']
                    if len(bits)!=lanes*8 or not all(type(b) is int for b in bits):raise RuntimeError('Lost symbolic port '+port)
                sat='sat -seq 4 -timeout 60 -set-assumes -prove-asserts' if negative else 'sat -seq 3 -tempinduct -maxsteps 6 -timeout 60 -set-assumes -prove-asserts -verify'
                with log.open('w') as f:
                    try:
                        p=subprocess.run([backend,'-Q','-T','-p',f'read_json {design.relative_to(ROOT)}; '+sat],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=300,preexec_fn=limit)
                        text=log.read_text()
                        ok=(p.returncode==0 and 'model found: FAIL!' in text) if negative else (p.returncode==0 and 'Induction step proven: SUCCESS!' in text)
                    except subprocess.TimeoutExpired:ok=False
                results.append({'lanes':lanes,'stages':stages,'negative_control':negative,'status':'pass' if ok else 'unclosed'})
                print(name,results[-1]['status'],flush=True)
                if not ok:print(log.read_text()[-2500:],flush=True)
    if any(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h for p,h in hashes.items()):raise RuntimeError('Sources changed')
    report={'status':'pass' if all(x['status']=='pass' for x in results) else 'unclosed',
            'scope':'Production decode registers, per-lane product replication, special-flag reduction and product registers; arbitrary raw inputs, metadata, bubbles, stalls and resets after initial reset; one-lane arithmetic contract remains separate',
            'source_sha256':hashes,'harness_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'results':results}
    (ROOT/'reports/product-bindings.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['status']!='pass':raise SystemExit(1)
if __name__=='__main__':run()

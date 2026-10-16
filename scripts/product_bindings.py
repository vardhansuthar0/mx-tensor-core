"""Prove lane replication and decode/product register bindings.

Combinational replication is checked on actual arbitrary decoded words.
Register proofs cut only the decode calls and product combinational cone at
explicit symbolic oracle ports; exact source anchors validate each cut.
The one-lane arithmetic contract is a separate exhaustive proof.
"""
import hashlib,json,pathlib,resource,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
def parts(rtl):
    dec=rtl[rtl.index('    typedef struct packed'):rtl.index('    function automatic integer leading70')]
    cone=rtl[rtl.index('    logic [LANES*70-1:0] products_comb'):rtl.index('    always_ff @(posedge clk) begin\n        if(rst) begin v2')]
    return dec,cone
def comb_source(rtl):
    dec,cone=parts(rtl)
    header="""module lane_contract #(parameter LANES=1)(
input[LANES*14-1:0]da_bits,db_bits,input[5:0]grid,input[4:0]trunc,input poison,
output[LANES*70-1:0]p,output[3:0]f);
"""
    assignments="""
dec_t da[LANES],db[LANES];meta_t m1;
always_comb begin
for(integer i=0;i<LANES;i++)begin da[i]=dec_t'(da_bits[14*i+:14]);db[i]=dec_t'(db_bits[14*i+:14]);end
m1='0;m1.grid=grid;m1.trunc=trunc;m1.poison=poison;
end
"""
    miter="""module replication_proof #(parameter LANES=8,NEGATIVE=0)(
input[LANES*14-1:0]da_bits,db_bits,input[5:0]grid,input[4:0]trunc,input poison);
wire[LANES*70-1:0]actual,expected;wire[3:0]actual_flags;
wire[3:0]f[LANES];logic[3:0]flags;
lane_contract #(.LANES(LANES)) dut(da_bits,db_bits,grid,trunc,poison,actual,actual_flags);
for(genvar i=0;i<LANES;i++)begin: lane
lane_contract one(da_bits[14*i+:14],db_bits[14*i+:14],grid,trunc,poison,expected[70*i+:70],f[i]);
end
always_comb begin flags=0;for(integer i=0;i<LANES;i++)flags=flags|f[i];end
always @*begin assert(actual==(expected^((LANES*70)'(NEGATIVE))));assert(actual_flags==flags);end
endmodule
"""
    return header+dec+assignments+cone+'\nassign p=products_comb;assign f={nan_comb,pos_comb,neg_comb,approx_comb};\nendmodule\n'+miter
def register_source(rtl):
    dec,_=parts(rtl)
    body=rtl[rtl.index('    assign in_ready=advance && !rst;'):rtl.index('    wire [69:0] lane_sum;')]
    for raw,oracle in [('in_a','oracle_da'),('in_b','oracle_db')]:
        call=f'decode({raw}[8*i+:8],active_fmt)'
        if body.count(call)!=2:raise RuntimeError('Decode argument/replication binding changed: '+call)
        body=body.replace(call,f"dec_t'({oracle}[14*i+:14])")
    begin=body.index('    always_comb begin\n        products_comb=')
    end=body.index('    always_ff @(posedge clk) begin\n        if(rst) begin v2',begin)
    body=body[:begin]+"""
always_comb begin
products_comb=oracle_products;
{nan_comb,pos_comb,neg_comb,approx_comb}=oracle_flags;
mag=0;clipped=0;mant_product=0;alignment=0;cut=0;
end
"""+body[end:]
    header="""module register_proof #(parameter LANES=8,PIPE_STAGES=5,NEGATIVE=0)(
input clk,rst,advance,in_valid,input[LANES*14-1:0]oracle_da,oracle_db,
input[LANES*70-1:0]oracle_products,input[3:0]oracle_flags,
input[7:0]in_scale_a,in_scale_b,input[2:0]in_fmt,input in_bf16,input[4:0]in_trunc);
localparam BEATS=32/LANES;wire in_ready;
"""
    checks="""
logic[LANES*14-1:0]gold_da,gold_db;
logic gv1;
generate if(PIPE_STAGES==3)begin
always_comb begin gold_da=oracle_da;gold_db=oracle_db;gv1=in_valid;end
end else begin
always @(posedge clk)if(rst)begin gold_da<=0;gold_db<=0;gv1<=0;end
else if(advance)begin gold_da<=oracle_da;gold_db<=oracle_db;gv1<=in_valid;end
end endgenerate
reg[LANES*70-1:0]gold_products;
reg[3:0]gold_flags;
reg gv2,past_valid=0;
always @(posedge clk)begin
past_valid<=1;
if(rst)begin gold_products<=0;gold_flags<=0;gv2<=0;end
else if(advance)begin gold_products<=oracle_products;gold_flags<=oracle_flags;gv2<=gv1;end
end
always @*begin
if(!past_valid)assume(rst);
if(past_valid)begin
assert(v1==gv1);assert(v2==gv2);
for(integer i=0;i<LANES;i++)begin
assert(da[i]==dec_t'(gold_da[14*i+:14]));assert(db[i]==dec_t'(gold_db[14*i+:14]));
end
assert(products==(gold_products^((LANES*70)'(NEGATIVE))));
assert({nan2,pos2,neg2,approx2}==gold_flags);
end
end
endmodule
"""
    return header+dec+body+checks
def run():
    frontend=shutil.which('yowasp-yosys');backend=shutil.which('yosys')
    if not frontend or not backend:raise SystemExit('Requires both Yosys frontends')
    paths=['rtl/mx_pe.sv','scripts/product_bindings.py']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    rtl=(ROOT/'rtl/mx_pe.sv').read_text()
    work=ROOT/'build/product-bindings';work.mkdir(parents=True,exist_ok=True)
    sources={}
    for kind,generator in [('replication',comb_source),('register',register_source)]:
        path=ROOT/'reports'/f'product-{kind}-harness.sv';path.write_text(generator(rtl));sources[kind]=path
    results=[]
    def limit():resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    for kind in ('replication','register'):
        for lanes in (8,16,32):
            for stages in ((None,) if kind=='replication' else (3,4,5)):
                for negative in (False,True):
                    name=f'{kind}-l{lanes}'+('' if stages is None else f'_p{stages}')+('-negative' if negative else '')
                    top=kind+'_proof';source=sources[kind]
                    design=work/(name+'.json');frontlog=ROOT/'reports'/f'product-bindings-{name}-frontend.log';log=ROOT/'reports'/f'product-bindings-{name}.log'
                    parameters=f'-GLANES={lanes} -GNEGATIVE={int(negative)}'+('' if stages is None else f' -GPIPE_STAGES={stages}')
                    cmd=f'read_slang -j 1 {parameters} --top {top} {source.relative_to(ROOT)}; prep -top {top} -flatten; chformal -lower; memory_map; opt; dffunmap; write_json {design.relative_to(ROOT)}'
                    with frontlog.open('w') as f:p=subprocess.run([frontend,'-Q','-T','-p',cmd],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=150)
                    if p.returncode:print(frontlog.read_text()[-4000:],flush=True);raise SystemExit(1)
                    ports=json.loads(design.read_text())['modules'][top]['ports']
                    required=[('da_bits',14*lanes),('db_bits',14*lanes)] if stages is None else [('oracle_da',14*lanes),('oracle_db',14*lanes),('oracle_products',70*lanes),('oracle_flags',4)]
                    for port,width in required:
                        bits=ports[port]['bits']
                        if len(bits)!=width or not all(type(b) is int for b in bits):raise RuntimeError('Lost symbolic port '+port)
                    if stages is None:sat='sat -timeout 60 -prove-asserts'+('' if negative else ' -verify')
                    elif negative:sat='sat -seq 2 -timeout 60 -set-assumes -prove-asserts'
                    else:sat='sat -seq 2 -tempinduct -maxsteps 5 -timeout 60 -set-assumes -prove-asserts -verify'
                    with log.open('w') as f:
                        try:
                            p=subprocess.run([backend,'-Q','-T','-p',f'read_json {design.relative_to(ROOT)}; '+sat],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=240,preexec_fn=limit)
                            text=log.read_text()
                            ok=(p.returncode==0 and 'model found: FAIL!' in text) if negative else (p.returncode==0 and ('Induction step proven: SUCCESS!' in text if stages is not None else 'no model found: SUCCESS!' in text))
                        except subprocess.TimeoutExpired:ok=False
                    results.append({'kind':kind,'lanes':lanes,'stages':stages,'negative_control':negative,'status':'pass' if ok else 'unclosed'})
                    print('::notice::'+name+' '+results[-1]['status'],flush=True)
                    if not ok:print(log.read_text()[-3500:],flush=True)
    if any(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h for p,h in hashes.items()):raise RuntimeError('Sources changed')
    report={'status':'pass' if all(x['status']=='pass' for x in results) else 'unclosed',
            'scope':'Production per-lane product replication/flag OR for arbitrary decoded words; real decode/product registers under explicit oracle cuts, arbitrary bubbles/stalls/resets after initial reset. Decode calls and cut arguments checked by exact production source anchors. One-lane arithmetic and control/metadata are separate obligations.',
            'source_sha256':hashes,'harness_sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in sources.items()},'results':results}
    (ROOT/'reports/product-bindings.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['status']!='pass':raise SystemExit(1)
if __name__=='__main__':run()

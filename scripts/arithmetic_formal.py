"""Optional bounded single-block arithmetic proof using a native SAT backend.
A pass covers only the named format/configuration and the stated control trace.
The inverted known-zero control must produce a counterexample, never a timeout.
"""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
def run():
    p=argparse.ArgumentParser();p.add_argument('--lanes',type=int,choices=(8,16,32),default=8);p.add_argument('--stages',type=int,choices=(3,4,5),default=5);p.add_argument('--format',type=int,choices=range(8),default=4);p.add_argument('--timeout',type=int,default=180);a=p.parse_args()
    frontend=shutil.which('yowasp-yosys') or str(pathlib.Path.home()/'.local/bin/yowasp-yosys')
    backend=os.environ.get('YOSYS_NATIVE') or shutil.which('yosys')
    if not backend:raise SystemExit('Set YOSYS_NATIVE to the native Yosys SAT backend; the full unroll exceeds the WASM backend memory budget')
    work=ROOT/'build/arithmetic';work.mkdir(parents=True,exist_ok=True)
    results=[]
    for negative in (True,False):
        name='negative' if negative else f'f{a.format}_l{a.lanes}_p{a.stages}'
        frontend_log=ROOT/'reports'/f'arithmetic-{name}-frontend.log';log=ROOT/'reports'/f'arithmetic-{name}.log'
        output=work/f'{name}.json'
        command=f'read_slang -j 1 -I formal -GLANES={a.lanes} -GSTAGES={a.stages} -GFMT={a.format} -GNEGATIVE_CONTROL={int(negative)} --top arithmetic_proof rtl/mx_csa.sv rtl/mx_pe.sv formal/arithmetic.sv; prep -top arithmetic_proof -flatten; chformal -lower; memory_map; opt; dffunmap; write_json build/arithmetic/{name}.json'
        with frontend_log.open('w') as f:
            subprocess.run([frontend,'-Q','-T','-p',command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
        design=json.loads(output.read_text())['modules']['arithmetic_proof']
        for port in ['symbolic_a','symbolic_b','symbolic_sa','symbolic_sb','symbolic_bf','symbolic_trunc']:
            bits=design['ports'][port]['bits']
            if not all(type(bit) is int for bit in bits):raise RuntimeError('Symbolic port contains constants/X: '+port)
        command=f'read_json build/arithmetic/{name}.json; sat -seq {32//a.lanes+a.stages+1} -set-assumes -prove-asserts -verify -timeout {a.timeout}'
        with log.open('w') as f:
            result=subprocess.run([backend,'-Q','-T','-p',command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=a.timeout+180)
        text=log.read_text();success=result.returncode==0 and 'no model found: SUCCESS!' in text
        rejected=result.returncode!=0 and 'model found: FAIL!' in text
        results.append({'name':name,'status':('pass' if rejected else 'invalid') if negative else ('pass' if success else 'unclosed'),'log':str(log.relative_to(ROOT))})
        if negative and not rejected:break
    report={'status':'pass' if len(results)==2 and all(r['status']=='pass' for r in results) else 'unclosed',
            'scope':'Bounded single 32-element block after reset, contiguous valid beats, out_ready=1; no arbitrary-stream or stalled/reset-interleaved arithmetic claim',
            'configuration':{'lanes':a.lanes,'stages':a.stages,'format_id':a.format},'symbolic':'All 32 A/B element bytes, both scales, truncation and output format, captured as symbolic input ports at reset',
            'negative_control':'Inverted result on known-zero block must fail at the output assertion',
            'results':results,'rtl_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'rtl').glob('*.sv')}}
    (ROOT/'reports/arithmetic-bounded.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if report['status']!='pass':raise SystemExit(1)
if __name__=='__main__':run()

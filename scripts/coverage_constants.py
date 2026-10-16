"""Prove candidate constant toggles without changing raw coverage counts.

Candidates come from unhit toggle counters, never from a blanket source waiver.
The proof has arbitrary input streams, bubbles, backpressure and resets, with
an initial reset. A failed proof leaves every candidate unclassified.
"""
import hashlib,json,os,pathlib,re,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]

def run():
    coverage=json.loads((ROOT/'reports/code-coverage.json').read_text())
    for path,sha in coverage['rtl_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise SystemExit('Stale coverage input: '+path)
    proof_paths=['rtl/mx_pe.sv','rtl/mx_csa.sv','scripts/coverage_constants.py','reports/code-coverage.json']
    proof_sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in proof_paths}
    yosys=shutil.which('yowasp-yosys')
    if not yosys:raise SystemExit('yowasp-yosys is required')
    work=ROOT/'reports/coverage-constant-harnesses';work.mkdir(parents=True,exist_ok=True)
    backend=os.environ.get('YOSYS_NATIVE') or shutil.which('yosys')
    results=[]
    for config in coverage['configurations']:
        lanes,stages=config['lanes'],config['stages']
        name=f'l{lanes}_p{stages}'
        candidates=[];signals=set();directions={}
        for counter in config['uncovered']:
            if counter['type']!='toggle':continue
            signal=counter['instance'].removeprefix('mx_pe')+'.'+counter['detail'].split(':')[0]
            # Only exact simulator-derived SV identifiers/bit selects are used.
            if not re.fullmatch(r'(?:\.[A-Za-z_][A-Za-z_0-9]*(?:\[\d+\])?)+',signal):
                raise RuntimeError('Unsupported coverage signal: '+signal)
            candidates.append(counter);signals.add('dut'+signal)
            directions.setdefault('dut'+signal,set()).add(counter['detail'].split(':')[1])
        header=f'''module coverage_constants(input clk,rst,in_valid,out_ready,
input [{lanes*8-1}:0] in_a,in_b,input [7:0] sa,sb,input [2:0] fmt,input bf,input [4:0] trunc);
wire ir,ov;wire [31:0] data;wire [4:0] flags;
mx_pe #(.LANES({lanes}),.PIPE_STAGES({stages})) dut(clk,rst,in_valid,ir,in_a,in_b,sa,sb,fmt,bf,trunc,ov,out_ready,data,flags);
reg past_valid=0;
always @(posedge clk) past_valid<=1;
always @* begin
if(!past_valid) assume(rst);
if(past_valid) begin
'''
        values={s:int(directions[s]=={'1->0'}) for s in signals}
        checks='\n'.join(f'assert({s}=={values[s]});' for s in sorted(signals))
        if lanes==32:
            checks+='\nassert(!dut.v1 || dut.m1.last);\nassert(!dut.v2 || dut.m2.last);'
        source=work/f'{name}.sv';source.write_text(header+checks+'\nend\nend\nendmodule\n')
        log=ROOT/'reports'/f'coverage-constants-{name}.log'
        command=f'read_slang -j 1 -DSYNTHESIS --top coverage_constants rtl/mx_csa.sv rtl/mx_pe.sv {source.relative_to(ROOT)}; prep -top coverage_constants -flatten; chformal -lower; memory_map; opt; dffunmap; '
        sat='sat -seq 3 -tempinduct -maxsteps 6 -timeout 20 -set-assumes -prove-asserts -verify'
        solver=yosys
        if backend:
            design=ROOT/'build/coverage-constants'/f'{name}.json';design.parent.mkdir(parents=True,exist_ok=True)
            frontend_log=ROOT/'reports'/f'coverage-constants-{name}-frontend.log'
            with frontend_log.open('w') as f:
                subprocess.run([yosys,'-Q','-T','-p',command+f'write_json {design.relative_to(ROOT)}'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=100)
            positive_command=f'read_json {design.relative_to(ROOT)}; '+sat
            solver=backend
        else:positive_command=command+sat
        with log.open('w') as f:
            try:
                result=subprocess.run([solver,'-Q','-T','-p',positive_command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=160)
                passed=result.returncode==0 and 'Induction step proven: SUCCESS!' in log.read_text()
            except subprocess.TimeoutExpired:passed=False
        negative_passed=False
        if passed and signals:
            negative=work/f'{name}-negative.sv'
            signal=sorted(signals)[0]
            negative.write_text(header+f'assert({signal}=={1-values[signal]});\nend\nend\nendmodule\n')
            negative_log=ROOT/'reports'/f'coverage-constants-{name}-negative.log'
            negative_command=(command+sat).replace(str(source.relative_to(ROOT)),str(negative.relative_to(ROOT))).replace('-tempinduct -maxsteps 6 ','')
            with negative_log.open('w') as f:
                try:
                    bad=subprocess.run([yosys,'-Q','-T','-p',negative_command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=60)
                    negative_passed=bad.returncode!=0 and 'model found: FAIL!' in negative_log.read_text()
                except subprocess.TimeoutExpired:negative_passed=False
        passed=passed and negative_passed
        results.append({'lanes':lanes,'stages':stages,'status':'pass' if passed else 'unclosed',
                        'inverted_property_counterexample':negative_passed,
                        'candidate_counters':candidates,'signals':values,
                        'log':str(log.relative_to(ROOT)),
                        'harness':str(source.relative_to(ROOT)),
                        'harness_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
        print(name,results[-1]['status'],len(candidates),flush=True)
    if any(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha for p,sha in proof_sources.items()):raise SystemExit('Proof inputs changed during execution')
    report={'status':'pass' if all(r['status']=='pass' for r in results) else 'unclosed',
            'scope':'Constant toggles only; unbounded induction after initial reset, arbitrary input streams/backpressure/resets. Raw coverage unchanged; branch/expression gaps not waived.',
            'rtl_sha256':coverage['rtl_sha256'],'source_sha256':proof_sources,'configurations':results}
    (ROOT/'reports/coverage-constants.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['status']!='pass':raise SystemExit(1)

if __name__=='__main__':run()

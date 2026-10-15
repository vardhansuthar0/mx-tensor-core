"""Prove candidate constant-zero toggles without changing raw coverage counts.

Candidates come from unhit toggle counters, never from a blanket source waiver.
The proof has arbitrary input streams, bubbles, backpressure and resets, with
an initial reset. A failed proof leaves every candidate unclassified.
"""
import hashlib,json,pathlib,re,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]

def run():
    coverage=json.loads((ROOT/'reports/code-coverage.json').read_text())
    yosys=shutil.which('yowasp-yosys')
    if not yosys:raise SystemExit('yowasp-yosys is required')
    work=ROOT/'build/coverage-constants';work.mkdir(parents=True,exist_ok=True)
    results=[]
    for config in coverage['configurations']:
        lanes,stages=config['lanes'],config['stages']
        name=f'l{lanes}_p{stages}'
        candidates=[];signals=set()
        for counter in config['uncovered']:
            if counter['type']!='toggle':continue
            signal=counter['instance'].removeprefix('mx_pe')+'.'+counter['detail'].split(':')[0]
            # Only exact simulator-derived SV identifiers/bit selects are used.
            if not re.fullmatch(r'(?:\.[A-Za-z_][A-Za-z_0-9]*(?:\[\d+\])?)+',signal):
                raise RuntimeError('Unsupported coverage signal: '+signal)
            candidates.append(counter);signals.add('dut'+signal)
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
        checks='\n'.join(f'assert({s}==0);' for s in sorted(signals))
        source=work/f'{name}.sv';source.write_text(header+checks+'\nend\nend\nendmodule\n')
        log=ROOT/'reports'/f'coverage-constants-{name}.log'
        command=f'read_slang -j 1 -DSYNTHESIS --top coverage_constants rtl/mx_csa.sv rtl/mx_pe.sv {source.relative_to(ROOT)}; prep -top coverage_constants -flatten; chformal -lower; memory_map; opt; dffunmap; sat -seq 3 -tempinduct -maxsteps 6 -timeout 20 -set-assumes -prove-asserts -verify'
        with log.open('w') as f:
            try:
                result=subprocess.run([yosys,'-Q','-T','-p',command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=160)
                passed=result.returncode==0 and 'Induction step proven: SUCCESS!' in log.read_text()
            except subprocess.TimeoutExpired:passed=False
        negative_passed=False
        if passed and signals:
            negative=work/f'{name}-negative.sv'
            negative.write_text(header+f'assert({sorted(signals)[0]}==1);\nend\nend\nendmodule\n')
            negative_log=ROOT/'reports'/f'coverage-constants-{name}-negative.log'
            negative_command=command.replace(str(source.relative_to(ROOT)),str(negative.relative_to(ROOT))).replace('-tempinduct -maxsteps 6 ','')
            with negative_log.open('w') as f:
                try:
                    bad=subprocess.run([yosys,'-Q','-T','-p',negative_command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=60)
                    negative_passed=bad.returncode!=0 and 'model found: FAIL!' in negative_log.read_text()
                except subprocess.TimeoutExpired:negative_passed=False
        passed=passed and negative_passed
        results.append({'lanes':lanes,'stages':stages,'status':'pass' if passed else 'unclosed',
                        'inverted_property_counterexample':negative_passed,
                        'candidate_counters':candidates,'signals':sorted(signals),
                        'log':str(log.relative_to(ROOT)),
                        'harness':str(source.relative_to(ROOT)),
                        'harness_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
        print(name,results[-1]['status'],len(candidates),flush=True)
    report={'status':'pass' if all(r['status']=='pass' for r in results) else 'unclosed',
            'scope':'Constant-zero toggles only; unbounded induction after initial reset, arbitrary input streams/backpressure/resets. Raw coverage unchanged; branch/expression gaps not waived.',
            'rtl_sha256':coverage['rtl_sha256'],'configurations':results}
    (ROOT/'reports/coverage-constants.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['status']!='pass':raise SystemExit(1)

if __name__=='__main__':run()

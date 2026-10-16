"""Measure Verilator RTL instrumentation; preserve every uncovered counter.
These are tool counters, not functional bins. No inferred exclusions/waivers.
"""
import argparse, hashlib, json, pathlib, subprocess, sys
from collections import defaultdict
ROOT=pathlib.Path(__file__).resolve().parents[1]

def summarize(path):
    metrics=defaultdict(lambda:{'hit':0,'total':0})
    uncovered=[]
    for line in path.read_text().splitlines()[1:]:
        if not line.startswith("C '"):continue
        key,count=line[3:].rsplit("' ",1)
        fields=dict(part.split('\x02',1) for part in key.split('\x01')[1:])
        source=pathlib.Path(fields['f'])
        if source.parent != ROOT/'rtl':continue
        kind=fields['t'];hit=int(count)>0
        metrics[kind]['total']+=1;metrics[kind]['hit']+=hit
        if not hit:
            uncovered.append({'file':str(source.relative_to(ROOT)),'line':int(fields['l']),
                              'type':kind,'detail':fields.get('o',''),'instance':fields.get('h','')})
    if not metrics:raise RuntimeError('No RTL coverage counters found')
    for m in metrics.values():m['percent']=100*m['hit']/m['total']
    return dict(metrics),uncovered

def run():
    p=argparse.ArgumentParser();p.add_argument('--collect-only',action='store_true');a=p.parse_args()
    reports=[]
    for lanes in (8,16,32):
        for stages in (3,4,5):
            label=f'coverage_l{lanes}_p{stages}'
            if not a.collect_only:
                with (ROOT/'reports'/f'{label}.log').open('w') as f:
                    subprocess.run([sys.executable,str(ROOT/'scripts/run_sim.py'),'--lanes',str(lanes),'--stages',str(stages),'--coverage','--label',label],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
            metrics,uncovered=summarize(ROOT/'build'/label/'coverage.dat')
            passed=json.loads((ROOT/'reports'/f'{label}.json').read_text())['status']=='pass'
            if not passed:raise RuntimeError('Coverage run did not pass scoreboard')
            report={'lanes':lanes,'stages':stages,'metrics':metrics,'uncovered':uncovered}
            reports.append(report)
    result={'status':'measured','closure_status':'incomplete' if any(x['uncovered'] for x in reports) else 'complete',
            'scope':'PE and CSA only; nine configurations. Verilator instrumented line/branch/expression/toggle counters. Toggle directions counted separately. No exclusions or waivers. Array/APB coverage not measured.',
            'rtl_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'rtl').glob('*.sv'))},'configurations':reports}
    (ROOT/'reports/code-coverage.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in r.items() if k!='uncovered'} for r in reports],indent=2))
if __name__=='__main__':run()

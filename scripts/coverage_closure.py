"""Audit raw PE counters and narrowly justified unreachable points.

Raw hits/totals are never rewritten. Every excluded point must match a proven
constant, an elaboration constant, or the separately proved 16-lane branch.
Unknown points and missing/stale/failed proofs keep closure blocked.
"""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]

def evaluate(root):
    failures=[];configs=[]
    def read(name):
        try:return json.loads((root/'reports'/name).read_text())
        except (OSError,ValueError):return {}
    def fresh(manifest):
        return bool(manifest) and all((root/p).is_file() and hashlib.sha256((root/p).read_bytes()).hexdigest()==sha for p,sha in manifest.items())
    raw=read('code-coverage.json');constants=read('coverage-constants.json');paths=read('coverage-paths.json')
    required_constant_sources={'rtl/mx_pe.sv','rtl/mx_csa.sv','scripts/coverage_constants.py','reports/code-coverage.json'}
    required_path_sources={'rtl/mx_pe.sv','rtl/mx_csa.sv','scripts/coverage_paths.py'}
    constant_ok=constants.get('status')=='pass' and required_constant_sources<=constants.get('source_sha256',{}).keys() and fresh(constants.get('source_sha256',{}))
    path_ok=paths.get('status')=='pass' and required_path_sources<=paths.get('source_sha256',{}).keys() and fresh(paths.get('source_sha256',{})) and {
        (r.get('stages'),r.get('negative_control')) for r in paths.get('results',[]) if r.get('status')=='pass'
    }=={(s,n) for s in (3,4,5) for n in (False,True)}
    def identity(c):return tuple(c.get(k) for k in ('file','line','type','detail','instance'))
    try:lines=(root/'rtl/mx_pe.sv').read_text().splitlines()
    except OSError:lines=[]
    for c in raw.get('configurations',[]):
        lanes,stages=c.get('lanes'),c.get('stages');exclusions=[]
        proof=next((p for p in constants.get('configurations',[]) if (p.get('lanes'),p.get('stages'))==(lanes,stages)),{})
        valid_constants=constant_ok and proof.get('status')=='pass' and proof.get('inverted_property_counterexample') is True
        constant_ids={identity(p) for p in proof.get('candidate_counters',[])} if valid_constants else set()
        zero_beat=valid_constants and all(proof.get('signals',{}).get(f'dut.beat[{b}]')==0 for b in range(3))
        helpers=False
        if valid_constants:
            h=root/proof.get('harness','')
            if h.is_file() and hashlib.sha256(h.read_bytes()).hexdigest()==proof.get('harness_sha256'):
                helpers='assert(!dut.v2 || dut.m2.last);' in h.read_text()
        for counter in c.get('uncovered',[]):
            kind=counter.get('type');detail=counter.get('detail');reason=None
            index=counter.get('line',0)-1
            line=lines[index] if counter.get('file')=='rtl/mx_pe.sv' and 0<=index<len(lines) else ''
            if kind=='toggle' and identity(counter) in constant_ids:
                reason='Unbounded constant-state induction with counterexample negative control'
            elif kind=='expr' and 'assert(LANES==8 || LANES==16 || LANES==32)' in line:
                false_terms={f"((LANES == 32'sh{n:x})==1) => 1" for n in (8,16,32) if n!=lanes}
                false_terms.add("((LANES == 32'sh8)==0 && (LANES == 32'sh10)==0 && (LANES == 32'sh20)==0) => 0")
                if lanes in (8,16,32) and detail in false_terms:reason='Elaboration parameter makes this assertion outcome impossible'
            elif lanes==16 and path_ok and 'run_nan<=run_nan|nan2;' in line and kind=='expr':
                if detail in {f'(run_{flag}==1) => 1' for flag in ('nan','pos','neg','approx')}:
                    reason='Unbounded phase/flag induction: first accumulation beat starts with zero run flags'
            elif lanes==32 and zero_beat:
                if 'active_fmt=(beat==0)?' in line and (kind,detail) in {('branch','cond_else'),('expr',"((beat == 32'sh0)==0) => 0")}:
                    reason='Beat is always zero in the one-beat configuration'
                elif 'if(beat==0)' in line and (kind,detail)==('branch','else'):
                    reason='Beat is always zero in the one-beat configuration'
                elif "if(int'(beat)==BEATS-1)" in line and (kind,detail)==('branch','else'):
                    reason='One-beat configuration: beat zero is always the last beat'
                elif helpers and 'if(m2.last)' in line and (kind,detail)==('branch','else'):
                    reason='Proved invariant: every valid product beat is last'
                elif 'nan3<=run_nan|nan2;' in line and kind=='expr':
                    allowed={f'(run_{flag}==1) => 1' for flag in ('nan','pos','neg','approx') if proof.get('signals',{}).get('dut.run_'+flag)==0}
                    if detail in allowed:reason='Run flags are proved constant zero in the one-beat configuration'
                elif helpers and 'run_nan<=run_nan|nan2;' in line and kind=='expr':
                    allowed=set()
                    for flag in ('nan','pos','neg','approx'):
                        allowed.update([f'({flag}2==1) => 1',f'(run_{flag}==1) => 1',f'(run_{flag}==0 && {flag}2==0) => 0'])
                    if detail in allowed:reason='Non-last accumulation branch is proved unreachable'
            if reason:exclusions.append(dict(counter,reason=reason))
            else:failures.append(f'l{lanes}/p{stages}: unjustified uncovered point {identity(counter)}')
        metrics={}
        for kind in ('line','branch','expr','toggle'):
            m=c.get('metrics',{}).get(kind,{})
            hit,total=m.get('hit',-1),m.get('total',0)
            unhit=sum(x.get('type')==kind for x in c.get('uncovered',[]))
            excluded=sum(x.get('type')==kind for x in exclusions)
            if type(hit) is not int or type(total) is not int or not (0<=hit<=total) or total==0 or total-hit!=unhit:
                failures.append(f'l{lanes}/p{stages}: inconsistent raw {kind} counters')
            metrics[kind]={'raw_hit':hit,'raw_total':total,'proved_unreachable':excluded,'reachable_total':total-excluded}
        configs.append({'lanes':lanes,'stages':stages,'metrics':metrics,'exclusions':exclusions})
    if {(c['lanes'],c['stages']) for c in configs}!={(l,p) for l in (8,16,32) for p in (3,4,5)}:failures.append('Missing PE configurations')
    return {'status':'blocked' if failures else 'pass','scope':'Reachable PE/CSA line, branch, expression and toggle counters, nine configurations; raw counts retained. Array/APB coverage not included.',
            'failures':failures,'configurations':configs}

if __name__=='__main__':
    result=evaluate(ROOT)
    (ROOT/'reports/coverage-closure.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='configurations'},indent=2))
    raise SystemExit(result['status']!='pass')

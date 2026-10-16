"""Fail closed on absent, stale, non-finite, or failing signoff evidence."""
import argparse, hashlib, json, math, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
CORNERS=[f'{rc}_{cell}' for rc in ('nom','min','max') for cell in ('tt_025C_1v80','ss_100C_1v60','ff_n40C_1v95')]

def evaluate(root, physical_only=False):
    failures=[]
    def read(name):
        try:return json.loads((root/'reports'/name).read_text())
        except (OSError,ValueError):failures.append(f'Missing/invalid evidence: {name}');return {}
    def require(ok,label):
        if not ok:failures.append(label)
    def numeric(mapping,key,test,label=None):
        value=mapping.get(key)
        require(type(value) in (int,float) and math.isfinite(value) and test(value),label or f'{key}: required passing finite metric; got {value!r}')
    def fresh(manifest,label):
        require(bool(manifest),f'{label}: missing source hashes')
        for path,sha in manifest.items():
            p=root/path
            require(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==sha,f'{label}: stale source {path}')
    physical=read('physical.json')
    require(physical.get('flow_exit_code')==0,'Physical flow did not finish successfully')
    numeric(physical,'requested_clock_ns',lambda v:v==50,'Physical target must remain 50 ns / 20 MHz')
    manifest=physical.get('source_sha256',{})
    required={'rtl/mx_pe.sv','rtl/mx_csa.sv','physical/mx_pe_sky130.sv','physical/config.json','physical/generated.v'}
    require(required<=manifest.keys(),'Physical provenance does not cover all implementation inputs')
    fresh(manifest,'Physical')
    timing=physical.get('timing',{});electrical=physical.get('electrical',{})
    for corner in CORNERS:
        for check in ('setup','hold'):
            numeric(timing,f'timing__{check}__ws__corner:{corner}',lambda v:v>=0)
            numeric(timing,f'timing__{check}__tns__corner:{corner}',lambda v:v==0)
            numeric(timing,f'timing__{check}_vio__count__corner:{corner}',lambda v:v==0)
        for check in ('slew','cap'):
            numeric(electrical,f'design__max_{check}_violation__count__corner:{corner}',lambda v:v==0)
        numeric(timing,f'timing__unannotated_net_filtered__count__corner:{corner}',lambda v:v==0)
    checks=physical.get('drc_lvs',{})
    for key in ('antenna__violating__nets','antenna__violating__pins','route__drc_errors',
                'magic__drc_error__count','klayout__drc_error__count','design__lvs_error__count','design__xor_difference__count'):
        numeric(checks,key,lambda v:v==0)
    power=physical.get('power') or {}
    numeric(power,'blocks_checked',lambda v:v>0,'No checked routed gate simulation')
    require(bool(power.get('netlist_sha256')) and power.get('netlist_sha256')==physical.get('netlist_sha256'),'Gate simulation/power netlist does not match physical netlist')
    if physical_only:return failures
    verification=read('status.json')
    require(verification.get('verification_status')=='pass','Verification regression did not pass')
    source_manifest=read('source-sha256.json');fresh(source_manifest,'Verification')
    require({'rtl/mx_pe.sv','rtl/mx_csa.sv','rtl/mx_engine.sv'}<=source_manifest.keys(),'Verification source manifest incomplete')
    uvm=read('native-uvm.json');require(uvm.get('status')=='pass' and uvm.get('blocks_checked',0)>0,'Native SV UVM regression not passed')
    fresh(uvm.get('rtl_sha256',{}),'Native UVM')
    arithmetic=read('arithmetic-equivalence.json')
    require(arithmetic.get('status')=='pass' and arithmetic.get('scope')=='full_pe_independent_spec','Full PE arithmetic equivalence against independent specification remains open')
    fresh(arithmetic.get('rtl_sha256',{}),'Arithmetic proof')
    coverage=read('code-coverage.json');fresh(coverage.get('rtl_sha256',{}),'Code coverage')
    raw_complete=coverage.get('closure_status')=='complete'
    configs=coverage.get('configurations',[])
    require({(r.get('lanes'),r.get('stages')) for r in configs}=={(l,p) for l in (8,16,32) for p in (3,4,5)},'Coverage missing PE configurations')
    for r in configs:
        for kind in ('line','branch','expr','toggle'):
            metric=r.get('metrics',{}).get(kind,{})
            if not (metric.get('total',0)>0 and metric.get('hit')==metric.get('total')):raw_complete=False
    if not raw_complete:
        try:from coverage_closure import evaluate as evaluate_coverage
        except ModuleNotFoundError:from scripts.coverage_closure import evaluate as evaluate_coverage
        closure=evaluate_coverage(root)
        require(closure['status']=='pass','Code/toggle coverage closure remains open: '+str(closure['failures'][:3]))
    return failures

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=ROOT);p.add_argument('--physical-only',action='store_true');a=p.parse_args()
    failures=evaluate(a.root,a.physical_only)
    result={'status':'blocked' if failures else 'pass','scope':'one_pe_physical' if a.physical_only else 'full_signoff','target_clock_ns':50,'failures':failures}
    (a.root/'reports'/('physical-signoff.json' if a.physical_only else 'signoff.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return bool(failures)
if __name__=='__main__':sys.exit(main())

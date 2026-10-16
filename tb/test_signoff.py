"""Signoff must reject realistic false-positive and stale-evidence cases."""
import hashlib, importlib.util, json, math
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('signoff_check',Path(__file__).parents[1]/'scripts/signoff_check.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

def write(root,name,data):
    (root/'reports'/name).write_text(json.dumps(data))

@pytest.fixture
def passing(tmp_path):
    (tmp_path/'reports').mkdir()
    paths=['rtl/mx_pe.sv','rtl/mx_csa.sv','rtl/mx_engine.sv','physical/mx_pe_sky130.sv','physical/config.json','physical/generated.v']
    manifest={}
    for path in paths:
        p=tmp_path/path;p.parent.mkdir(exist_ok=True);p.write_text(path)
        manifest[path]=hashlib.sha256(p.read_bytes()).hexdigest()
    timing={};electrical={}
    for corner in gate.CORNERS:
        for kind in ('setup','hold'):
            timing[f'timing__{kind}__ws__corner:{corner}']=0.1
            timing[f'timing__{kind}__tns__corner:{corner}']=0
            timing[f'timing__{kind}_vio__count__corner:{corner}']=0
        timing[f'timing__unannotated_net_filtered__count__corner:{corner}']=0
        for kind in ('slew','cap'):electrical[f'design__max_{kind}_violation__count__corner:{corner}']=0
    physical={'requested_clock_ns':50,'flow_exit_code':0,'source_sha256':manifest,'timing':timing,'electrical':electrical,
              'drc_lvs':dict.fromkeys(['antenna__violating__nets','antenna__violating__pins','route__drc_errors','magic__drc_error__count','klayout__drc_error__count','design__lvs_error__count','design__xor_difference__count'],0),
              'netlist_sha256':'abc','power':{'blocks_checked':200,'netlist_sha256':'abc'}}
    write(tmp_path,'physical.json',physical)
    write(tmp_path,'status.json',{'verification_status':'pass'})
    write(tmp_path,'source-sha256.json',manifest)
    write(tmp_path,'native-uvm.json',{'status':'pass','blocks_checked':200,'rtl_sha256':manifest})
    arithmetic_manifest=dict(manifest);components={}
    for path in gate.ARITHMETIC_PRODUCERS+['reports/'+name for name in gate.ARITHMETIC_COMPONENTS]:
        p=tmp_path/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(path)
        arithmetic_manifest[path]=hashlib.sha256(p.read_bytes()).hexdigest()
        if path.startswith('reports/'):components[path]=arithmetic_manifest[path]
    write(tmp_path,'arithmetic-equivalence.json',{'status':'pass','scope':'full_pe_independent_spec','rtl_sha256':arithmetic_manifest,
          'configurations':[{'lanes':l,'stages':p} for l in (8,16,32) for p in (3,4,5)],
          'certificate_negative_controls_passed':6,'component_evidence_sha256':components})
    write(tmp_path,'code-coverage.json',{'closure_status':'complete','rtl_sha256':manifest,'configurations':[{'lanes':l,'stages':p,'metrics':{k:{'hit':3,'total':3} for k in ('line','branch','expr','toggle')}} for l in (8,16,32) for p in (3,4,5)]})
    return tmp_path

def test_accept_complete_evidence(passing):assert gate.evaluate(passing)==[]

@pytest.mark.parametrize('failure',['timing','slew','antenna','klayout','clock','nan','missing_corner','flow','gate_hash'])
def test_reject_physical_false_passes(passing,failure):
    p=passing/'reports/physical.json';d=json.loads(p.read_text())
    c='max_ss_100C_1v60'
    if failure=='timing':d['timing'][f'timing__setup__ws__corner:{c}']=-0.01
    if failure=='slew':d['electrical'][f'design__max_slew_violation__count__corner:{c}']=1
    if failure=='antenna':d['drc_lvs']['antenna__violating__nets']=1
    if failure=='klayout':del d['drc_lvs']['klayout__drc_error__count']
    if failure=='clock':d['requested_clock_ns']=60
    if failure=='nan':d['timing'][f'timing__hold__ws__corner:{c}']=math.nan
    if failure=='missing_corner':del d['timing'][f'timing__setup__ws__corner:{c}']
    if failure=='flow':d['flow_exit_code']=1
    if failure=='gate_hash':d['power']['netlist_sha256']='stale'
    write(passing,'physical.json',d)
    assert gate.evaluate(passing)

def test_reject_stale_source(passing):
    (passing/'rtl/mx_pe.sv').write_text('modified')
    assert any('stale source' in x for x in gate.evaluate(passing))

@pytest.mark.parametrize('name',['native-uvm.json','arithmetic-equivalence.json','code-coverage.json'])
def test_reject_missing_verification(passing,name):
    (passing/'reports'/name).unlink()
    assert gate.evaluate(passing)

def test_reject_coverage_claim_without_hits(passing):
    p=passing/'reports/code-coverage.json';d=json.loads(p.read_text());d['configurations'][0]['metrics']['toggle']['hit']=2
    write(passing,'code-coverage.json',d)
    assert gate.evaluate(passing)

def test_reject_exclusion_without_proof(passing):
    p=passing/'reports/code-coverage.json';d=json.loads(p.read_text())
    d['closure_status']='complete_with_exclusions'
    d['configurations'][0]['metrics']['toggle']['hit']=2
    d['configurations'][0]['uncovered']=[{'file':'rtl/mx_pe.sv','line':1,'type':'toggle','detail':'beat[2]:0->1','instance':'mx_pe'}]
    write(passing,'code-coverage.json',d)
    write(passing,'coverage-constants.json',{'status':'pass','configurations':[]})
    assert any('coverage closure remains open' in x for x in gate.evaluate(passing))


def test_physical_scope_keeps_full_signoff_blocked(passing):
    (passing/'reports/arithmetic-equivalence.json').unlink()
    assert gate.evaluate(passing,physical_only=True)==[]
    assert gate.evaluate(passing)

def test_physical_scope_rejects_violations(passing):
    p=passing/'reports/physical.json';d=json.loads(p.read_text())
    d['drc_lvs']['antenna__violating__pins']=1
    write(passing,'physical.json',d)
    assert gate.evaluate(passing,physical_only=True)

@pytest.mark.parametrize('failure',['configuration','negative_controls','component_missing','producer_missing','digest_unbound','stale_component'])
def test_arithmetic_certificate_fail_closed(passing,failure):
    p=passing/'reports/arithmetic-equivalence.json';d=json.loads(p.read_text())
    component='reports/'+gate.ARITHMETIC_COMPONENTS[0]
    if failure=='configuration':d['configurations'].pop()
    if failure=='negative_controls':d['certificate_negative_controls_passed']=5
    if failure=='component_missing':del d['component_evidence_sha256'][component]
    if failure=='producer_missing':del d['rtl_sha256'][gate.ARITHMETIC_PRODUCERS[0]]
    if failure=='digest_unbound':d['component_evidence_sha256'][component]='0'*64
    if failure=='stale_component':(passing/component).write_text('changed proof result')
    write(passing,'arithmetic-equivalence.json',d)
    assert gate.evaluate(passing)

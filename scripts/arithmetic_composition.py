"""Assemble a fail-closed compositional PE arithmetic certificate.

Run only after all component campaigns finish. This script does not prove a
missing obligation: missing, failed, stale or incomplete components block it.
See docs/arithmetic-composition.md for the assume/guarantee argument.
"""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def assemble(root=ROOT):
    source={};evidence={};components={}
    def require(ok,message):
        if not ok:raise ValueError(message)
    def digest(path):return hashlib.sha256((root/path).read_bytes()).hexdigest()
    def read(name):
        path='reports/'+name
        data=json.loads((root/path).read_text())
        require(data.get('status')=='pass',name+' not passed')
        manifest=data.get('source_sha256',{})
        require(bool(manifest) and ('rtl/mx_csa.sv' if name=='csa-composition.json' else 'rtl/mx_pe.sv') in manifest,name+' missing source manifest')
        for p,h in manifest.items():
            require(digest(p)==h,name+' stale source: '+p)
            require(p not in source or source[p]==h,'Conflicting proof source: '+p)
            source[p]=h
        evidence[path]=digest(path);components[name]=data
        return data
    def cases(data,fields,expected,label):
        rows=data.get('results',[])
        require(len(rows)==len(expected) and all(r.get('status')=='pass' for r in rows),label+' missing/failed obligations')
        require({tuple(r.get(f) for f in fields) for r in rows}==expected,label+' configuration/control coverage incomplete')
    stream=read('streaming-refinement.json')
    cases(stream,['lanes','stages','negative_control'],{(l,s,n) for l in (8,16,32) for s in (3,4,5) for n in (False,True)},'Streaming')
    bindings=read('product-bindings.json')
    expected={('replication',l,None,n) for l in (8,16,32) for n in (False,True)}
    expected|={('register',l,s,n) for l in (8,16,32) for s in (3,4,5) for n in (False,True)}
    cases(bindings,['kind','lanes','stages','negative_control'],expected,'Product bindings')
    norm=read('normalization-refinement.json')
    cases(norm,['stages','negative_control'],{(s,n) for s in (3,4,5) for n in (False,True)},'Normalization')
    csa=read('csa-composition.json')
    cases(csa,['lanes'],{(l,) for l in (8,16,32)},'CSA')
    require(csa.get('primitive_sat')=='pass' and csa.get('primitive_negative_control')=='counterexample','CSA primitive/control incomplete')
    require('rtl/mx_csa.sv' in csa.get('source_sha256',{}),'CSA source unbound')
    for row in csa['results']:
        require(row.get('negative_controls')==['zero_bit rejected','duplicate_word rejected'],'CSA mutation controls incomplete')
        require(2 in row.get('certified_recursive_sizes',[]) and row['lanes'] in row['certified_recursive_sizes'],'CSA hierarchy incomplete')
    product=read('product-exhaustive.json')
    require(product.get('input_assignments')==27262976,'Exhaustive input space incomplete')
    maximum=14123288431433875456;total=32*maximum;limit=1<<69
    require(product.get('maximum_finite_product')==maximum,'Finite product bound not measured')
    require(product.get('maximum_32_term_magnitude')==total and product.get('signed_70_bit_limit')==limit and total<limit,'Signed accumulation range not established')
    for name in ('converter-equivalence.json','converter-specification.json'):
        converter=read(name)
        require(converter.get('method')=='combinational SAT','Converter method changed')
    require('formal/converter_spec.svh' in source and 'formal/arithmetic_reference.svh' in source,'Independent specification unbound')
    # Explicitly bind the checker and all proof generators, beyond report RTL hashes.
    for path in ('scripts/arithmetic_composition.py','scripts/converter_formal.py','scripts/product_exhaustive.py','scripts/csa_composition.py','scripts/product_bindings.py','scripts/streaming_formal.py','scripts/normalization_formal.py','formal/streaming_pipeline.sv','formal/product_check.svh','formal/arithmetic_reference.svh'):
        source[path]=digest(path)
    # Bind the independently duplicated grid tables used by the product and
    # streaming references to the dot specification. Reject changes for review.
    def compact(path):return ''.join((root/path).read_text().split())
    ref=compact('formal/arithmetic_reference.svh')
    require('case(fmt)0:grid=14;1:grid=0;2:grid=24;3:grid=26;4:grid=30;default:grid=0;endcase' in ref,'Dot grid specification changed')
    require('case(fmt)0:reference_grid=14;1:reference_grid=0;2:reference_grid=24;3:reference_grid=26;4:reference_grid=30;default:reference_grid=0;endcase' in compact('formal/product_check.svh'),'Product grid reference changed')
    require('case(f)0:grid=14;1:grid=0;2:grid=24;3:grid=26;4:grid=30;default:grid=0;endcase' in compact('formal/streaming_pipeline.sv'),'Streaming grid reference changed')
    require('assert(dut.active_fmt==((beat==0)?fmt:heldfmt));' in compact('formal/streaming_pipeline.sv'),'First-beat format binding not proved')
    # Full source used by the dot function includes the converter specification.
    require('reference_dot=specification_convert(total,bf,scale,nanbit,posinf,neginf,approx);' in ref,'Independent dot/converter binding changed')
    return {'status':'pass','scope':'full_pe_independent_spec',
            'method':'Compositional arithmetic refinement: exhaustive finite lane contract + structural CSA induction + unbounded streaming/register refinement + independent scalar RNE SAT proof',
            'configurations':[{'lanes':l,'stages':s} for l in (8,16,32) for s in (3,4,5)],
            'assumptions':['Initial synchronous reset; later resets arbitrary','Two-state RTL semantics','Supported LANES 8/16/32 and PIPE_STAGES 3/4/5'],
            'input_space':'All raw A/B byte encodings; five supported formats and three reserved formats producing poison; all scales, truncations, output formats, valid bubbles, stalls and later resets; first accepted beat supplies block metadata',
            'scope_limits':['PE arithmetic only; not array/APB equivalence or four-state X analysis','Physical checks and measured coverage are separate signoff obligations'],
            'maximum_finite_product':maximum,'maximum_32_term_magnitude':total,'signed_70_bit_limit':limit,
            'rtl_sha256':{**source,**evidence},'component_evidence_sha256':evidence,
            'component_campaigns':len(components),'configuration_and_control_rows':18+24+6+3,
            'documentation':'docs/arithmetic-composition.md'}
def audit_certificate_controls(report):
    """Exercise the assembler on corrupted copies without changing evidence."""
    import shutil,tempfile
    mutations=[
        ('streaming-refinement.json',lambda d:d['results'].pop()),
        ('product-exhaustive.json',lambda d:d.update(input_assignments=20971520)),
        ('normalization-refinement.json',lambda d:d.update(status='fail')),
        ('csa-composition.json',lambda d:d.update(primitive_negative_control='unavailable')),
        ('product-bindings.json',lambda d:d['source_sha256'].update({'rtl/mx_pe.sv':'0'*64})),
        ('product-exhaustive.json',lambda d:d.update(maximum_32_term_magnitude=1<<70))]
    with tempfile.TemporaryDirectory(prefix='mx-certificate-controls-') as directory:
        root=pathlib.Path(directory)
        for path in report['rtl_sha256']:
            target=root/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path,target)
        for name,mutate in mutations:
            path=root/'reports'/name;original=path.read_text();data=json.loads(original);mutate(data);path.write_text(json.dumps(data))
            try:
                try:assemble(root)
                except (OSError,ValueError,KeyError,TypeError):pass
                else:raise RuntimeError('Corrupted certificate input accepted: '+name)
            finally:path.write_text(original)
    return len(mutations)

def main():
    try:
        report=assemble()
        report['certificate_negative_controls_passed']=audit_certificate_controls(report)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        report={'status':'unclosed','scope':'full_pe_independent_spec','failure':str(exc)}
    (ROOT/'reports/arithmetic-equivalence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
    if report['status']!='pass':raise SystemExit(1)
if __name__=='__main__':main()

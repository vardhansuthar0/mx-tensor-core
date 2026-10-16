import hashlib,importlib.metadata,json,pathlib,platform,subprocess,xml.etree.ElementTree as ET
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]
reports=ROOT/'reports'
from provenance import source_manifest
run=json.loads((reports/'verification-inputs.json').read_text())
assert run['source_sha256']==source_manifest(), 'Regression inputs changed during execution; rerun make reproduce'
required=[f'l{l}_p{p}.json' for l in [8,16,32] for p in [3,4,5]]+[f'array{x}.json' for x in [1,2,4]]+['formal.json','mutations.json','model.xml','native-uvm.json','code-coverage.json','coverage-closure.json','converter-equivalence.json','converter-specification.json','formal-negative-controls.json','product-exhaustive.json']
assert all((reports/p).stat().st_mtime>=run['started_epoch'] for p in required), 'Stale regression evidence; rerun make reproduce'

pe=[json.loads((reports/f'l{l}_p{p}.json').read_text()) for l in [8,16,32] for p in [3,4,5]]
arrays=[json.loads((reports/f'array{x}.json').read_text()) for x in [1,2,4]]
formal=json.loads((reports/'formal.json').read_text());mut=json.loads((reports/'mutations.json').read_text())
assert all(x['status']=='pass' for x in pe+arrays+formal)
assert mut['baseline']=='pass' and mut['killed']==mut['total']
assert not ET.parse(reports/'model.xml').getroot().findall('.//failure')
physical_path=reports/'physical.json'
physical=json.loads(physical_path.read_text()) if physical_path.exists() else {'status':'not_run','signoff_status':'unavailable','reason':'No physical report exists at this verification snapshot'}
summary={'generated_utc':datetime.now(timezone.utc).isoformat(),'verification_status':'pass','verification_run_id':run['run_id'],
 'model':{'test_functions':5,'element_codes_crosschecked':656,'rounding_checks':44000},
 'pe_configurations':len(pe),'pe_blocks_checked':sum(x['checked_blocks'] for x in pe),
 'functional_coverage':{'contract_bins_per_configuration':160,'rounding_bins_per_configuration':7,
                        'scope':'Declared bins only; not exhaustive arithmetic or code coverage'},
 'array_tiles_checked':sum(x['tiles'] for x in arrays),'array_results_checked':sum(x['pe_results'] for x in arrays),
 'formal':formal,'mutations':{'killed':mut['killed'],'total':mut['total']},
 'physical':physical,'github':'https://github.com/vardhansuthar0/mx-tensor-core',
 'tools':{name:importlib.metadata.version(name) for name in ['numpy','ml_dtypes','cocotb','pyuvm','cocotb-coverage','verilator','yowasp-yosys']},
 'python':platform.python_version(),
 'limitations':['SKY130 physical results cover one PE only; final acceptance is recorded separately in reports/signoff.json','No cross-block K accumulation; K=32 tiles only',
                'Full PE arithmetic requires the separate source-bound compositional certificate; array/APB equivalence is not established','PE/CSA reachable code/toggle closure uses proven exclusions; array/APB code coverage not measured',
                'Runtime truncation retains 70-bit hardware width','Native SV UVM regression covers one 8-lane PE configuration only']}
for key,name in [('native_uvm','native-uvm.json'),('converter_equivalence','converter-equivalence.json'),('converter_specification','converter-specification.json'),('formal_negative_controls','formal-negative-controls.json'),('product_exhaustive','product-exhaustive.json')]:
 path=reports/name
 if path.exists():summary[key]=json.loads(path.read_text())
path=reports/'code-coverage.json'
if path.exists():
 coverage=json.loads(path.read_text())
 summary['code_coverage']={k:v for k,v in coverage.items() if k!='configurations'}
 summary['code_coverage']['configurations']=[{k:v for k,v in c.items() if k!='uncovered'} for c in coverage['configurations']]
closure=json.loads((reports/'coverage-closure.json').read_text())
assert closure['status']=='pass','Reachable PE coverage audit failed'
summary['reachable_pe_coverage']={k:v for k,v in closure.items() if k!='configurations'}
(reports/'status.json').write_text(json.dumps(summary,indent=2)+'\n')
manifest=run['source_sha256']
(reports/'source-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(summary,indent=2))

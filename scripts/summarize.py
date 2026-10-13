import hashlib,importlib.metadata,json,pathlib,platform,subprocess,xml.etree.ElementTree as ET
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]
reports=ROOT/'reports'
pe=[json.loads((reports/f'l{l}_p{p}.json').read_text()) for l in [8,16,32] for p in [3,4,5]]
arrays=[json.loads((reports/f'array{x}.json').read_text()) for x in [1,2,4]]
formal=json.loads((reports/'formal.json').read_text());mut=json.loads((reports/'mutations.json').read_text())
assert all(x['status']=='pass' for x in pe+arrays+formal)
assert mut['baseline']=='pass' and mut['killed']==mut['total']
assert not ET.parse(reports/'model.xml').getroot().findall('.//failure')
summary={'generated_utc':datetime.now(timezone.utc).isoformat(),'verification_status':'pass',
 'model':{'test_functions':5,'element_codes_crosschecked':656,'rounding_checks':44000},
 'pe_configurations':len(pe),'pe_blocks_checked':sum(x['checked_blocks'] for x in pe),
 'functional_coverage':{'contract_bins_per_configuration':160,'rounding_bins_per_configuration':7,
                        'scope':'Declared bins only; not exhaustive arithmetic or code coverage'},
 'array_tiles_checked':sum(x['tiles'] for x in arrays),'array_results_checked':sum(x['pe_results'] for x in arrays),
 'formal':formal,'mutations':{'killed':mut['killed'],'total':mut['total']},
 'physical':json.loads((reports/'physical.json').read_text()),'github':'https://github.com/vardhansuthar0/mx-tensor-core',
 'tools':{name:importlib.metadata.version(name) for name in ['numpy','ml_dtypes','cocotb','pyuvm','cocotb-coverage','verilator','yowasp-yosys']},
 'python':platform.python_version(),
 'limitations':['SKY130 physical results cover one PE only; signoff violations remain','No cross-block K accumulation; K=32 tiles only',
                'Formal does not prove end-to-end floating-point correctness','No measured code coverage',
                'Runtime truncation retains 70-bit hardware width','Full native SystemVerilog UVM not implemented']}
(reports/'status.json').write_text(json.dumps(summary,indent=2)+'\n')
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['rtl','model','tb','formal','scripts','physical'] for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in str(p) and 'runs' not in p.parts and 'results' not in p.parts and p.suffix in ['.sv','.py','.json','.sby']}
(reports/'source-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(summary,indent=2))

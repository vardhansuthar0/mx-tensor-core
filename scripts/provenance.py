"""Bind a complete regression to a stable source snapshot and fresh reports."""
import hashlib,json,pathlib,time,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
def source_manifest():
    paths=[p for folder in ['rtl','model','tb','formal','scripts','physical'] for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in str(p) and 'runs' not in p.parts and 'results' not in p.parts and p.suffix in ['.sv','.svh','.py','.json','.sby','.c']]
    paths += [ROOT/'Makefile',ROOT/'requirements.txt',ROOT/'requirements-physical.txt']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
if __name__=='__main__':
    report={'run_id':str(uuid.uuid4()),'started_epoch':time.time(),'source_sha256':source_manifest()}
    (ROOT/'reports/verification-inputs.json').write_text(json.dumps(report,indent=2)+'\n')

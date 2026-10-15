"""Run baseline SKY130 implementation, retain failures, collect routed metrics."""
import argparse,hashlib,importlib.util,json,os,pathlib,re,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--tag',default='measured');p.add_argument('--from-step');p.add_argument('--jobs',type=int,default=4);a=p.parse_args()
if not re.fullmatch(r'[A-Za-z0-9_-]+',a.tag):raise SystemExit('Use an alphanumeric run tag')
missing=[x for x in ('openroad','yosys','sta','magic','netgen','klayout','iverilog','vvp') if not shutil.which(x)]
if importlib.util.find_spec('openlane') is None:missing.append('Python openlane')
if not os.environ.get('PDK_ROOT'):missing.append('PDK_ROOT')
if missing:raise SystemExit('Physical prerequisites missing: '+', '.join(missing)+'. Existing measurement reports have been preserved.')
yosys=os.environ.get('YOSYS_SLANG') or shutil.which('yowasp-yosys')
if not a.from_step:
 if not yosys:raise SystemExit('Install yowasp-yosys or set YOSYS_SLANG to a Yosys with read_slang.')
 with (ROOT/'reports/physical-lowering.log').open('w') as f:
  subprocess.run([yosys,'-Q','-T','-p','read_slang -j 1 --top mx_pe_sky130 rtl/mx_csa.sv rtl/mx_pe.sv physical/mx_pe_sky130.sv; proc; flatten; memory_map; opt; check -assert; write_verilog physical/generated.v'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
# Keep helper Python scripts on the same interpreter as the OpenLane driver.
# Native OpenROAD retains its own embedded Python environment.
host=ROOT/'build/host-bin';host.mkdir(parents=True,exist_ok=True)
python_link=host/'python3'
if python_link.exists() or python_link.is_symlink():python_link.unlink()
python_link.symlink_to(sys.executable)
os.environ['PATH']=str(host)+os.pathsep+os.environ['PATH']
if os.environ.get('MX_KLAYOUT_PROC_SELF_EXE')=='1':
 # Resolve the real executable before prepending the wrapper directory.
 search_path=os.pathsep.join(part for part in os.environ['PATH'].split(os.pathsep) if pathlib.Path(part).resolve()!=host.resolve())
 binary=shutil.which('klayout',path=search_path)
 if not binary:raise SystemExit('Cannot locate native KLayout outside the host wrapper directory')
 host=ROOT/'build/host-bin';host.mkdir(parents=True,exist_ok=True)
 library=host/'proc_self_exe.so'
 subprocess.run(['cc','-shared','-fPIC','-O2','-Wall','-Werror',str(ROOT/'scripts/host/proc_self_exe.c'),'-ldl','-o',str(library)],check=True)
 wrapper=host/'klayout'
 import shlex
 wrapper.write_text('#!/bin/sh\nexport LD_PRELOAD='+shlex.quote(str(library))+'${LD_PRELOAD:+:$LD_PRELOAD}\nexec '+shlex.quote(binary)+' "$@"\n')
 wrapper.chmod(0o755)
 os.environ['PATH']=str(host)+os.pathsep+os.environ['PATH']
manifest=ROOT/'reports'/f'physical-inputs-{a.tag}.json'
if a.from_step:
 if not manifest.exists():raise SystemExit('Cannot resume without original source provenance')
 for path,sha in json.loads(manifest.read_text()).items():
  if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise SystemExit('Resume inputs changed: '+path+'; use a fresh run tag')
else:
 inputs=['scripts/closure_flow.py','scripts/host/proc_self_exe.c','rtl/mx_csa.sv','rtl/mx_pe.sv','physical/mx_pe_sky130.sv','physical/config.json','physical/generated.v']
 manifest.write_text(json.dumps({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs},indent=2)+'\n')
info=ROOT/'reports'/f'physical-run-{a.tag}.json'
if not a.from_step:
 top=(ROOT/'physical/mx_pe_sky130.sv').read_text()
 lanes=int(re.search(r'\.LANES\((\d+)\)',top)[1]);stages=int(re.search(r'\.PIPE_STAGES\((\d+)\)',top)[1])
 info.write_text(json.dumps({'lanes':lanes,'stages':stages,'flow':'MXClosure'},indent=2)+'\n')
cmd=[sys.executable,str(ROOT/'scripts/openlane_host.py'),'--flow','MXClosure','--condensed','--jobs',str(a.jobs),'--manual-pdk','--pdk','sky130A','--scl','sky130_fd_sc_hd','--run-tag',a.tag]
if a.from_step:cmd+=['--from',a.from_step]
cmd+=['physical/config.json']
with (ROOT/'reports'/f'physical-flow-{a.tag}.log').open('w') as f:result=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
run=ROOT/'physical/runs'/a.tag
sta=sorted(run.glob('*-openroad-stapostpnr/state_out.json'),key=lambda p:int(p.parent.name.split('-')[0]))
if sta:
 subprocess.run([sys.executable,str(ROOT/'scripts/routed_power.py'),str(sta[-1])],cwd=ROOT,check=True)
 subprocess.run([sys.executable,str(ROOT/'scripts/timing_sweep.py'),str(sta[-1])],cwd=ROOT,check=True)
if not list(run.glob('[0-9]*/*state_out.json')):
 raise SystemExit(result.returncode or 'No completed physical stages; no new physical report written')
subprocess.run([sys.executable,str(ROOT/'scripts/collect_physical.py'),str(run),'--source-manifest',str(manifest),'--flow-exit-code',str(result.returncode)],cwd=ROOT,check=True)
print('Physical flow exit status:',result.returncode,'; measurements: reports/physical.json')
sys.exit(result.returncode)

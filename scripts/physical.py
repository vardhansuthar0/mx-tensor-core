"""Run baseline SKY130 implementation, retain failures, collect routed metrics."""
import argparse,importlib.util,json,os,pathlib,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--tag',default='measured');p.add_argument('--from-step');p.add_argument('--jobs',type=int,default=4);a=p.parse_args()
missing=[x for x in ('openroad','yosys','sta','magic','netgen','klayout','iverilog','vvp') if not shutil.which(x)]
if importlib.util.find_spec('openlane') is None:missing.append('Python openlane')
if not os.environ.get('PDK_ROOT'):missing.append('PDK_ROOT')
if missing:raise SystemExit('Physical prerequisites missing: '+', '.join(missing)+'. Existing measurement reports have been preserved.')
yosys=os.environ.get('YOSYS_SLANG') or shutil.which('yowasp-yosys')
if not a.from_step:
 if not yosys:raise SystemExit('Install yowasp-yosys or set YOSYS_SLANG to a Yosys with read_slang.')
 with (ROOT/'reports/physical-lowering.log').open('w') as f:
  subprocess.run([yosys,'-Q','-T','-p','read_slang -j 1 --top mx_pe_sky130 rtl/mx_csa.sv rtl/mx_pe.sv physical/mx_pe_sky130.sv; proc; flatten; memory_map; opt; check -assert; write_verilog -noattr physical/generated.v'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
cmd=[sys.executable,str(ROOT/'scripts/openlane_host.py'),'--condensed','--jobs',str(a.jobs),'--manual-pdk','--pdk','sky130A','--scl','sky130_fd_sc_hd','--run-tag',a.tag]
if a.from_step:cmd+=['--from',a.from_step]
cmd+=['physical/config.json']
with (ROOT/'reports/physical-flow.log').open('w') as f:result=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
run=ROOT/'physical/runs'/a.tag
sta=sorted(run.glob('*-openroad-stapostpnr/state_out.json'),key=lambda p:int(p.parent.name.split('-')[0]))
if sta:
 subprocess.run([sys.executable,str(ROOT/'scripts/routed_power.py'),str(sta[-1])],cwd=ROOT,check=True)
 subprocess.run([sys.executable,str(ROOT/'scripts/timing_sweep.py'),str(sta[-1])],cwd=ROOT,check=True)
subprocess.run([sys.executable,str(ROOT/'scripts/collect_physical.py'),str(run)],cwd=ROOT,check=True)
print('Physical flow exit status:',result.returncode,'; measurements: reports/physical.json')
sys.exit(result.returncode)

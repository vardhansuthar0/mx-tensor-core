"""Collect only observed OpenLane metrics; preserve stage and corner provenance."""
import argparse,datetime,hashlib,json,pathlib,re,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('run');p.add_argument('--lvs-run');p.add_argument('--source-manifest');p.add_argument('--flow-exit-code',type=int);a=p.parse_args();run=pathlib.Path(a.run).resolve()
files=sorted(run.glob('[0-9]*/*state_out.json'),key=lambda x:int(x.parent.name.split('-')[0]))
if not files:raise SystemExit('No completed stages')
latest=json.loads(files[-1].read_text());metrics=latest['metrics']
sta_files=[x for x in files if 'stapostpnr' in x.parent.name]
sta=json.loads(sta_files[-1].read_text()) if sta_files else None
syn=next((json.loads(x.read_text()) for x in files if x.parent.name.endswith('yosys-synthesis')),None)
evidence=ROOT/'reports/physical-evidence'
if evidence.exists():shutil.rmtree(evidence)
evidence.mkdir()
shutil.copy2(run/'resolved.json',evidence/'resolved.json')
(evidence/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
if sta:
 shutil.copytree(sta_files[-1].parent,evidence/'sta-post-route',dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.sdf','*.lib','*.odb','*.def','*.v','*.spef'))
for f in files:
 if any(s in f.parent.name for s in ('magic-drc','klayout-drc','netgen-lvs','checker-')):
  dest=evidence/f.parent.name;dest.mkdir(exist_ok=True)
  for s in f.parent.iterdir():
   if s.is_file() and s.suffix in ('.log','.json','.rpt','.txt'):shutil.copy2(s,dest/s.name)
def matched_report(name):
 path=ROOT/'reports'/name
 if not sta or not path.exists():return None
 result=json.loads(path.read_text())
 expected=hashlib.sha256(pathlib.Path(sta['nl']).read_bytes()).hexdigest()
 return result if result.get('netlist_sha256')==expected else None
if a.lvs_run:
 lvs_run=pathlib.Path(a.lvs_run)
 lvs_files=sorted(lvs_run.glob('*-netgen-lvs/state_out.json'))
 if lvs_files:
  lvs_state=json.loads(lvs_files[-1].read_text())
  if hashlib.sha256(pathlib.Path(lvs_state['nl']).read_bytes()).digest()!=hashlib.sha256(pathlib.Path(latest['nl']).read_bytes()).digest():raise SystemExit('LVS netlist does not match')
  metrics.update({k:v for k,v in lvs_state['metrics'].items() if 'lvs' in k or 'illegal_overlap' in k})
  shutil.copytree(lvs_files[-1].parent,evidence/'netgen-lvs',dirs_exist_ok=True)
(evidence/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
clock_reports={}
if sta:
 for f in sta_files[-1].parent.rglob('*.rpt'):
  s=f.read_text(errors='replace');matches=re.findall(r'clk period_min = ([\d.]+) fmax = ([\d.]+)',s)
  if matches:clock_reports[str(f.relative_to(sta_files[-1].parent))]={'minimum_period_ns':float(matches[-1][0]),'sta_fmax_mhz':float(matches[-1][1])}
physical={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'post_route_measured' if sta else 'partial','configuration':'8-lane, 4-stage PE, runtime five formats, 70-bit accumulator; not the 4x4 array','signoff_status':'pending_evaluation','requested_clock_ns':json.loads((run/'resolved.json').read_text())['CLOCK_PERIOD'],'synthesis_area_um2':syn['metrics'].get('design__instance__area') if syn else None,'area_um2':metrics.get('design__instance__area__stdcell',metrics.get('design__instance__area')),'core_area_um2':metrics.get('design__core__area'),'die_area_um2':metrics.get('design__die__area'),'utilization':metrics.get('design__instance__utilization'),'timing':{k:v for k,v in (sta['metrics'] if sta else {}).items() if k.startswith('timing__')},'sta_clock_reports':clock_reports,'drc_lvs':{k:v for k,v in metrics.items() if any(s in k for s in ('drc','lvs','antenna','xor'))},'timing_sweep':matched_report('timing-sweep.json'),'last_completed_stage':files[-1].parent.name,'power':matched_report('routed-power.json'),'limitations':['Physical result covers one PE configuration only.','STA frequency estimates are not silicon measurements or a PnR clock sweep.','Gate activity is zero-delay; delay-induced glitches are not included.','CPU/RSS tool telemetry was disabled for host PID namespace compatibility.']}
info_path=ROOT/'reports'/f'physical-run-{run.name}.json'
if info_path.exists():
 info=json.loads(info_path.read_text())
 physical['configuration']=f"{info['lanes']}-lane, {info['stages']}-stage PE, runtime five formats, 70-bit accumulator; not the 4x4 array"
 physical['implementation_configuration']=info
else:
 physical['configuration']='Historical candidate: consult the original source hash and run configuration'
physical['flow_exit_code']=a.flow_exit_code
physical['source_sha256']=json.loads(pathlib.Path(a.source_manifest).read_text()) if a.source_manifest else {}
physical['netlist_sha256']=hashlib.sha256(pathlib.Path(sta['nl']).read_bytes()).hexdigest() if sta else None
physical['electrical']={k:v for k,v in (sta['metrics'] if sta else {}).items() if k.startswith(('design__max_slew_violation','design__max_cap_violation'))}
physical['klayout_checks']={name:('pass' if metrics.get(key)==0 else 'not_passed') for name,key in [('drc','klayout__drc_error__count'),('xor','design__xor_difference__count')]}
(ROOT/'reports/physical.json').write_text(json.dumps(physical,indent=2)+'\n');print(json.dumps(physical,indent=2))

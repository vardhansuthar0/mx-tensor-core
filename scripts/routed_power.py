"""Checked gate VCD plus extracted-parasitic OpenSTA power at TT, 5 MHz.
Use a completed OpenLane STA post-PnR state. Output remains an estimate, not
silicon power; zero-delay simulation excludes delay-induced glitches.
"""
import argparse,hashlib,json,os,pathlib,re,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('state');a=p.parse_args();state=json.load(open(a.state))
if not state.get('spef'):raise SystemExit('Post-route SPEF required')
subprocess.run([sys.executable,str(ROOT/'scripts/gate_activity.py'),state['nl']],check=True,cwd=ROOT)
meta=json.load(open(ROOT/'reports/gate-activity.json'));spefs=state['spef'];print('SPEF corners',spefs)
spef=next((v for k,v in spefs.items() if k=='nom' or k.startswith('nom_')),None)
if isinstance(spef,list):spef=spef[0]
if not spef:raise SystemExit('No nominal SPEF found')
lib=pathlib.Path(os.environ['PDK_ROOT'])/'sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib'
def q(x):return '{'+str(x)+'}'
tcl=f'''read_liberty {q(lib)}
read_verilog {q(state['nl'])}
link_design mx_pe_sky130
read_sdc {q(state['sdc'])}
create_clock -name clk -period 200 [get_ports clk]
set_propagated_clock [all_clocks]
read_spef {q(spef)}
puts "TOTAL_STA_PINS [llength [get_pins -hierarchical *]]"
read_vcd -scope power_tb/dut {q(meta['vcd'])}
report_power -digits 9
report_worst_slack -max
report_worst_slack -min
report_clock_min_period -include_port_paths
exit
'''
script=ROOT/'build/gate-power/routed_power.tcl';script.write_text(tcl)
log=ROOT/'reports/routed-power.log'
with log.open('w') as f:subprocess.run(['sta','-exit',str(script)],stdout=f,stderr=subprocess.STDOUT,check=True,cwd=ROOT)
s=log.read_text()
if re.search(r'^Error:',s,re.M):raise SystemExit('OpenSTA reported an error; inspect log')
count=int(re.search(r'Annotated (\d+) pin activities',s)[1]);total=int(re.search(r'TOTAL_STA_PINS (\d+)',s)[1])
if count==0:raise SystemExit('No VCD annotations; refusing to label power activity-based')
v=list(map(float,re.search(r'^Total\s+([\deE.+-]+)\s+([\deE.+-]+)\s+([\deE.+-]+)\s+([\deE.+-]+)',s,re.M).groups()))
meta.update({'netlist_sha256':hashlib.sha256(pathlib.Path(state['nl']).read_bytes()).hexdigest(),'corner':'nom_tt_025C_1v80','power_mw':dict(zip(['internal','switching','leakage','total'],[x*1000 for x in v])),'estimated_energy_pj_per_block':v[3]*meta['activity_window_ns']*1000/meta['blocks_checked'],'annotated_pin_activities':count,'sta_pin_count':total,'annotation_count_ratio_pct':100*count/total,'annotation_note':'Tool-reported annotation count divided by STA pin count; unannotated pins use tool defaults. Not a claim of full annotation.','spef':spef,'log':'reports/routed-power.log'})
(ROOT/'reports/routed-power.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))

"""STA period sweep of the fixed routed netlist (not a PnR optimization sweep).
Retains the routed SDC's fixed 10 ns interface budgets, derates and uncertainty.
"""
import argparse,hashlib,json,os,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('state');a=p.parse_args();state=json.load(open(a.state))
if not state.get('spef'):raise SystemExit('Routed SPEF required')
work=ROOT/'build/timing-sweep';work.mkdir(parents=True,exist_ok=True)
pdk=pathlib.Path(os.environ['PDK_ROOT'])/'sky130A/libs.ref/sky130_fd_sc_hd/lib'
spefs={k.removesuffix('_*'):v for k,v in state['spef'].items()}; corners=[];reads=[]
def q(s):return '{'+str(s)+'}'
for rc,path in spefs.items():
 if isinstance(path,list):path=path[0]
 for c in ('tt_025C_1v80','ss_100C_1v60','ff_n40C_1v95'):
  name=rc+'_'+c;corners.append(name);reads.append(f'read_liberty -corner {name} {q(pdk/("sky130_fd_sc_hd__"+c+".lib"))}')
tcl='define_corners '+' '.join(corners)+'\n'+'\n'.join(reads)+'\n'
tcl+=f'read_verilog {q(state["nl"])}\nlink_design mx_pe_sky130\nread_sdc {q(state["sdc"])}\n'
for rc,path in spefs.items():
 if isinstance(path,list):path=path[0]
 for c in ('tt_025C_1v80','ss_100C_1v60','ff_n40C_1v95'):tcl+=f'read_spef -corner {rc}_{c} {q(path)}\n'
tcl+='''
proc margin {period} {
 create_clock -name clk -period $period [get_ports clk]
 set_propagated_clock [all_clocks]
 return [sta::worst_slack -max]
}
puts "TARGET50_WNS [margin 50]"
set low 1.0
set high 1000.0
if {[margin $high] < 0} {error "Cannot bracket passing period"}
for {set i 0} {$i < 22} {incr i} {
 set mid [expr {($low+$high)/2.0}]
 if {[margin $mid] < 0} {set low $mid} else {set high $mid}
}
puts "FAIL_PERIOD_NS $low"
puts "PASS_PERIOD_NS $high"
puts "PASS_SETUP_WNS [margin $high]"
puts "PASS_HOLD_WNS [sta::worst_slack -min]"
puts "STA_LIMIT_MHZ [expr {1000.0/$high}]"
puts "POWER5MHZ_SETUP_WNS [margin 200]"
puts "POWER5MHZ_HOLD_WNS [sta::worst_slack -min]"
check_setup -verbose -unconstrained_endpoints
exit
'''
f=work/'sweep.tcl';f.write_text(tcl);log=ROOT/'reports/timing-sweep.log'
with log.open('w') as out:subprocess.run(['sta','-exit',str(f)],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,check=True)
s=log.read_text()
if re.search(r'^Error:',s,re.M):raise SystemExit('STA error; inspect reports/timing-sweep.log')
keys=('TARGET50_WNS','FAIL_PERIOD_NS','PASS_PERIOD_NS','PASS_SETUP_WNS','PASS_HOLD_WNS','STA_LIMIT_MHZ','POWER5MHZ_SETUP_WNS','POWER5MHZ_HOLD_WNS')
result={k.lower():float(re.search(r'^'+k+r' ([\deE.+-]+)',s,re.M)[1]) for k in keys}
result.update({'netlist_sha256':hashlib.sha256(pathlib.Path(state['nl']).read_bytes()).hexdigest(),'corners':corners,'method':'22-step period bisection, fixed routed netlist and parasitics, fixed SDC interface delays; not a physical-flow clock sweep','log':'reports/timing-sweep.log'})
(ROOT/'reports/timing-sweep.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

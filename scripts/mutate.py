"""Manual RTL mutants. Compile errors/timeouts are INVALID, never kills."""
import concurrent.futures,json,pathlib,subprocess,sys,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'rtl/mx_pe.sv').read_text()
MUTATIONS={
 'broken_backpressure':('wire advance=!out_valid || out_ready;', 'wire advance=!out_valid || out_ready || in_valid;'),
 'scale_bias':("int'(in_scale_b)-254", "int'(in_scale_b)-253"),
 'subnormal_exponent':("((ex!=0)?ex:1)-bias-mb", "((ex!=0)?ex:0)-bias-mb"),
 'e4m3_max_is_nan':('fmt==0 && ex==15 && fr==7','fmt==0 && ex==15 && fr>=6'),
 'product_sign':('(da[i].signbit ^ db[i].signbit)?-clipped:clipped','(da[i].signbit | db[i].signbit)?-clipped:clipped'),
 'round_ties_up':('guardbit && (sticky || kept[0])','guardbit'),
 'ignore_nan_scale':('(in_scale_a==255)','(1\'b0)'),
 'drop_prior_beats':('sum3<=running+$signed(lane_sum)','sum3<=$signed(lane_sum)'),
 'disable_truncation':('clipped=(mag>>cut)<<cut','clipped=mag | (70\'(cut)&70\'d0)'),
}

def run_one(name,pair):
 old,new=pair
 if SOURCE.count(old)!=1: raise RuntimeError(f'non-unique mutation {name}')
 path=ROOT/'build'/'mutants'/name/'mx_pe.sv';path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(SOURCE.replace(old,new))
 log=ROOT/'reports'/f'mutant-{name}.log'
 command=[sys.executable,str(ROOT/'scripts/run_sim.py'),'--lanes','8','--stages','4','--count','100','--rtl',str(path),'--label',f'mutant_{name}']
 try:
  with log.open('w') as f: result=subprocess.run(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180)
 except subprocess.TimeoutExpired:
  return {'name':name,'status':'invalid','reason':'timeout'}
 text=log.read_text();xml=ROOT/'build'/f'mutant_{name}'/'results.xml'
 status='survived' if result.returncode==0 else 'invalid'
 reason='no functional failure identified'
 if result.returncode and xml.exists():
  root=ET.parse(xml).getroot()
  failures=root.findall('.//failure')
  if failures and ('SCOREBOARD:' in text or 'PROTOCOL:' in text):
   status='killed';reason='scoreboard/protocol assertion'
 if result.returncode and 'Running tests' in text and 'Assertion failed' in text:
  status='killed';reason='RTL assertion'
 return {'name':name,'status':status,'reason':reason,'log':str(log.relative_to(ROOT))}

if __name__=='__main__':
 # Passing baseline is mandatory, independent of stale report files.
 with (ROOT/'reports/mutation-baseline.log').open('w') as f:
  subprocess.run([sys.executable,str(ROOT/'scripts/run_sim.py'),'--lanes','8','--stages','4','--count','100','--label','mutation_baseline'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
  results=list(pool.map(lambda x:run_one(*x),MUTATIONS.items()))
 report={'baseline':'pass','mutants':results,'killed':sum(x['status']=='killed' for x in results),'total':len(results)}
 (ROOT/'reports/mutations.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
 sys.exit(0 if report['killed']==report['total'] else 1)

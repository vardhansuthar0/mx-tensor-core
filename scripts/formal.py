import json,os,pathlib,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
yosys=os.environ.get('YOSYS') or shutil.which('yowasp-yosys') or str(pathlib.Path.home()/'.local/bin/yowasp-yosys')
commands={
 'csa': 'read_verilog -sv -formal rtl/mx_csa.sv formal/csa.sv; prep -top csa_proof -flatten; chformal -lower; sat -verify -prove-asserts -show-inputs',
 'protocol': 'read_slang -j 1 --top protocol_proof rtl/mx_csa.sv rtl/mx_pe.sv formal/protocol.sv; prep -top protocol_proof -flatten; chformal -lower; memory_map; opt; dffunmap; sat -seq 6 -tempinduct -maxsteps 10 -timeout 30 -set-assumes -prove-asserts -verify'
}
(ROOT/'build').mkdir(exist_ok=True)
(ROOT/'build/formal-protocol5.sv').write_text((ROOT/'formal/protocol.sv').read_text().replace('.PIPE_STAGES(4)','.PIPE_STAGES(5)'))
commands['protocol5']=commands['protocol'].replace('formal/protocol.sv','build/formal-protocol5.sv')
results=[]
for name,command in commands.items():
 log=ROOT/'reports'/f'formal-{name}.log'
 with log.open('w') as f:
  p=subprocess.run([yosys,'-Q','-T','-p',command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180)
 text=log.read_text()
 success=p.returncode==0 and ('SUCCESS!' in text)
 results.append({'name':name,'status':'pass' if success else 'fail','method':'combinational SAT' if name=='csa' else 'unbounded temporal induction',
                 'scope':'70-bit 3:2 compressor equivalence modulo 2^70' if name=='csa' else f'8-lane {5 if name=="protocol5" else 4}-stage PE reset and output stability under backpressure; not arithmetic equivalence',
                 'log':str(log.relative_to(ROOT))})
 print(name,success)
(ROOT/'reports/formal.json').write_text(json.dumps(results,indent=2)+'\n')
if not all(x['status']=='pass' for x in results):sys.exit(1)

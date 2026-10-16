"""Native SystemVerilog UVM PE smoke/regression using pinned Accellera UVM.
No HDL backdoor/DPI calls are used. Golden vectors come from the integer model.
"""
import argparse, hashlib, json, os, pathlib, re, subprocess, sys
from run_sim import ROOT, setup_tools
sys.path.insert(0,str(ROOT))
from tb.cases import cases
from model.mx import dot
UVM_COMMIT='78c06547a2a0a29b3dc9dcafae62b75b2ff61544'

def run():
    setup_tools()
    p=argparse.ArgumentParser();p.add_argument('--stages',type=int,choices=(3,4,5),default=5);p.add_argument('--count',type=int,default=2500);p.add_argument('--skip-build',action='store_true');a=p.parse_args()
    build=ROOT/'build/native-uvm';build.mkdir(parents=True,exist_ok=True)
    uvm=ROOT/'build/uvm-core'
    if not uvm.exists():
        subprocess.run(['git','clone','--depth','1','--branch','2020.3.1','https://github.com/accellera-official/uvm-core.git',str(uvm)],check=True)
    commit=subprocess.check_output(['git','-C',str(uvm),'rev-parse','HEAD'],text=True).strip()
    if commit!=UVM_COMMIT:raise SystemExit('UVM source does not match pinned commit')
    vectors=build/'vectors.txt';blocks=cases(count=a.count)
    with vectors.open('w') as f:
        for b in blocks:
            av=sum(v<<(i*8) for i,v in enumerate(b.a));bv=sum(v<<(i*8) for i,v in enumerate(b.b))
            data,flags=dot(b.a,b.b,b.fmt,b.sa,b.sb,b.bf16,b.trunc)
            f.write(f'{av:064x} {bv:064x} {b.fmt:x} {b.sa:02x} {b.sb:02x} {int(b.bf16):x} {b.trunc:02x} {data:08x} {flags:02x}\n')
    if not a.skip_build:
        cmd=['verilator','--binary','--timing','--assert','-Wno-fatal','-CFLAGS','-std=c++20',
             '+define+UVM_NO_DPI','--top-module','mx_uvm_top',f'-GPIPE_STAGES={a.stages}',
             '+incdir+'+str(uvm/'src'),str(uvm/'src/uvm_pkg.sv'),
             'rtl/mx_csa.sv','rtl/mx_pe.sv','tb/uvm/mx_uvm.sv','--Mdir',str(build),'-j','2']
        with (ROOT/'reports/native-uvm-build.log').open('w') as f:
            subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
    log=ROOT/'reports/native-uvm.log'
    with log.open('w') as f:
        result=subprocess.run([str(build/'Vmx_uvm_top'),'+vectors='+str(vectors)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180)
    text=log.read_text();matches=re.findall(r'\[MX_PASS\] checked=(\d+)',text)
    success=result.returncode==0 and matches==[str(len(blocks))] and all(re.search(rf'{s}\s*:\s*0\b',text) for s in ('UVM_ERROR','UVM_FATAL'))
    report={'status':'pass' if success else 'fail','blocks_checked':int(matches[0]) if matches else 0,
            'expected_blocks':len(blocks),'uvm_commit':commit,'uvm_version':'Accellera 2020.3.1',
            'configuration':{'lanes':8,'stages':a.stages},'seed':20261011,
            'scope':'Native SV UVM sequence, sequencer, driver, monitor, scoreboard; deterministic integer-model vectors and LFSR backpressure. Initial reset only. PE only; no UVM coverage closure claim. DPI/backdoor disabled.',
            'rtl_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'rtl').glob('*.sv'))},
            'vectors_sha256':hashlib.sha256(vectors.read_bytes()).hexdigest(),'log':'reports/native-uvm.log'}
    (ROOT/'reports/native-uvm.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not success:raise SystemExit(1)
if __name__=='__main__':run()

import os,pathlib,shutil,subprocess,sys
from run_sim import ROOT,setup_tools
setup_tools()
for lanes in [8,16,32]:
 for stages in [3,4,5]:
  subprocess.run(['verilator','--lint-only','--assert','-Wall','--top-module','mx_pe',f'-GLANES={lanes}',f'-GPIPE_STAGES={stages}','rtl/mx_csa.sv','rtl/mx_pe.sv'],cwd=ROOT,check=True)
subprocess.run(['verilator','--lint-only','--assert','-Wall','--top-module','mx_engine','rtl/mx_csa.sv','rtl/mx_pe.sv','rtl/mx_engine.sv'],cwd=ROOT,check=True)
yosys=os.environ.get('YOSYS') or shutil.which('yowasp-yosys') or str(pathlib.Path.home()/'.local/bin/yowasp-yosys')
with (ROOT/'reports/yosys-check.log').open('w') as log:
 subprocess.run([yosys,'-Q','-T','-p','read_slang -j 1 --top mx_engine rtl/mx_csa.sv rtl/mx_pe.sv rtl/mx_engine.sv; hierarchy -check; proc; opt; check -assert; stat'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
print('Verilator warning-clean: nine PE configurations and 4x4 engine. Yosys hierarchy/process/check passed.')

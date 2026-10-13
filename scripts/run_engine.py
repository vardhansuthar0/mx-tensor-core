import argparse,os,sys
from pathlib import Path
from run_sim import setup_tools,ROOT
setup_tools()
import cocotb_tools.runner as runner_module
runner_module.MAX_PARALLEL_BUILD_JOBS=2
from cocotb_tools.runner import get_runner,get_results
p=argparse.ArgumentParser();p.add_argument('--size',type=int,default=4);a=p.parse_args()
r=get_runner('verilator');build=ROOT/'build'/f'array{a.size}'
r.build(sources=[ROOT/'rtl'/f'{x}.sv' for x in ['mx_csa','mx_pe','mx_engine']],hdl_toplevel='mx_engine',build_dir=build,
        parameters={'M':a.size,'N':a.size},build_args=['--assert','-Wall'],always=True)
executable=build/'mx_engine'
executable.chmod(executable.stat().st_mode | 0o100)
r.test(hdl_toplevel='mx_engine',test_module='tb.test_engine',test_dir=build,results_xml='results.xml',
       extra_env={'MX_M':str(a.size),'MX_N':str(a.size),'MX_REPORT':str(ROOT/'reports'/f'array{a.size}.json')})
tests,failures=get_results(build/'results.xml')
assert tests and not failures

#!/usr/bin/env python3
import argparse, os, pathlib, shutil, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def setup_tools():
    if not shutil.which('verilator'):
        import verilator
        os.environ['PATH']=str(pathlib.Path(verilator.__file__).parent/'bin')+os.pathsep+os.environ['PATH']
    # Avoid broken precompiled-header include flags in the pinned wheel.
    os.environ['MAKEFLAGS']=os.environ.get('MAKEFLAGS','')+' VK_PCH_I_FAST= VK_PCH_I_SLOW='
    os.environ['PYTHONPATH']=str(ROOT)+os.pathsep+os.environ.get('PYTHONPATH','')

def run(lanes=32, stages=4, rtl=None, label=None, count=2500, coverage=False):
    setup_tools()
    import cocotb_tools.runner as runner_module
    runner_module.MAX_PARALLEL_BUILD_JOBS=2
    from cocotb_tools.runner import get_runner, get_results
    runner=get_runner('verilator')
    label=label or f'l{lanes}_p{stages}'
    build=ROOT/'build'/label
    sources=[ROOT/'rtl/mx_csa.sv',pathlib.Path(rtl) if rtl else ROOT/'rtl/mx_pe.sv']
    runner.build(sources=sources,hdl_toplevel='mx_pe',build_dir=build,
                 parameters={'LANES':lanes,'PIPE_STAGES':stages},
                 build_args=['--assert','-Wall']+(['--coverage'] if coverage else []),always=True)
    executable=build/'mx_pe'
    executable.chmod(executable.stat().st_mode | 0o100)
    runner.test(hdl_toplevel='mx_pe',test_module='tb.test_pe',test_dir=build,
                extra_env={'MX_LANES':str(lanes),'MX_STAGES':str(stages),'MX_COUNT':str(count),
                           'MX_REPORT':str(ROOT/'reports'/f'{label}.json')},
                results_xml='results.xml',
                test_args=['+verilator+coverage+file+'+str(build/'coverage.dat')] if coverage else [])
    tests, failures=get_results(build/'results.xml')
    if failures or not tests:
        raise RuntimeError(f'{label}: {failures}/{tests} tests failed')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lanes',type=int,default=32);p.add_argument('--stages',type=int,default=4)
    p.add_argument('--coverage',action='store_true');p.add_argument('--count',type=int,default=2500);p.add_argument('--rtl');p.add_argument('--label')
    a=p.parse_args();run(a.lanes,a.stages,a.rtl,a.label,a.count,a.coverage)

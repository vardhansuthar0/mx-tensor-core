"""Exhaust every finite input assignment to the one-lane product cone.

This is an exhaustive compiled combinational check, not a sequential PE proof.
The production decoder/product source is extracted verbatim; the reference
uses independently decoded fixed-point element magnitudes and a wide product.
"""
import hashlib,json,pathlib,subprocess
from run_sim import setup_tools
ROOT=pathlib.Path(__file__).resolve().parents[1]

def run():
    setup_tools()
    rtl=(ROOT/'rtl/mx_pe.sv').read_text()
    declarations=rtl[rtl.index('    typedef struct packed'):rtl.index('    function automatic integer leading70')]
    cone=rtl[rtl.index('    logic [LANES*70-1:0] products_comb'):rtl.index('    always_ff @(posedge clk) begin\n        if(rst) begin v2')]
    reference=(ROOT/'formal/arithmetic_reference.svh').read_text().split('function automatic [36:0] reference_dot')[0]
    check=(ROOT/'formal/product_check.svh').read_text()
    header='module product_proof(input [7:0] in_a,in_b,input [2:0] fmt,input [4:0] trunc,input poison,negative_control,output ok);\nlocalparam LANES=1;\n'
    decode="dec_t da[LANES],db[LANES];meta_t m1;\nalways_comb begin da[0]=decode(in_a,fmt);db[0]=decode(in_b,fmt);m1='0;m1.grid=grid_for(fmt);m1.trunc=trunc;m1.poison=poison;end\n"
    work=ROOT/'build/product-exhaustive';work.mkdir(parents=True,exist_ok=True)
    source=work/'product_proof.sv';source.write_text(header+declarations+decode+cone+reference+check+'\nendmodule\n')
    cpp=work/'driver.cpp'
    cpp.write_text('''#include "Vproduct_proof.h"
#include "verilated.h"
#include <cstdio>
int main(int argc,char**argv){
Verilated::commandArgs(argc,argv);Vproduct_proof dut;unsigned long checked=0;
dut.negative_control=0;
for(unsigned fmt=0;fmt<8;++fmt)for(unsigned a=0;a<256;++a)for(unsigned b=0;b<256;++b)for(unsigned t=0;t<32;++t)for(unsigned p=0;p<2;++p){
if(fmt>4 && p==0)continue;
dut.fmt=fmt;dut.in_a=a;dut.in_b=b;dut.trunc=t;dut.poison=p;dut.eval();
if(!dut.ok){printf("FAIL %u %u %u %u %u\\n",fmt,a,b,t,p);return 1;}++checked;}
// A deliberately wrong production product bit must be detected.
dut.in_a=0;dut.in_b=0;dut.fmt=1;dut.trunc=0;dut.poison=0;dut.negative_control=1;dut.eval();
if(dut.ok){puts("FAIL negative control escaped");return 2;}
printf("PASS %lu exhaustive product inputs; inverted product bit rejected\\n",checked);return 0;}
''')
    build_log=ROOT/'reports/product-exhaustive-build.log'
    log=ROOT/'reports/product-exhaustive.log'
    with build_log.open('w') as f:
        subprocess.run(['verilator','--cc','--exe','--build','-j','2','-Wno-fatal','--top-module','product_proof','--Mdir',str(work),str(source),str(cpp)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
    with log.open('w') as f:
        result=subprocess.run([str(work/'Vproduct_proof')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=120)
    passed=result.returncode==0 and 'PASS 27262976 exhaustive product inputs; inverted product bit rejected' in log.read_text()
    paths=['rtl/mx_pe.sv','formal/arithmetic_reference.svh','formal/product_check.svh','scripts/product_exhaustive.py']
    report={'status':'pass' if passed else 'fail','input_assignments':27262976,
            'method':'exhaustive compiled combinational enumeration with independent integer reference',
            'scope':'One lane: all 256 A/B byte encodings, five supported formats with poison on/off, plus all three reserved formats with required poison, and 32 truncations. Checks signed 70-bit product and all four special/approximation flags. Not PE sequencing or full arithmetic equivalence.',
            'negative_control':'Inverted production product bit must fail on a known zero input',
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
            'harness_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'log':str(log.relative_to(ROOT))}
    (ROOT/'reports/product-exhaustive.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not passed:raise SystemExit(1)

if __name__=='__main__':run()

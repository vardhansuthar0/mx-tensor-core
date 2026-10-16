"""All-input converter rewrite equivalence and independent integer-RNE proof.
These are converter lemmas, not a full sequential PE arithmetic proof.
"""
import hashlib,json,pathlib,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]

def run():
    rtl=(ROOT/'rtl/mx_pe.sv').read_text()
    functions=rtl[rtl.index('    function automatic integer leading70'):rtl.index('    wire advance=')]
    prefix=rtl[rtl.index('    // Preserve parallel-prefix'):rtl.index('    // End normalization network.')]
    build=ROOT/'build';build.mkdir(exist_ok=True)
    yosys=shutil.which('yowasp-yosys') or str(pathlib.Path.home()/'.local/bin/yowasp-yosys')
    for name,file,function,report_name,scope in [
        ('converter','converter_reference.svh','reference_convert','converter-equivalence.json','All converter inputs equivalent to frozen baseline 835e63e'),
        ('converter-spec','converter_spec.svh','specification_convert','converter-specification.json','All converter inputs equivalent to independently written integer quotient/remainder RNE specification')]:
        ref=(ROOT/'formal'/file).read_text()
        header='module converter_proof(input signed [69:0] total, input bf16, input signed [9:0] scale, input nanbit,posinf,neginf,approx);\nwire [69:0] sum3=total;\n'
        miter=header+functions+prefix+ref+f'\nalways @* assert(convert(total,bf16,scale,nanbit,posinf,neginf,approx,completed_mag,completed_lead)=={function}(total,bf16,scale,nanbit,posinf,neginf,approx));\nendmodule\n'
        source=build/f'{name}_miter.sv';source.write_text(miter)
        log=ROOT/'reports'/f'formal-{name}.log'
        with log.open('w') as f:
            result=subprocess.run([yosys,'-Q','-T','-p',f'read_verilog -formal -sv build/{source.name}; prep -top converter_proof -flatten; chformal -lower; opt; sat -verify -prove-asserts -timeout 300'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=360)
        success=result.returncode==0 and 'SUCCESS!' in log.read_text()
        report={'status':'pass' if success else 'fail','method':'combinational SAT','scope':scope+'; all 70-bit sums, 10-bit scales, output formats and special flags. Not full PE arithmetic equivalence.',
                'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'rtl/mx_pe.sv',ROOT/'formal'/file,ROOT/'scripts/converter_formal.py']},'harness_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'log':str(log.relative_to(ROOT))}
        (ROOT/'reports'/report_name).write_text(json.dumps(report,indent=2)+'\n')
        print(report,flush=True)
        if not success:raise SystemExit(1)
if __name__=='__main__':run()

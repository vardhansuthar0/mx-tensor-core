"""Require counterexamples for deliberately wrong properties.
Build errors and timeouts never count as successful negative controls.
"""
import json,pathlib,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
def run():
    build=ROOT/'build';build.mkdir(exist_ok=True)
    rtl=(ROOT/'rtl/mx_pe.sv').read_text()
    functions=rtl[rtl.index('    function automatic integer leading70'):rtl.index('    wire advance=')]
    prefix=rtl[rtl.index('    // Preserve parallel-prefix'):rtl.index('    // End normalization network.')]
    reference=(ROOT/'formal/converter_reference.svh').read_text()
    converter='module converter_negative(input signed [69:0] total,input bf16,input signed [9:0] scale,input nanbit,posinf,neginf,approx);\nwire [69:0] sum3=total;\n'+functions+prefix+reference+"\nalways @* assert(convert(total,bf16,scale,nanbit,posinf,neginf,approx,completed_mag,completed_lead)==(reference_convert(total,bf16,scale,nanbit,posinf,neginf,approx)^37'd1));\nendmodule\n"
    (build/'converter_negative.sv').write_text(converter)
    protocol=(ROOT/'formal/protocol.sv').read_text().replace('if(past_valid && was_rst) assert(!out_valid);','if(past_valid && was_rst) assert(out_valid);')
    (build/'protocol_negative.sv').write_text(protocol)
    yosys=shutil.which('yowasp-yosys') or str(pathlib.Path.home()/'.local/bin/yowasp-yosys')
    commands={
      'converter': 'read_verilog -formal -sv build/converter_negative.sv; prep -top converter_negative -flatten; chformal -lower; opt; sat -verify -prove-asserts -timeout 30',
      'protocol': 'read_slang -j 1 --top protocol_proof rtl/mx_csa.sv rtl/mx_pe.sv build/protocol_negative.sv; prep -top protocol_proof -flatten; chformal -lower; memory_map; opt; dffunmap; sat -seq 3 -set-assumes -prove-asserts -verify -timeout 30'}
    results=[]
    for name,command in commands.items():
        log=ROOT/'reports'/f'formal-negative-{name}.log'
        with log.open('w') as f:
            result=subprocess.run([yosys,'-Q','-T','-p',command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=90)
        rejected=result.returncode!=0 and 'model found: FAIL!' in log.read_text()
        results.append({'name':name,'status':'pass' if rejected else 'invalid','expected':'Counterexample for deliberately inverted result/reset assertion','log':str(log.relative_to(ROOT))})
    report={'status':'pass' if all(r['status']=='pass' for r in results) else 'fail','controls':results}
    (ROOT/'reports/formal-negative-controls.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if report['status']!='pass':raise SystemExit(1)
if __name__=='__main__':run()

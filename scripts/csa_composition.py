"""Check the elaborated CSA hierarchy by Boolean identities and induction.

The checker accepts only a wire, a two-input modular adder, or a strictly
smaller certified CSA fed by exact 3:2 reductions and untouched remainders.
This proves the CSA cone, not full PE arithmetic equivalence.
"""
import copy,hashlib,json,pathlib,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
class ProofError(Exception):pass
def require(ok,message):
    if not ok:raise ProofError(message)
ZERO=frozenset()
ONE=frozenset([frozenset()])
def atom(i):return frozenset([frozenset([i])])
def xor(a,b):return a^b
def land(a,b):
    out=ZERO
    for x in a:
        for y in b:out=out^frozenset([x|y])
    return out
def lor(a,b):return xor(xor(a,b),land(a,b))
def number(bits):
    require(all(b in ('0','1') for b in bits),'Nonconstant shift')
    return sum((b=='1')<<i for i,b in enumerate(bits))
def check(design):
    modules=design['modules'];done=set();levels=[]
    def visit(name):
        if name in done:return
        m=modules[name];ports=m['ports'];raw=ports['terms']['bits'];out=ports['sum']['bits'];w=len(out)
        require(w==70 and len(raw)%w==0,'Unexpected width')
        n=len(raw)//w
        require(all(type(b) is int for b in raw) and len(set(raw))==len(raw),'Lost independent input bits')
        words=[raw[i*w:(i+1)*w] for i in range(n)]
        cells=list(m.get('cells',{}).values())
        if n==1:require(out==raw and not cells,'Bad one-input base')
        elif n==2:
            require(len(cells)==1 and cells[0]['type']=='$add','Bad two-input base')
            c=cells[0]['connections']
            require(c['Y']==out and sorted([c['A'],c['B']])==sorted(words),'Incorrect modular-adder binding')
        else:
            children=[c for c in cells if c['type'] in modules]
            require(len(children)==1,'Expected one recursive child')
            child=children[0];cw=child['connections']['terms'];cs=child['connections']['sum']
            g,r=divmod(n,3);nn=2*g+r
            require(cs==out and len(cw)==nn*w and nn<n,'Incorrect recursion/output binding')
            require(len(modules[child['type']]['ports']['terms']['bits'])==len(cw),'Child width mismatch')
            visit(child['type'])
            drivers={}
            for c in cells:
                if c is child:continue
                require(c['type'] in ('$xor','$and','$or','$shl'),'Unsupported reduction operator '+c['type'])
                p=c['connections']
                for i,b in enumerate(p['Y']):
                    require(type(b) is int and b not in drivers and b not in raw,'Multiple/invalid drivers')
                    drivers[b]=(c,i)
            cache={b:atom(b) for b in raw};active=set()
            def ev(b):
                if b=='0':return ZERO
                if b=='1':return ONE
                require(type(b) is int,'Unknown symbolic value')
                if b in cache:return cache[b]
                require(b in drivers and b not in active,'Undriven/cyclic reduction')
                active.add(b);c,i=drivers[b];p=c['connections'];typ=c['type']
                def bit(k,j):return ev(p[k][j]) if 0<=j<len(p[k]) else ZERO
                if typ=='$shl':value=bit('A',i-number(p['B']))
                else:value={'$xor':xor,'$and':land,'$or':lor}[typ](bit('A',i),bit('B',i))
                active.remove(b);cache[b]=value;return value
            expected=[]
            for i in range(g):
                a,b,c=words[3*i:3*i+3]
                expected.extend([
                    [xor(xor(atom(a[k]),atom(b[k])),atom(c[k])) for k in range(w)],
                    [ZERO]+[xor(xor(land(atom(a[k]),atom(b[k])),land(atom(a[k]),atom(c[k]))),land(atom(b[k]),atom(c[k]))) for k in range(w-1)]])
            expected.extend([[atom(b) for b in word] for word in words[3*g:]])
            for i,word in enumerate(expected):
                for k,value in enumerate(word):
                    require(ev(cw[i*w+k])==value,f'Incorrect reduction N={n} word={i} bit={k}')
        done.add(name);levels.append(n)
    visit('csa_root')
    return sorted(set(levels))
def run():
    backend=shutil.which('yosys')
    if not backend:raise SystemExit('Requires native Yosys')
    work=ROOT/'build/csa-composition';work.mkdir(parents=True,exist_ok=True)
    (ROOT/'reports').mkdir(exist_ok=True)
    files=['rtl/mx_csa.sv','scripts/csa_composition.py']
    source={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
    results=[]
    for n in (8,16,32):
        wrapper=work/f'root{n}.sv';design=work/f'root{n}.json'
        wrapper.write_text(f'module csa_root(input [{n*70-1}:0] terms,output [69:0] sum); mx_csa #(.N({n}),.W(70)) core(terms,sum); endmodule\n')
        # Make mx_csa the top name so the verifier sees the actual recursive root.
        command=f'read_verilog -sv rtl/mx_csa.sv; hierarchy -top mx_csa -chparam N {n} -chparam W 70; proc; opt; rename -top csa_root; write_json {design.relative_to(ROOT)}'
        log=ROOT/'reports'/f'csa-structure-{n}.log'
        with log.open('w') as f:subprocess.run([backend,'-Q','-T','-p',command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=60)
        data=json.loads(design.read_text());levels=check(data)
        root=data['modules']['csa_root'];child=next(c for c in root['cells'].values() if c['type'] in data['modules'])
        for mode in ('zero_bit','duplicate_word'):
            wrong=copy.deepcopy(data)
            target=next(c for c in wrong['modules']['csa_root']['cells'].values() if c['type'] in wrong['modules'])
            if mode=='zero_bit':target['connections']['terms'][0]='0'
            else:target['connections']['terms'][70:140]=target['connections']['terms'][:70]
            try:check(wrong)
            except ProofError:pass
            else:raise ProofError('Incorrect reduction accepted: '+mode)
        results.append({'lanes':n,'status':'pass','certified_recursive_sizes':levels,'negative_controls':['zero_bit rejected','duplicate_word rejected']})
        print('CSA',n,'structure pass',levels,flush=True)
    # Independent SAT check of the 70-bit 3:2 identity used at each level.
    for negative in (False,True):
        harness=work/'primitive.sv'
        harness.write_text("module primitive(input [69:0] a,b,c); wire [69:0] actual; mx_csa #(.N(3),.W(70)) dut({c,b,a},actual); wire [69:0] reference=a+b+c; always @* assert(actual "+("!=" if negative else "==")+" reference); endmodule\n")
        log=ROOT/'reports'/('csa-primitive-negative.log' if negative else 'csa-primitive.log')
        command=f'read_verilog -sv -formal rtl/mx_csa.sv {harness.relative_to(ROOT)}; prep -top primitive -flatten; sat -timeout 90 -verify -prove-asserts -show-inputs'
        with log.open('w') as f:p=subprocess.run([backend,'-Q','-T','-p',command],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=110)
        text=log.read_text()
        require(('model found: FAIL!' in text and p.returncode!=0) if negative else ('SUCCESS!' in text and p.returncode==0),'Primitive SAT obligation unclosed')
    require(all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items()),'Sources changed')
    report={'status':'pass','scope':'CSA trees for 8, 16 and 32 arbitrary 70-bit terms, exact modulo 2^70; not full PE equivalence',
            'method':'Induction over elaborated hierarchy; exact Boolean polynomial check of every reduced bit; independent 70-bit 3:2 SAT identity and counterexample control',
            'source_sha256':source,'results':results,'primitive_sat':'pass','primitive_negative_control':'counterexample'}
    (ROOT/'reports/csa-composition.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':run()

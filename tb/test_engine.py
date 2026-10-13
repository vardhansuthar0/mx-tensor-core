import os,random
from collections import deque
import cocotb
from cocotb.triggers import Timer
from model.mx import dot,FORMATS

@cocotb.test()
async def array_and_apb(d):
    M=int(os.environ['MX_M']);N=int(os.environ['MX_N']);L=8
    rng=random.Random(438)
    async def tick(reset=0):
        d.clk.value=0;d.rst.value=reset;await Timer(5,unit='ns')
        sample=(int(d.in_ready.value),int(d.out_valid.value),int(d.out_data.value),int(d.out_flags.value))
        d.clk.value=1;await Timer(5,unit='ns');return sample
    async def access(addr,write=False,data=0,error=0):
        d.psel.value=1;d.penable.value=0;d.paddr.value=addr;d.pwrite.value=int(write);d.pwdata.value=data
        await tick();d.penable.value=1
        d.clk.value=0;await Timer(5,unit='ns')
        assert int(d.pready.value)==1
        assert int(d.pslverr.value)==error
        result=int(d.prdata.value)
        d.clk.value=1;await Timer(5,unit='ns');d.psel.value=0;d.penable.value=0
        return result
    d.in_valid.value=0;d.out_ready.value=0;d.in_a.value=0;d.in_b.value=0
    d.in_scale_a.value=0;d.in_scale_b.value=0
    d.psel.value=0;d.penable.value=0;d.pwrite.value=0;d.paddr.value=0;d.pwdata.value=0
    await tick(1);await tick(1)
    assert await access(12)==(M<<24|N<<16|8<<8|4)
    await access(0,True,7,error=1);await access(8,True,0,error=1);await access(3,error=1)
    assert await access(0)==0
    expected_sticky=0;retired=0
    for fmt,(eb,mb,bias) in enumerate(FORMATS):
        for bf in [0,1]:
            trunc=1 if bf else 0
            config=fmt|(bf<<3)|(trunc<<4)
            await access(0,True,config)
            assert await access(0)==config
            for trial in range(3):
                a=[[rng.randrange(1<<(1+eb+mb)) for _ in range(32)] for _ in range(M)]
                b=[[rng.randrange(1<<(1+eb+mb)) for _ in range(32)] for _ in range(N)]
                sa=[255 if trial==0 and r==0 else 127+r for r in range(M)]
                sb=[125+c for c in range(N)]
                d.in_scale_a.value=sum(x<<(8*r) for r,x in enumerate(sa))
                d.in_scale_b.value=sum(x<<(8*c) for c,x in enumerate(sb))
                expected=[dot(a[r],b[c],fmt,sa[r],sb[c],bool(bf),trunc) for r in range(M) for c in range(N)]
                for beat in range(4):
                    d.in_valid.value=1
                    d.in_a.value=sum(a[r][beat*L+i]<<(8*(r*L+i)) for r in range(M) for i in range(L))
                    d.in_b.value=sum(b[c][beat*L+i]<<(8*(c*L+i)) for c in range(N) for i in range(L))
                    assert (await tick())[0]
                d.in_valid.value=0
                for _ in range(12):
                    _,valid,data,flags=await tick()
                    if valid: break
                else: raise AssertionError('array deadlock')
                wantdata=sum(x[0]<<(32*k) for k,x in enumerate(expected))
                wantflags=sum(x[1]<<(5*k) for k,x in enumerate(expected))
                assert(data,flags)==(wantdata,wantflags)
                for _ in range(4):
                    _,valid,data2,flags2=await tick();assert valid and (data2,flags2)==(data,flags)
                # W1C concurrent with retirement: newly raised flags must win.
                d.psel.value=1;d.penable.value=0;d.pwrite.value=1;d.paddr.value=4;d.pwdata.value=31
                await tick();d.penable.value=1;d.out_ready.value=1
                await tick();d.psel.value=0;d.penable.value=0;d.out_ready.value=0
                expected_sticky=0
                for _,f in expected:expected_sticky|=f
                retired+=1
                assert await access(4)==expected_sticky
                assert await access(8)==retired
                await access(4,True,31);assert await access(4)==0
    await tick(1);assert await access(8)==0;assert await access(4)==0
    import json
    from pathlib import Path
    Path(os.environ['MX_REPORT']).write_text(json.dumps({'status':'pass','M':M,'N':N,'tiles':retired,'pe_results':retired*M*N,'checks':['broadcast indexing','all formats','both outputs','APB decode/errors','W1C event precedence','retirement counter','output stall','reset']},indent=2)+'\n')

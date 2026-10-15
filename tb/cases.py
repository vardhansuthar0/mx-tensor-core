"""Deterministic closure suite plus seeded random sequence items."""
from dataclasses import dataclass
import random
from model.mx import FORMATS

SCENARIOS = ('zero','subnormal','maximum','cancel','scale_low','scale_high','nan_scale_a','nan_scale_b')
@dataclass
class Block:
    a: list
    b: list
    fmt: int = 0
    sa: int = 127
    sb: int = 127
    bf16: bool = False
    trunc: int = 0
    tag: str = 'random'


def cases(seed=20261011, count=2500):
    rng=random.Random(seed)
    out=[]
    for fmt,(e,m,bias) in enumerate(FORMATS):
        one=bias<<m
        sign=1<<(e+m)
        maximum=(1<<(e+m))-1-(1 if fmt==0 else 4 if fmt==1 else 0)
        for bf in [False,True]:
            for trunc in [0,1]:
                for tag in SCENARIOS:
                    a=[one]*32; b=[one]*32; sa=sb=127
                    if tag=='zero': a=[0]*32
                    if tag=='subnormal': a=b=[1]*32
                    if tag=='maximum': a=b=[maximum]*32
                    if tag=='cancel': a=[one]*16+[one|sign]*16
                    if tag=='scale_low': sa=sb=0
                    if tag=='scale_high': sa=sb=254
                    if tag=='nan_scale_a': sa=255
                    if tag=='nan_scale_b': sb=255
                    out.append(Block(a,b,fmt,sa,sb,bf,trunc,tag))
        # Every encoding, including both signed zeros, exercised as a lane
        # with a finite nonzero partner. Products checked by the scoreboard.
        for start in range(0,1<<(1+e+m),32):
            a=[(start+i)% (1<<(1+e+m)) for i in range(32)]
            for bf in [False,True]:
                out.append(Block(a,[one]*32,fmt,bf16=bf,tag='decode_sweep'))
        # Every scale byte on both inputs, preserving alternating sign.
        for sc in range(256):
            out.append(Block([one|((sc%2)*sign)]+[0]*31,[one]*32,fmt,sc,127,bool(sc%2),tag='scale_sweep'))
            out.append(Block([one]+[0]*31,[one]*32,fmt,127,sc,bool(sc%2),tag='scale_sweep'))
    # NaNs, both infinities, zero*infinity, opposite infinities, reserved format.
    for bf in [False,True]:
        for ac,bc in [(0x7c,0),(0x7c,0x7c),(0x7c,0x3c),(0xfc,0x3c),(0x7d,0x3c)]:
            out.append(Block([ac]+[0]*31,[bc]*32,1,bf16=bf,tag='special'))
        out.append(Block([0x7c,0xfc]+[0]*30,[0x3c]*32,1,bf16=bf,tag='opposite_inf'))
        out.append(Block([0x7f]+[0]*31,[0x38]*32,0,bf16=bf,tag='special'))
        out.append(Block([0]*32,[0]*32,7,bf16=bf,tag='reserved'))
        # E5M2: 1 + 2^-(p) is an exact output midpoint; +/- smallest
        # product breaks the tie, and an odd retained LSB must round upward.
        p=8 if bf else 24
        tiny_exp=-p
        choices={}
        from model.mx import decode
        for ac in range(1,0x7c):
            x=decode(ac,1)
            for bc in range(1,0x7c):
                y=decode(bc,1)
                if x.sig*y.sig and (x.sig*y.sig)&(x.sig*y.sig-1)==0:
                    power=(x.sig*y.sig).bit_length()-1+x.exp+y.exp
                    choices.setdefault(power,(ac,bc))
        # Carry into a new normal exponent, and subnormal RNE promotion to
        # minimum normal. These were uncovered converter branches.
        ac,bc=choices[-p]
        out.append(Block([0x3c,0x3c,ac|0x80]+[0]*29,[0x3c,0x3c,bc]+[0]*29,1,bf16=bf,tag='round_carry'))
        out.append(Block([0x3c,ac|0x80]+[0]*30,[0x3c,bc]+[0]*30,1,1,127,bf,tag='round_to_min_normal'))
        for direction in [-1,0,1]:
            for odd in [False,True]:
                a=[0x3c]; b=[0x3c]
                ac,bc=choices[tiny_exp];a.append(ac);b.append(bc)
                if direction: a.append(1|(0x80 if direction<0 else 0));b.append(1)
                if odd:
                    ac,bc=choices[tiny_exp+1];a.append(ac);b.append(bc)
                out.append(Block(a+[0]*(32-len(a)),b+[0]*(32-len(b)),1,bf16=bf,tag='rounding'))
    # Sparse powers exercise the low product bits that broad random blocks
    # obscure, and move each event through every physical lane/beat position.
    # E5M2 powers span the complete fixed-point product grid (bits 0..62).
    from model.mx import decode
    powers={}
    for code in range(1,0x7c):
        value=decode(code,1)
        if value.sig and value.sig & (value.sig-1)==0:
            powers.setdefault(value.sig.bit_length()-1+value.exp,code)
    products={}
    for ap,ac in powers.items():
        for bp,bc in powers.items():
            products.setdefault(ap+bp+32,(ac,bc))
    for bit,(ac,bc) in sorted(products.items()):
        for negative in [False,True]:
            signed=ac | (0x80 if negative else 0)
            for lane in range(32):
                a=[0]*32;b=[0]*32;a[lane]=signed;b[lane]=bc
                out.append(Block(a,b,1,tag='sparse_product_bit'))
            out.append(Block([signed]*32,[bc]*32,1,tag='carry_product_bit'))
        # Mixed populations expose carries hidden by both a one-hot vector
        # and the symmetric all-lanes vector at recursive compressor levels.
        masks=random.Random(0xCA770000+bit)
        for _ in range(64):
            a=[];b=[]
            for lane in range(32):
                enabled=masks.randrange(2)
                a.append((ac | (0x80 if masks.randrange(2) else 0)) if enabled else 0)
                b.append(bc if enabled else 0)
            out.append(Block(a,b,1,tag='mixed_carry_product_bit'))
    for lane in range(32):
        for code,partner,trunc in [(0x7c,0x3c,0),(0xfc,0x3c,0),
                                   (0x7d,0x3c,0),(1,1,1)]:
            a=[0]*32;b=[0]*32;a[lane]=code;b[lane]=partner
            out.append(Block(a,b,1,trunc=trunc,tag='special_lane_position'))
    for _ in range(count):
        fmt=rng.randrange(5); e,m,_=FORMATS[fmt]; limit=1<<(1+e+m)
        a=[rng.randrange(limit) for _ in range(32)]; b=[rng.randrange(limit) for _ in range(32)]
        # Upper byte padding noise is legal and must not alter FP4/FP6.
        if limit<256:
            a=[x|(rng.randrange(256//limit)*limit) for x in a]
            b=[x|(rng.randrange(256//limit)*limit) for x in b]
        out.append(Block(a,b,fmt,rng.randrange(256),rng.randrange(256),bool(rng.randrange(2)),rng.choice([0,0,1,4,8,16,31])))
    return out

def scenario_hits(block):
    """Classify observed transaction fields; tags never award coverage."""
    if block.fmt not in range(5): return set()
    e,m,bias=FORMATS[block.fmt];mask=(1<<(1+e+m))-1
    a=[x&mask for x in block.a];b=[x&mask for x in block.b]
    one=bias<<m;sign=1<<(e+m)
    maximum=(1<<(e+m))-1-(1 if block.fmt==0 else 4 if block.fmt==1 else 0)
    hits=set()
    if all((x & (sign-1))==0 for x in a):hits.add('zero')
    if a==[1]*32 and b==[1]*32:hits.add('subnormal')
    if a==[maximum]*32 and b==[maximum]*32:hits.add('maximum')
    if a==[one]*16+[one|sign]*16 and b==[one]*32:hits.add('cancel')
    if block.sa==block.sb==0:hits.add('scale_low')
    if block.sa==block.sb==254:hits.add('scale_high')
    if block.sa==255:hits.add('nan_scale_a')
    if block.sb==255:hits.add('nan_scale_b')
    return hits

def rounding_class(block):
    from model.mx import decode
    if block.fmt not in range(5) or max(block.sa,block.sb)==255:return None
    _,m,bias=FORMATS[block.fmt];unit=2*(1-bias-m)
    total=0
    for ac,bc in zip(block.a,block.b):
        x,y=decode(ac,block.fmt),decode(bc,block.fmt)
        if x.kind!='finite' or y.kind!='finite':return None
        mag=x.sig*y.sig<<(x.exp+y.exp-unit)
        mag=(mag>>block.trunc)<<block.trunc
        total+=-mag if x.sign^y.sign else mag
    value=abs(total)
    if not value:return 'exact'
    p=8 if block.bf16 else 24;expo=unit+block.sa+block.sb-254
    lead=value.bit_length()-1
    if lead+expo>127:return 'overflow'
    if lead+expo< -126:return 'underflow'
    shift=lead-(p-1)
    if shift<=0:return 'exact'
    retained,remainder=divmod(value,1<<shift)
    if not remainder:return 'exact'
    half=1<<(shift-1)
    if remainder<half:return 'below_half'
    if remainder>half:return 'above_half'
    return 'tie_odd' if retained&1 else 'tie_even'

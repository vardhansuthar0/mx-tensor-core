import math
import random
import struct
from fractions import Fraction
import numpy as np
import ml_dtypes as ml
from model.mx import FORMATS, decode, dot, pack

TYPES = [ml.float8_e4m3fn, ml.float8_e5m2, ml.float6_e3m2fn,
         ml.float6_e2m3fn, ml.float4_e2m1fn]

def test_all_element_codes():
    for fmt, (e, m, _) in enumerate(FORMATS):
        for code in range(1 << (1+e+m)):
            x = decode(code, fmt)
            other = float(np.array([code], dtype=np.uint8).view(TYPES[fmt])[0])
            if x.kind == 'nan':
                assert math.isnan(other)
            elif x.kind == 'inf':
                assert other == (-math.inf if x.sign else math.inf)
            else:
                ours = math.ldexp((-1.0 if x.sign else 1.0)*x.sig, x.exp)
                assert ours == other
                assert math.copysign(1, ours) == math.copysign(1, other)

def test_widths():
    for fmt, w in enumerate([42, 70, 24, 18, 14]):
        e, m, bias = FORMATS[fmt]
        vals = [decode(i, fmt) for i in range(1 << (e+m))]
        ints = [x.sig << (x.exp-(1-bias-m)) for x in vals if x.kind == 'finite']
        assert 1+(32*max(ints)**2).bit_length() == w

def test_pack_crosscheck():
    rng = random.Random(84)
    with np.errstate(over='ignore', under='ignore'):
        for _ in range(20000):
            # <=24-bit integers are represented exactly in binary64; direct
            # float64 -> destination casts independently cross-check rounding.
            n = rng.randrange(-(1 << 24), 1 << 24)
            exponent = rng.randrange(-190, 150)
            value = math.ldexp(n, exponent)
            for bf16 in [False, True]:
                dt, udt = (ml.bfloat16, np.uint16) if bf16 else (np.float32, np.uint32)
                other = int(np.array([value], dtype=dt).view(udt)[0])
                assert pack(n, exponent, bf16)[0] == other

def test_wide_rounding_boundaries():
    # Each target neighbor is exact as a Fraction. Select the nearest of
    # nearby representable values independently, including ties-even.
    rng = random.Random(915)
    for bf16 in [False, True]:
        m = 7 if bf16 else 23
        for _ in range(2000):
            e = rng.randrange(1, 253)
            code = (e << m) | rng.randrange(1 << m)
            exp = e-127-m
            mant = (1 << m) | (code & ((1 << m)-1))
            low = Fraction(mant)*Fraction(2)**exp
            step = Fraction(2)**exp
            offset = rng.choice([0, 1, 2, 3, 4])
            value = low+step*offset/4
            candidates = [(code, low), (code+1, low+step)]
            expected = min(candidates, key=lambda c:(abs(value-c[1]), c[0]&1))[0]
            n = value.numerator
            ex = -(value.denominator.bit_length()-1)
            # Force a wide integer to catch host-double loss in a model.
            assert pack(n << 75, ex-75, bf16)[0] == expected

def test_dot_directed():
    for fmt, (_, m, bias) in enumerate(FORMATS):
        one = bias << m
        assert dot([one]*32, [one]*32, fmt)[0] == 0x42000000
        assert dot([1]*32, [1]*32, fmt, sa=255)[0] == 0x7fc00000
        assert dot([one]*32, [one]*32, fmt, sa=0, sb=0) == (0, 3)
        assert dot([one]*32, [one]*32, fmt, sa=254, sb=254) == (0x7f800000, 5)
    assert dot([0x7c]+[0]*31, [0]*32, 1) == (0x7fc00000, 8)
    assert dot([1]+[0]*31, [1]+[0]*31, 4, trunc=1) == (0, 16)
    assert pack(1, -150) == (0, 3)
    assert pack(3, -150) == (2, 3)
    assert pack((1 << 24)-1, -150) == (0x800000, 1)

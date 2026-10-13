"""Integer-only reference. No host floating arithmetic in dot/pack paths."""
from dataclasses import dataclass

FORMATS = ((4, 3, 7), (5, 2, 15), (3, 2, 3), (2, 3, 1), (2, 1, 1))
NAMES = ('E4M3', 'E5M2', 'E3M2', 'E2M3', 'E2M1')
INEXACT, UNDERFLOW, OVERFLOW, INVALID, APPROX = 1, 2, 4, 8, 16

@dataclass(frozen=True)
class Element:
    sign: int
    sig: int
    exp: int
    kind: str = 'finite'

def decode(code, fmt):
    e, m, bias = FORMATS[fmt]
    sign = (code >> (e+m)) & 1
    ex = (code >> m) & ((1 << e)-1)
    frac = code & ((1 << m)-1)
    kind = 'finite'
    if fmt == 0 and ex == 15 and frac == 7:
        kind = 'nan'
    if fmt == 1 and ex == 31:
        kind = 'inf' if frac == 0 else 'nan'
    return Element(sign, frac + ((1 << m) if ex else 0),
                   (ex if ex else 1)-bias-m, kind)

def round_shift(value, shift):
    """Positive integer scaled by 2^-shift; return RNE integer and lost flag."""
    if shift <= 0:
        return value << -shift, False
    kept, lost = divmod(value, 1 << shift)
    half = 1 << (shift-1)
    return kept + (lost > half or (lost == half and kept & 1)), bool(lost)

def pack(value, exponent, bf16=False):
    """Round signed integer * 2**exponent to binary32/bfloat16."""
    p = 8 if bf16 else 24
    sign = int(value < 0)
    value = abs(value)
    signword = sign << (p+7)
    if value == 0:
        return 0, 0
    lead = value.bit_length()-1
    unbiased = lead + exponent
    shift = max(lead-(p-1), -126-(p-1)-exponent)
    mant, lost = round_shift(value, shift)
    flags = INEXACT if lost else 0
    if unbiased < -126:
        if mant < 1 << (p-1):
            return signword | mant, flags | (UNDERFLOW if lost else 0)
        unbiased = -126
    elif mant == 1 << p:
        mant >>= 1
        unbiased += 1
    if unbiased > 127:
        return signword | (255 << (p-1)), OVERFLOW | INEXACT
    return signword | ((unbiased+127) << (p-1)) | (mant & ((1 << (p-1))-1)), flags

def dot(a, b, fmt=0, sa=127, sb=127, bf16=False, trunc=0):
    if len(a) != 32 or len(b) != 32:
        raise ValueError('MX blocks contain exactly 32 elements')
    if not 0 <= trunc <= 31 or not 0 <= sa <= 255 or not 0 <= sb <= 255:
        raise ValueError('control out of range')
    nanword = 0x7fc0 if bf16 else 0x7fc00000
    if fmt not in range(5) or sa == 255 or sb == 255:
        return nanword, INVALID
    _, m, bias = FORMATS[fmt]
    unit = 2*(1-bias-m)
    total = 0
    posinf = neginf = invalid = approx = False
    for ac, bc in zip(a, b):
        x, y = decode(ac, fmt), decode(bc, fmt)
        sign = x.sign ^ y.sign
        if x.kind == 'nan' or y.kind == 'nan':
            invalid = True
        elif x.kind == 'inf' or y.kind == 'inf':
            if (x.kind == 'finite' and x.sig == 0) or (y.kind == 'finite' and y.sig == 0):
                invalid = True
            elif sign:
                neginf = True
            else:
                posinf = True
        else:
            mag = (x.sig*y.sig) << (x.exp+y.exp-unit)
            approx |= bool(mag & ((1 << trunc)-1))
            mag = (mag >> trunc) << trunc
            total += -mag if sign else mag
    aflag = APPROX if approx else 0
    if invalid or (posinf and neginf):
        return nanword, INVALID | aflag
    if posinf or neginf:
        return ((0xff80 if neginf else 0x7f80) if bf16 else
                (0xff800000 if neginf else 0x7f800000)), aflag
    bits, flags = pack(total, unit+sa+sb-254, bf16)
    return bits, flags | aflag

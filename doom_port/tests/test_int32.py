#!/usr/bin/env python3
from __future__ import annotations
import random

I32_MIN = -(1 << 31)
I32_MAX = (1 << 31) - 1
MASK = (1 << 32) - 1


def i32(v: int) -> int:
    v &= MASK
    return v - (1 << 32) if v >= (1 << 31) else v


def trunc_div(a: int, b: int) -> int:
    assert b != 0
    q = abs(a) // abs(b)
    return -q if (a < 0) ^ (b < 0) else q


def trunc_mod(a: int, b: int) -> int:
    return a - trunc_div(a, b) * b


def h_floor_div_65536(a: int) -> int:
    q = trunc_div(a, 65536)
    r = trunc_mod(a, 65536)
    if r < 0:
        q -= 1
    return q


def h_floor_mod_65536(a: int) -> int:
    r = trunc_mod(a, 65536)
    if r < 0:
        r += 65536
    return r


def h_u16_product_hi(a: int, b: int) -> int:
    a1, a0 = a // 256, a % 256
    b1, b0 = b // 256, b % 256
    cross = a1 * b0 + a0 * b1
    lowcarry = (a0 * b0) // 256
    return a1 * b1 + (cross + lowcarry) // 256


def h_fixed_mul(a: int, b: int) -> int:
    ah, al = h_floor_div_65536(a), h_floor_mod_65536(a)
    bh, bl = h_floor_div_65536(b), h_floor_mod_65536(b)
    t0 = i32(i32(ah * bh) * 65536)
    t1 = i32(ah * bl + al * bh)
    t2 = h_u16_product_hi(al, bl)
    return i32(i32(t0 + t1) + t2)


def ref_fixed_mul(a: int, b: int) -> int:
    return i32((a * b) >> 16)


def h_sar1(a: int) -> int:
    q = trunc_div(a, 2)
    if a < 0 and trunc_mod(a, 2) != 0:
        q -= 1
    return q


def h_shr1_u32(a: int) -> int:
    if a >= 0:
        return a // 2
    q = trunc_div(a, 2)
    if trunc_mod(a, 2) != 0:
        q -= 1
    q = 1073741824 + q
    return 1073741824 + q


def h_frac16_pos(rem: int, den: int) -> int:
    out = 0
    threshold = den // 2 + den % 2
    for _ in range(16):
        out *= 2
        if rem >= threshold:
            rem = rem - (den - rem)
            out += 1
        else:
            rem += rem
    return out


def h_frac16_den_2p31(rem: int) -> int:
    out = 0
    for _ in range(16):
        out *= 2
        if rem >= 1073741824:
            rem = rem - (2147483647 - rem) - 1
            out += 1
        else:
            rem += rem
    return out


def h_fixed_div_mag(a_mag: int, b_mag: int, a_2p31: bool, b_2p31: bool) -> int:
    if a_2p31:
        if b_2p31:
            return 65536
        q = I32_MAX // b_mag
        rem = I32_MAX % b_mag
        if rem == b_mag - 1:
            q += 1
            rem = 0
        else:
            rem += 1
    else:
        if b_2p31:
            return h_frac16_den_2p31(a_mag)
        q = a_mag // b_mag
        rem = a_mag % b_mag
    out = q * 65536
    if rem:
        out += h_frac16_pos(rem, b_mag)
    return out


def h_fixed_div(a: int, b: int) -> int:
    if b == 0:
        return I32_MIN if a < 0 else I32_MAX
    if a == I32_MIN:
        amag, a2 = I32_MAX, True
    elif a < 0:
        amag, a2 = -a, False
    else:
        amag, a2 = a, False
    if b == I32_MIN:
        bmag, b2 = I32_MAX, True
    elif b < 0:
        bmag, b2 = -b, False
    else:
        bmag, b2 = b, False
    lhs = 131072 if a2 else amag // 16384
    if not b2 and lhs >= bmag:
        return I32_MIN if ((a < 0) ^ (b < 0)) else I32_MAX
    qmag = h_fixed_div_mag(amag, bmag, a2, b2)
    return -qmag if ((a < 0) ^ (b < 0)) else qmag


def ref_fixed_div(a: int, b: int) -> int:
    # Mathematical version of FixedDiv's guard plus the disabled int64 FixedDiv2
    # branch in linuxdoom-1.10/m_fixed.c.  Treat abs(INT_MIN) as magnitude 2^31.
    amag, bmag = abs(a), abs(b)
    if (amag >> 14) >= bmag:
        return I32_MIN if ((a < 0) ^ (b < 0)) else I32_MAX
    q = trunc_div(a * 65536, b)
    assert I32_MIN <= q <= I32_MAX
    return q


def test_mul() -> None:
    fixed = [I32_MIN, I32_MIN + 1, -0x40000000, -65537, -65536, -1, 0, 1, 65535, 65536, 0x40000000, I32_MAX]
    for a in fixed:
        for b in fixed:
            assert h_fixed_mul(a, b) == ref_fixed_mul(a, b), (a, b, h_fixed_mul(a,b), ref_fixed_mul(a,b))
    rng = random.Random(0xD00F1E)
    for _ in range(200_000):
        a = rng.randint(I32_MIN, I32_MAX)
        b = rng.randint(I32_MIN, I32_MAX)
        assert h_fixed_mul(a, b) == ref_fixed_mul(a, b), (a, b)


def test_shifts() -> None:
    fixed = [I32_MIN, I32_MIN + 1, -3, -2, -1, 0, 1, 2, 3, I32_MAX]
    for a in fixed:
        assert h_sar1(a) == i32(a) >> 1
        assert h_shr1_u32(a) == ((a & MASK) >> 1)


def test_div() -> None:
    fixed_a = [I32_MIN, I32_MIN + 1, -0x40000000, -65537, -65536, -1, 0, 1, 65535, 65536, 0x40000000, I32_MAX]
    fixed_b = [I32_MIN, I32_MIN + 1, -1000000, -131073, -131072, -65536, -2, -1, 1, 2, 65536, 131072, 131073, 1000000, I32_MAX]
    for a in fixed_a:
        for b in fixed_b:
            got = h_fixed_div(a, b)
            exp = ref_fixed_div(a, b)
            assert got == exp, (a, b, got, exp)
    rng = random.Random(0xF17ED1)
    for _ in range(200_000):
        a = rng.randint(I32_MIN, I32_MAX)
        b = rng.randint(I32_MIN, I32_MAX)
        if b == 0:
            b = 1
        got = h_fixed_div(a, b)
        exp = ref_fixed_div(a, b)
        assert got == exp, (a, b, got, exp)


def main() -> None:
    test_mul()
    test_shifts()
    test_div()
    print('int32/fixed-point compatibility tests: PASS')

if __name__ == '__main__':
    main()

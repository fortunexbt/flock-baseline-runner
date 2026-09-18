#!/usr/bin/env python3
"""Apply the deferred Karatsuba experiment to a pristine Flock checkout."""
from pathlib import Path
import difflib
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
expected = '1b55c6ee2c9cae3c807489293199760e5e21d52b'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == expected
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip()
p = root / 'crates/flock-core/src/field/gf2_128/x86_64.rs'
original = p.read_bytes().decode()
s = original.replace('\r\n', '\n')
start = s.index('    pub unsafe fn mul_acc(&mut self, x: __m512i, y: __m512i) {')
end = s.index('\n    /// XOR-accumulate two', start)
s = s[:start] + '''    pub unsafe fn mul_acc(&mut self, x: __m512i, y: __m512i) {
        // Accumulate the Karatsuba middle product without reconstructing the
        // cross term yet. Linearity lets reduce_lanes/fold do that once for
        // the complete sum, rather than after every product.
        let lo = _mm512_clmulepi64_epi128::<0x00>(x, y);
        let hi = _mm512_clmulepi64_epi128::<0x11>(x, y);
        let x_sum = _mm512_xor_si512(x, _mm512_shuffle_epi32::<0x4e>(x));
        let y_sum = _mm512_xor_si512(y, _mm512_shuffle_epi32::<0x4e>(y));
        let middle = _mm512_clmulepi64_epi128::<0x00>(x_sum, y_sum);
        self.lo = _mm512_xor_si512(self.lo, lo);
        self.hi = _mm512_xor_si512(self.hi, hi);
        self.mid = _mm512_xor_si512(self.mid, middle);
    }
''' + s[end:]
start = s.index('    pub unsafe fn mul_acc2(&mut self, x0: __m512i, y0: __m512i, x1: __m512i, y1: __m512i) {')
end = s.index('\n    /// XOR-accumulate the 4 unreduced products `x[i] * 1`', start)
s = s[:start] + '''    pub unsafe fn mul_acc2(&mut self, x0: __m512i, y0: __m512i, x1: __m512i, y1: __m512i) {
        let lo0 = _mm512_clmulepi64_epi128::<0x00>(x0, y0);
        let lo1 = _mm512_clmulepi64_epi128::<0x00>(x1, y1);
        let hi0 = _mm512_clmulepi64_epi128::<0x11>(x0, y0);
        let hi1 = _mm512_clmulepi64_epi128::<0x11>(x1, y1);
        let sx0 = _mm512_xor_si512(x0, _mm512_shuffle_epi32::<0x4e>(x0));
        let sy0 = _mm512_xor_si512(y0, _mm512_shuffle_epi32::<0x4e>(y0));
        let sx1 = _mm512_xor_si512(x1, _mm512_shuffle_epi32::<0x4e>(x1));
        let sy1 = _mm512_xor_si512(y1, _mm512_shuffle_epi32::<0x4e>(y1));
        let middle0 = _mm512_clmulepi64_epi128::<0x00>(sx0, sy0);
        let middle1 = _mm512_clmulepi64_epi128::<0x00>(sx1, sy1);
        self.lo = _mm512_ternarylogic_epi64::<0x96>(self.lo, lo0, lo1);
        self.hi = _mm512_ternarylogic_epi64::<0x96>(self.hi, hi0, hi1);
        self.mid = _mm512_ternarylogic_epi64::<0x96>(self.mid, middle0, middle1);
    }
''' + s[end:]
old = '''        self.lo = _mm512_xor_si512(self.lo, _mm512_maskz_mov_epi64(0x55, x));
        self.mid = _mm512_xor_si512(self.mid, _mm512_bsrli_epi128::<8>(x));'''
new = '''        self.lo = _mm512_xor_si512(self.lo, _mm512_maskz_mov_epi64(0x55, x));
        // (x.lo + x.hi) * (1 + 0), with the upper qword zero.
        let sum = _mm512_xor_si512(x, _mm512_bsrli_epi128::<8>(x));
        self.mid = _mm512_xor_si512(self.mid, _mm512_maskz_mov_epi64(0x55, sum));'''
assert old in s
s = s.replace(old, new)
old = 'unsafe { ghash_reduce_acc_x4(self.lo, self.mid, self.hi) }'
assert old in s
s = s.replace(old, '''unsafe {
            let cross = _mm512_ternarylogic_epi64::<0x96>(self.mid, self.lo, self.hi);
            ghash_reduce_acc_x4(self.lo, cross, self.hi)
        }''')
old = 'let mid = xor4_lanes(self.mid);'
assert old in s
s = s.replace(old, '''let cross = _mm512_ternarylogic_epi64::<0x96>(self.mid, self.lo, self.hi);
            let mid = xor4_lanes(cross);''')
s = s.replace('    mid: __m512i,\n}', '    // Sum of (x.lo + x.hi) * (y.lo + y.hi), not the cross term.\n    mid: __m512i,\n}', 1)
start = s.index('    /// Bit-identical to `mul_acc(x0, y0); mul_acc(x1, y1)`')
end = s.index('    /// # Safety', start)
s = s[:start] + '''    /// Bit-identical to two calls to `mul_acc`, with six carry-less products
    /// and three ternary XOR updates. The Karatsuba correction remains
    /// deferred until `reduce_lanes` or `fold`.
    ///
''' + s[end:]
start = s.index('    /// With `y = F128::ONE')
end = s.index('    /// # Safety', start)
s = s[:start] + '''    /// In the Karatsuba representation, `lo = x.lo`, `hi = 0`, and
    /// `mid = x.lo + x.hi`. Masking and shifting replace multiplication;
    /// the deferred correction recovers the same raw polynomial product.
    ///
''' + s[end:]
# Keep every unchanged line's original newline convention.
base_lines = original.splitlines(keepends=True)
new_lines = s.splitlines()
base_keys = [line.rstrip('\r\n') for line in base_lines]
result = []
for tag, i, j, k, l in difflib.SequenceMatcher(None, base_keys, new_lines, autojunk=False).get_opcodes():
    result.extend(base_lines[i:j] if tag == 'equal' else [line + '\n' for line in new_lines[k:l]])
s = ''.join(result)
s += '''
#[cfg(all(test, target_feature = "avx512f", target_feature = "vpclmulqdq"))]
mod deferred_karatsuba_tests {
    use super::*;

    fn next(seed: &mut u64) -> u64 {
        *seed = seed.wrapping_add(0x9e3779b97f4a7c15);
        let mut x = *seed;
        x = (x ^ (x >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        x = (x ^ (x >> 27)).wrapping_mul(0x94d049bb133111eb);
        x ^ (x >> 31)
    }

    fn values(seed: &mut u64) -> [F128; 4] {
        core::array::from_fn(|_| F128::new(next(seed), next(seed)))
    }

    #[test]
    fn deferred_karatsuba_accumulates_mixed_operations_exactly() {
        let mut seed = 0xf10c_cafe_7349_8283;
        for count in [0, 1, 2, 3, 7, 16, 31, 257, 1024] {
            // Compare both lane reductions and the unreduced horizontal sum
            // against the portable polynomial implementation, not a SIMD twin.
            unsafe {
                let mut acc = WideGhashX4::zero();
                let mut lanes = [F256Unreduced::ZERO; 4];
                for i in 0..count {
                    let a = values(&mut seed);
                    let b = values(&mut seed);
                    let c = values(&mut seed);
                    let d = values(&mut seed);
                    let av = f128x4_loadu(a.as_ptr());
                    let bv = f128x4_loadu(b.as_ptr());
                    if i % 3 == 0 {
                        acc.mul_acc_one(av);
                    } else if i % 3 == 1 {
                        acc.mul_acc(av, bv);
                    } else {
                        acc.mul_acc2(av, bv, f128x4_loadu(c.as_ptr()), f128x4_loadu(d.as_ptr()));
                    }
                    for lane in 0..4 {
                        let rhs = if i % 3 == 0 { F128::ONE } else { b[lane] };
                        lanes[lane] ^= super::super::software::ghash_mul_unreduced(a[lane], rhs);
                        if i % 3 == 2 {
                            lanes[lane] ^= super::super::software::ghash_mul_unreduced(c[lane], d[lane]);
                        }
                    }
                }
                let got = f128x4_extract(acc.reduce_lanes());
                assert_eq!(got, lanes.map(F256Unreduced::reduce), "count={count}");
                let raw_sum = lanes.into_iter().fold(F256Unreduced::ZERO, |a, b| a ^ b);
                assert_eq!(acc.fold(), raw_sum, "unreduced count={count}");
            }
        }
    }

    #[test]
    fn deferred_karatsuba_handles_every_basis_bit() {
        for i in 0..128 {
            for j in 0..128 {
                let x = F128::new(if i < 64 { 1 << i } else { 0 }, if i >= 64 { 1 << (i - 64) } else { 0 });
                let y = F128::new(if j < 64 { 1 << j } else { 0 }, if j >= 64 { 1 << (j - 64) } else { 0 });
                let a = [x, F128::ZERO, x, F128::ONE];
                let b = [y, y, F128::ONE, y];
                unsafe {
                    let mut acc = WideGhashX4::zero();
                    acc.mul_acc(f128x4_loadu(a.as_ptr()), f128x4_loadu(b.as_ptr()));
                    let got = f128x4_extract(acc.reduce_lanes());
                    let expected = core::array::from_fn(|lane| super::super::software::ghash_mul(a[lane], b[lane]));
                    assert_eq!(got, expected, "basis {i},{j}");
                }
            }
        }
    }
}
'''
p.write_bytes(s.encode())
print('Applied deferred Karatsuba to', p.relative_to(root))

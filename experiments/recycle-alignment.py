#!/usr/bin/env python3
"""Apply one allocator experiment to an otherwise pristine Flock checkout."""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
p = root / 'crates/flock-prover/src/recycle_alloc.rs'
original = p.read_bytes()
nl = b'\r\n' if b'\r\n' in original else b'\n'

def lines(s: str) -> bytes:
    return s.encode().replace(b'\n', nl)

old = lines('''fn recyclable(layout: &Layout) -> bool {
    layout.size() >= RECYCLE_MIN && layout.align() <= MAX_ALIGN
}''')
new = lines('''fn recyclable(layout: &Layout) -> bool {
    // With alignment enabled every recycled pointer is already 64-aligned,
    // irrespective of the caller's original alignment. SIMD allocations can
    // therefore share these exact-size classes without a second class key.
    // In the raw-System mode retain the original <=16 alignment boundary.
    layout.size() >= RECYCLE_MIN
        && (layout.align() <= MAX_ALIGN || (layout.align() <= 64 && align64_enabled()))
}''')
assert original.count(old) == 1, 'unexpected recyclable implementation'
updated = original.replace(old, new, 1)
old_doc = lines('''// glibc/mimalloc and the macOS allocator provide at least 16-byte alignment
// at these sizes; layouts requiring larger alignment bypass the recycler.''')
new_doc = lines('''// With align64 enabled, every pooled pointer is 64-aligned, including
// allocations originally requested with a smaller alignment. Without it,
// only the original <=16-byte-aligned layouts may enter these size classes.
// Layouts requiring more than 64-byte alignment always bypass the recycler.''')
assert updated.count(old_doc) == 1, 'unexpected allocator safety documentation'
updated = updated.replace(old_doc, new_doc, 1)
anchor = lines('''mod tests {
''')
assert updated.count(anchor) == 1
new_tests = lines('''mod tests {
    /// Mixed alignments exercise the same exact-size freelist. Run this test
    /// both normally and with FLOCK_NO_ALIGN64=1 in a separate process.
    #[test]
    fn mixed_alignment_alloc_zeroed_and_realloc_contract() {
        use super::RecycleAlloc;
        use std::alloc::{GlobalAlloc, Layout};
        let allocator = RecycleAlloc;
        for align in [8, 16, 32, 64, 128, 64, 32, 16, 8] {
            let size = 32 * 1024 + 13 * 64;
            let layout = Layout::from_size_align(size, align).unwrap();
            // SAFETY: all allocations are checked, initialized before reads,
            // and deallocated exactly once with the corresponding layout.
            unsafe {
                let p = allocator.alloc_zeroed(layout);
                assert!(!p.is_null());
                assert_eq!(p as usize % align, 0);
                assert!(std::slice::from_raw_parts(p, size).iter().all(|x| *x == 0));
                std::ptr::write_bytes(p, 0xA5, size);
                let q = allocator.realloc(p, layout, size * 2);
                assert!(!q.is_null());
                assert_eq!(q as usize % align, 0);
                assert!(std::slice::from_raw_parts(q, size).iter().all(|x| *x == 0xA5));
                allocator.dealloc(q, Layout::from_size_align(size * 2, align).unwrap());
            }
        }
    }

    #[test]
    fn concurrent_mixed_alignment_recycling_keeps_live_blocks_distinct() {
        use super::RecycleAlloc;
        use std::alloc::{GlobalAlloc, Layout};
        std::thread::scope(|scope| {
            for worker in 0..8usize {
                scope.spawn(move || {
                    let allocator = RecycleAlloc;
                    for iteration in 0..24usize {
                        let align = 8usize << ((worker + iteration) % 4);
                        let size = 32 * 1024 + 29 * 64;
                        let layout = Layout::from_size_align(size, align).unwrap();
                        let pattern = (worker * 24 + iteration + 1) as u8;
                        // SAFETY: each thread owns its live allocation; the
                        // freelist lock transfers ownership only on dealloc.
                        unsafe {
                            let p = allocator.alloc(layout);
                            assert!(!p.is_null());
                            assert_eq!(p as usize % align, 0);
                            std::ptr::write_bytes(p, pattern, size);
                            std::thread::yield_now();
                            assert!(std::slice::from_raw_parts(p, size)
                                .iter().all(|x| *x == pattern));
                            allocator.dealloc(p, layout);
                        }
                    }
                });
            }
        });
    }
''')
updated = updated.replace(anchor, new_tests, 1)
p.write_bytes(updated)
print('Changed only crates/flock-prover/src/recycle_alloc.rs; retained original newline convention.')

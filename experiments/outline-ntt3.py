#!/usr/bin/env python3
"""Apply one compiler-boundary change to the pristine public Flock source."""
from pathlib import Path
import hashlib
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
source_sha = '1b55c6ee2c9cae3c807489293199760e5e21d52b'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == source_sha
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root).strip()
relative = 'crates/flock-core/src/ntt/additive_ntt_f128/kernels/x86_64.rs'
path = root / relative
before = path.read_bytes()
old = b'#[inline]\n#[target_feature(enable = "avx512f,vpclmulqdq")]\nunsafe fn butterfly_fused_3layer_rows_impl'
new = b'''// Keep specialization bodies separate. Inlining every DIET/LOW/NNC arm
// into one dispatcher gives all calls its union-sized stack frame and makes
// the hot kernel share an instruction footprint with unused alternatives.
// This preserves every arithmetic operation and all dispatch preconditions.
#[inline(never)]
#[target_feature(enable = "avx512f,vpclmulqdq")]
unsafe fn butterfly_fused_3layer_rows_impl'''
assert before.count(old) == 1
path.write_bytes(before.replace(old, new))
assert subprocess.check_output(['git', 'diff', '--name-only'], cwd=root, text=True).strip() == relative
print('OUTLINED_FILE_SHA256=' + hashlib.sha256(path.read_bytes()).hexdigest())

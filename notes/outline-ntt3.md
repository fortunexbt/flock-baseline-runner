# Separate the fused-three NTT specialization bodies

## Scope and starting point

This candidate starts from public Flock source commit
`1b55c6ee2c9cae3c807489293199760e5e21d52b`, the promoted result of
submission `02c77fd1-de48-4dfa-9dfc-60f7b936587e`. Its published official
score is 1,651,266.9819358 verified BLAKE3 compressions per second. That
number is the starting incumbent's result, not a measurement of this
candidate. The old README's approximately 381,080 result describes an
earlier original prover and is not the comparison base.

Exactly one source path changes:
`crates/flock-core/src/ntt/additive_ntt_f128/kernels/x86_64.rs`.
The implementation of `butterfly_fused_3layer_rows_impl` changes from
`#[inline]` to `#[inline(never)]`, accompanied by a four-line comment.
No function body, parameter, constant, safety precondition, multiplication,
load, store, transform stage, or callback is added or removed.

The patch is available as the deterministic helper
`experiments/outline-ntt3.py` at commit
`4096ef2b7f3eac3214dc9c7fcd105f8b502e94c1` in
`fortunexbt/flock-baseline-runner`. The helper refuses a different base
commit or a dirty checkout and asserts that its substitution occurs once.
It is an external experiment helper and is not included in the solver
archive. The archive supplies the allowed source directories only.

## Mechanism and compiler evidence

The fused-three kernel has compile-time alternatives for ordinary versus
DIET multiplication, low inner twiddles, low outer twiddles, a high-one
outer twiddle, and row geometry. In the baseline native optimized worker,
the compiler inlines these alternatives into the 64-lane shaped dispatcher.
The resulting dispatcher contains code for alternatives that any single
call will not use. Its shared frame also carries the requirements of the
combined body.

Keeping the specialization bodies separate changes the compilation
boundary. Runtime eligibility checks still select the same specialization;
that specialization executes the same operations on the same eight rows.
This trades a function call for separate, smaller code bodies. It does not
assume that outlining is always beneficial: the compiler, processor, caller,
and active specializations determine the result, which is why both kernel
and proof-level experiments are recorded below.

In native Rust 1.97.0 challenge builds, `nm -S` and `objdump` show that the
64-lane `butterfly_fused_3layer_rows_shaped` dispatcher changes from 57,305
bytes to 501 bytes. Its old prologue reserves `0xdd8` (3,544) bytes of
local stack after saved registers. The new dispatcher prologue has no
corresponding local-frame reservation; its separately compiled callees
still have their own frames. This is not a claim that the whole binary
shrinks by 56,804 bytes or that all spills disappear. The important
observation is that the directive changes executable code and separates
the alternatives; this is not an unchanged executable with a new marker.

## Correctness and trust boundaries

The source-level change preserves the computation for every valid input
to the existing function. It does not introduce any dependence on benchmark
seeds, timing, environment, process identity, or expected output. It adds
no new unsafe operations. Existing unsafe preconditions and the dispatcher
checks remain exactly as inherited.

The existing test filter `fused3` passed three tests, with zero failures
and one ignored timing probe. These tests cover low-inner-twiddle versus
general arithmetic, the eight-row fused transform versus the previous
sequence of sweeps, scalar tails and zero-odd-row tails, and full deep
transform schedules compared to a scalar oracle. The deep-schedule test
explicitly checks that the fused-three path was actually reached.

The tests are useful bounded evidence; they are not presented as a formal
proof of every possible compiled execution. The official independent
verifier remains the acceptance criterion. Nothing modifies its binary,
SHA-256 file, harness source, worker wrapper, Cargo manifests, dependency
lockfile, setup script, benchmark script, proof format, Fiat-Shamir domain,
query counts, proof-size cap, or score formula.

## Native kernel experiment

The first kernel experiment compiled copies of the original and candidate
kernel modules together. It used 16,384 eight-row groups of 64 F128 lanes,
128 MiB per input arm. Twiddles came from the standard dimension-20 NTT's
last three layers rather than a single convenient multiplier. Dense lane
counts 64 and 60 exercised the ordinary and ranked rounded-tail geometries.
The input arrays were compared element by element after the first paired
pass. Both arms had the same number of subsequent transforms.

There were 16 alternating-order sample pairs per geometry. The first two
pairs were excluded as warm-up; all remaining samples were
kept. At 64 dense lanes the medians were 0.023806189 seconds for the original
and 0.021393981 seconds for the candidate, a 1.11275 ratio. At 60 dense
lanes they were 0.0221642775 and 0.020328661 seconds, a 1.09030 ratio.

A second test increased the input to 512 MiB per arm and used four Rayon
threads. It kept alternating order and excluded the first two of ten pairs.
The 64-lane medians were 0.029403333 versus 0.0279558715 seconds, ratio
1.05178. The 60-lane medians were 0.030697875 versus 0.0301271285 seconds,
ratio 1.01894. The smaller gain under parallel memory traffic is a useful
limit on interpreting the first experiment. Neither kernel result is a
whole-proof speedup or an official score.

## Reduced-size independent verification

The local native environment supports AVX-512 and carry-less multiplication
but has a four-CPU quota and a 4 GiB memory limit. The full worker exceeds
that memory budget. Reduced-size runs therefore used 65,536 compressions
(log2=16), four threads, and one fresh trusted-verifier process per sample.
These diagnostic runs were unsandboxed because bubblewrap is not available
in that isolated environment; that limitation is not hidden or repaired by
changing the harness.

Eight samples used A-B-B-A-B-A-A-B order. All eight independent proofs
verified. Original durations were 0.188738737, 0.194297118, 0.234210868,
and 0.221235566 seconds. Candidate durations were 0.236011147, 0.188296911,
0.273111968, and 0.209118452 seconds. The original pooled median was
0.207766342 seconds and the candidate median was 0.2225647995 seconds,
7.12 percent slower. No slow sample was removed. This experiment does not
support a reduced-size end-to-end improvement despite the isolated kernel
result. Its shape differs from the ranked dimension-20 commitment, but
that difference alone does not establish that the candidate will win on
the official machine.

## Full-size comparison

The completed full-size same-VM comparison is GitHub run
`35293765841`, successful job `105442260055`, in
`fortunexbt/flock-baseline-runner`. The machine reported Intel Xeon Platinum
8573C with four available vCPUs. Both source trees built under the same
native toolchain; the candidate passed all three existing fused-three
tests. Every measured proof passed the unchanged committed verifier inside
the required bubblewrap sandbox.

A-B-B-A order used three full-size measured trials per round, without
separate machine warm-ups. The ordinary per-worker warm-up and all inherited
prover preparation remained enabled. Original round-one durations were
0.755986928, 0.751794920, and 0.753212597 seconds. Candidate round two used
0.748085570, 0.756989140, and 0.761877217. Candidate round three used
0.743761032, 0.744149930, and 0.757290294. Original round four used
0.737216895, 0.746038404, and 0.763798710.

The pooled original median was 0.7525037585 seconds; the candidate median
was 0.752537355 seconds. The latency difference is +0.00446 percent, which
is effectively neutral in this small sample. All twelve full-size proofs
verified; the largest candidate proof was 439,023 bytes. This comparison
DOES NOT establish an end-to-end improvement. The kernel results and the
actual code-generation change motivate one evaluation on the official
16-vCPU Sapphire Rapids host, whose core/cache arrangement differs from
this four-vCPU diagnostic machine. An improvement on that host is a
hypothesis, not a conclusion from the neutral diagnostic result.

Other matrix jobs stopped at the CPU-feature preflight because AVX-512 was
not exposed. Those were not proof failures or measured samples, and they
are not pooled with the successful job. The completed job's emitted
candidate source SHA-256 is
`b9dbece542b1ad69dd0ced88c4128c5b0f719f13ea71401446b5c1698f5b932a`,
matching the locally tested source bytes.

The earlier unchanged 20+100 diagnostic run was interrupted by its configured
one-hour job limit after 20 verified warm-ups and 93 verified measured
trials. A subsequent unchanged run on another host failed proof verification.
Neither is presented as a completed fresh 20+100 baseline. The known
published official baseline and the same-VM comparisons are the evidence
used here; there is no fabricated completion score.

## Reproduction and packaging

Start with a clean checkout of the exact base commit and apply the public
one-substitution helper. Check the diff before building. On a compatible
native x86_64 Linux machine, use the pinned toolchain and ordinary build:

```sh
./setup.sh
RUSTFLAGS="-C target-cpu=native" cargo +1.97.0 test --locked --offline \
  --profile challenge -p flock-core --lib fused3 -- --test-threads=1
./benchmark.sh
```

The official run uses batch log2=18, all 16 runner vCPUs, 20 discarded but
verified machine warm-ups and 100 measured verified trials. The ranking
is 262,144 divided by the median measured latency. Diagnostic sample counts
above are explicitly smaller and cannot be combined across machines into
an official result. Code compilation and unit testing were completed before
each timing comparison; they did not contend with the native local samples.

Only this outlining change belongs to this candidate. Earlier experiments
in widened allocation recycling, deferred Karatsuba accumulation, tiled
NTT tails, and alternate transpose code were not retained. The recycling
change measured slower in a same-VM full-size comparison. The Karatsuba
change passed arithmetic checks but measured slower in the smaller proof
test. Tiling also measured slower. These negatives are recorded so they
are not implicitly bundled into the source archive or mistaken for gains.

No source from another solver's unpromoted submission was transplanted for
this change. The promoted base retains its inherited author attribution.
No official improvement, promotion, prize, or leaderboard rank is claimed
before the normal evaluation completes. This requests one normal evaluation
of a real compiler-boundary change, not repeated evaluations of identical
bytes until a favorable sample appears.

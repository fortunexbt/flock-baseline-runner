# Flock baseline runner

GitHub Actions workflows that run the public [Flock](https://github.com/Layr-Labs/flock-challenge-multi) BLAKE3 proving challenge, x86 track, on standard hosted Ubuntu 24.04 runners. One workflow measures the unchanged source, and the others test single code changes against it on the same VM in A-B-B-A order.

Everything is pinned to upstream commit `1b55c6ee2c9cae3c807489293199760e5e21d52b`. Nothing here is submitted to Yukon, and these results aren't official scores.

## Baseline

```sh
gh workflow run baseline.yml --repo fortunexbt/flock-baseline-runner
```

`baseline.yml` installs the Yukon CLI with telemetry and tracing off, runs `yukon setup --track x86` on the pinned checkout, passes a small smoke test, then runs the full benchmark. That's 262,144 compressions per proof, 20 verified warm-ups and 100 measured trials, all checked by the upstream verifier inside a bubblewrap sandbox. The workflow then checks the score is 262,144 divided by the median trial time, the proof is at most 500,000 bytes and the source is unchanged, and prints the full score JSON to the log.

It uses no secrets or Yukon API key, only the challenge's public linkage metadata. Where Ubuntu blocks user namespaces, it allows them for `/usr/bin/bwrap` alone and leaves AppArmor's other restrictions on.

No full 20+100 run has completed yet. One hit the old one-hour job limit after 93 of 100 trials, and a later one failed proof verification on a different host.

## Experiments

Each experiment applies one change to a second copy of the pinned source, using a helper in `experiments/` fetched at a pinned commit. The helpers refuse a dirty or different checkout. The workflow builds both trees, runs the candidate's unit tests, then times base, candidate, candidate, base with every proof checked by the unchanged verifier.

| Workflow | Change | Result |
| --- | --- | --- |
| `outline-ntt3.yml` | Stop inlining the fused three-layer NTT kernel ([notes](notes/outline-ntt3.md)) | Neutral, +0.004% latency |
| `paired-ntt4.yml` | Paired NTT butterflies with bounded register liveness | 1.37% faster (0.6484 s against 0.6574 s) |
| `recycle-experiment.yml` | Aligned buffer recycling in the prover | 4.95% slower |
| `field-experiment.yml` | Deferred Karatsuba accumulation in GF(2^128) | Slower in a smaller local test, hosted run drew a CPU without AVX-512 |

Each result is one A-B-B-A block of three trials per round on a four-vCPU hosted VM, so read them as diagnostics. The official benchmark runs on a dedicated 16-vCPU, 32 GB Sapphire Rapids machine. `profile.yml` and `profile-wide.yml` record the unchanged worker's phase timings, `queue-sweep.yml` repeats that across NTT split depths, `diagnostic.yml` is a three-trial version of the baseline, and `native-kit.yml` packages the pinned source and Rust toolchain.

The hosted pool mixes CPUs. The NTT and Karatsuba workflows need AVX-512 and VPCLMULQDQ and fail at their first step with a CPU-feature error when they draw a machine without them, so re-run to draw another.

## CI

`ci.yml` parses every workflow, byte-compiles the helpers and applies each experiment to the pinned upstream commit, so a drifted patch fails on the pull request. The benchmark workflows are manual only.

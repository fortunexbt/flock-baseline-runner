# Flock baseline runner

This repository runs the **unchanged** Flock x86 challenge on a standard GitHub-hosted Ubuntu 24.04 x86_64 runner. It does not submit to Yukon or modify the challenge source.

Source: `Layr-Labs/flock-challenge-multi`, commit `1b55c6ee2c9cae3c807489293199760e5e21d52b`.

## Run

```sh
gh workflow run baseline.yml --repo fortunexbt/flock-baseline-runner
```

The workflow installs Yukon and its skill, reads the skill before and after restoring the pinned checkout, and runs `yukon setup --track x86`. It requires bubblewrap, first verifies a small smoke test, then runs the complete baseline: 262,144 compressions per proof, 20 discarded verified warm-up trials, and 100 measured verified trials. The checksum-pinned verifier controls correctness and timing. The workflow independently checks the final score formula, proof-size limit, trial counts, and unchanged source revision.

No Yukon API key or other repository secret is supplied. Setup and run use only the public linkage metadata from the original Yukon clone. Telemetry and transcript collection are disabled. The Ubuntu namespace compatibility profile applies only to `/usr/bin/bwrap` in the disposable runner; system-wide AppArmor restrictions remain enabled. The protected benchmark scripts and verifier are unchanged.

Execution is manual-only, with one baseline at a time. No paid runner sizes, artifact uploads, caches, or persistent external machines are configured. Scores and complete trial data are printed in workflow logs.

## Interpretation

These are diagnostic measurements on GitHub-hosted hardware, **not official Yukon ranked scores**. The official benchmark uses a dedicated 16-vCPU, 32-GB Intel Sapphire Rapids runner. Hosted machines can differ between workflow runs. A future optimization comparison should run both baseline and candidate on the same allocated machine, keep workload and verification identical, and assess variation rather than compare unrelated hosted runs.

No optimization has been made in the benchmark checkout. The experiments below are applied to a separate copy of the pinned source and never submitted.

## Experiments

Each experiment applies one small change to the pinned source with a deterministic helper in `experiments/` (a patch, or a script that refuses a dirty or different checkout). The workflow then runs the unchanged verifier on a pristine tree and the changed tree on the same VM in A-B-B-A order.

| Workflow | Change |
| --- | --- |
| `outline-ntt3.yml` | Stop inlining the fused three-layer NTT kernel (`notes/outline-ntt3.md`) |
| `paired-ntt4.yml` | Paired butterflies with bounded register liveness (`experiments/paired-ntt4.patch`) |
| `field-experiment.yml` | Deferred Karatsuba accumulation in GF(2^128) |
| `recycle-experiment.yml` | Aligned buffer recycling in the prover |
| `queue-sweep.yml`, `profile*.yml`, `diagnostic.yml`, `native-kit.yml` | Queue depth, worker profiles and development-kit checks |

The experiment workflows need AVX-512 and VPCLMULQDQ, which only some GitHub-hosted machines have. A job that draws a machine without them fails at the first step with a CPU-feature error. Re-run it to draw another machine. Results are in each run's logs and are not official scores.

## CI

`ci.yml` runs on every push and pull request. It parses the workflows, compiles the helpers, and applies every experiment to the pinned upstream commit, so a drifted patch fails fast. The benchmark workflows themselves are manual and are not run by CI.

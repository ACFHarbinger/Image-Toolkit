# ASP deterministic rerun check — 2026-08-24

Authorized small check after `19fdb4c`; no corpus run. Each case ran twice in
a fresh process and an isolated copy of the inputs. Both repetitions used
`ASP_DETERMINISTIC=1`, seed 1729, one OpenCV/Torch/interop thread, and all
OpenMP/BLAS environment caps at one.

| case | routing, both runs | selection / dedup / edges | output SHA-256 |
|---|---|---|---|
| `asp_test28` | SCANS, `affine_invalid:min_gap=19.9941px < 20.3731px` | 143→22 / 22 / 44 | `5bb50fbc…b1df65` |
| `asp_test82` | SCANS, `disconnected_edge_graph` | 156→23 / 17 / 26 | `c8ef2a0a…e4449` |
| `asp_test67` | Raw ASP | 105→15 / 12 / 11 | `5a223307…8e011` |

All final PNG hashes match per case. The saved result JSONs capture the same
runtime record: RTX 4080 Laptop GPU; OpenCV/Torch/interop threads `1/1/1`;
cuDNN deterministic true; benchmark false; deterministic algorithms enabled;
all configured RNGs seed 1729.

`torch.median(..., indices)` warns that it has no deterministic CUDA
implementation, and BiRefNet's batch path OOMed then used the established
per-frame fallback on the second isolated pass. Neither changed selection,
routing, or final output in this check. The determinism gate is passed for
this three-case sample; it does not establish equivalence with the old frozen
corpus, which used a different runtime configuration.

Artifacts are temporary isolated outputs under `/tmp/asp-determinism-PvjBdZ`;
the six benchmark JSON records are in `submodules/ASP/backend/benchmark/output/`.

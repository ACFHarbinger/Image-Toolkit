# Codex GIF speed integration review — 2026-10-31

Reviewed `feat/gif-speed` at `117e26b5c`, integrated with current main and A5 `034e7354d` on `feat/gif-speed-codex`.

Fixed before landing:
- Preserve all three parallel-decoder eligibility regressions from main, including first-frame restore and opaque-canvas disposal.
- Multi-GPU scheduler now prefers B2's fused `scale_and_index_batch`. B4's adapter ignored its prefetched device tensor and downloaded/reuploaded RGBA through separate scale/index calls; it must not replace the fused path.
- CPU-only tests accept unavailable CUDA instead of requiring a held-device reason; normalize fallback text assertion.
- Remove duplicate summary reset from merge integration.

Validation used targeted test files with `CUDA_VISIBLE_DEVICES=''`, never a full directory or whole-file benchmark. Decoder/scheduler/overlap/process encoder/GPU-batch group: 34 passed, 4 CUDA tests skipped. Lease arbiter: 47 passed. Core GIF and media routes: 26 passed. Qt cancellation: 5 passed. Palette, writer, stream, progress and Lanczos checked separately. Ruff and diff whitespace checks pass.

Limits: real CUDA execution, multi-card throughput, full-file memory/cancellation behavior and performance budgets remain unverified in this review. No whole-file benchmark authorization inferred. B4's true pinned-copy/compute overlap remains unfinished; the landed scheduler uses fused B2 calls for real sessions. This landing does not close performance acceptance for F1 or the deferred neural streaming work.

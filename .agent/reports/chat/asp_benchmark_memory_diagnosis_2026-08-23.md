# P2 benchmark memory diagnosis — 2026-08-23

## Observation

- Before `asp_test21`: benchmark RSS was 0.75 GiB and host RAM was 69.6% used.
- Immediately before canonical ASP: RSS was 0.88 GiB and host RAM was 70.2%.
- During/after the BiRefNet portion the host reached 77% (~24 GiB used, 6.7 GiB
  available). The process was stopped; host availability recovered to ~10 GiB
  and GPU use to 111 MiB.
- `asp_test21/output/panorama.png` and `run_output.png` were written. Missing
  `raw_asp.png` means the result was non-Raw ASP, but termination occurred
  before benchmark result/registration telemetry persistence.

This is a roughly 2–2.5 GiB transient on an already loaded workstation, not
evidence of a 32 GiB per-dataset or cross-dataset leak. At the same time,
`rust-analyzer` (~2.5 GiB), `cloudcode_cli` (~2.0 GiB), and IDE/browser/agent
processes already consumed substantial host memory.

## Confirmed pressure defect

`BiRefNetWrapper.get_mask_batch()` constructs and retains a CUDA tensor for
every selected frame in `tensors` before it divides those tensors into chunks.
The advertised batch cap therefore bounds only model inference, not input
residency. It also retains all full-resolution float32 `soft_masks` before
converting them to binary masks. For 18 1080p frames this is hundreds of MiB;
it is a real avoidable peak but does not by itself explain 32 GiB.

## Missing attribution

The benchmark records RSS before/after the entire canonical call, but no
checkpoint immediately after Stage 4 masking. The interrupted run therefore
cannot separate BiRefNet model load, input tensors, activations, and later
pipeline stages.

## Implemented diagnostic slice

1. BiRefNet preprocessing and binary-mask conversion now stream per inference
   chunk, releasing the chunk tensors and predictions before the next chunk.
2. Stage 4 records process RSS plus CUDA allocated/reserved memory before and
   after masking; the benchmark persists that and registration telemetry to
   `canonical_evidence.json` immediately after canonical ASP returns.
3. Retry only after host availability is materially higher. Treat an increasing
   post-mask or post-dataset RSS across isolated runs as leak evidence; do not
   infer it from the shared host percentage alone.

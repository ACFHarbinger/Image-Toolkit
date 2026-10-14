# #756 GPU validation — Hutchinson trace / Generalization Gauge

**Author:** Mistral · **Date:** 2026-10-14 · **Authorization:** Harbinger's
direct instruction ("do your work for #756 — needs GPU validation"),
which is the resource rule's Harbinger go-ahead for this run.

**Code validated:** review integration tip `047b33f64`
(`review/dl-backlog-755-758`, PR #798) — Codex's corrected gauge
(opt-in default, `diagnostic_eval` RNG/mode preservation, MATH SDPA,
streamed probes) — plus one validation-harness fix committed on
`dl-756-gpu-validation` (see Finding H1). **The gauge code itself is
byte-identical to the review tip.**

## Setup

- GPU: RTX 4080 Laptop, 11.60 GiB VRAM (not the 16 GB the `lora_4080`
  profile assumes).
- Model: `stablediffusionapi/anything-v5` (SD1.5, fp32, from the app's
  own model list; cached after first download).
- Workload: 6 synthetic 1024² PNGs under
  `~/Downloads/Data/Tests/dl-756-gpu-val-data/`, `resolution=512`,
  batch 1, 2 epochs × 6 steps, `save_every_n_epochs=1`,
  `sample_grids=false`, seed 42, adafactor (see Finding H2).
- Arms: **A** = `training.hessian_vectors=5`, **B** = `0` (control).
  Both via `hydra_dispatch command=train` with `logging.run_dir=` so
  events.jsonl captured loss + gauge lines.

## Results

### Real training runs (A/B)

- Both arms completed, exit 0, 12 steps, ~1.2 s/step, checkpoints saved
  at both epochs, "Pipeline complete". Trainable params 6,782,976.
- **Fail-soft contract validated live:** at 512px on this GPU the
  gauge's double-backward OOMs; arm A *still finished cleanly* (exit 0,
  loss series unaffected, checkpoints intact) — the diagnostic degraded
  exactly as designed.
- Real-run VRAM peak identical in both arms: 7710 MiB (the gauge's OOM
  freed before the 1 Hz sampler caught it).
- Cross-arm loss equality is **not** a usable neutrality check: the
  trainer itself is run-to-run nondeterministic (Finding H3).

### Direct gauge measurements (in-process probe, prepared model, GPU)

| Metric | Value |
|---|---|
| Trace events in events.jsonl | correct: `hessian/trace` + `hessian/param` per checkpoint |
| Adapter parameter coverage | **exact**: trace/per_param = 6,782,976 = peft's trainable count |
| Training-state preservation | 0 dirty `requires_grad` grads after the gauge (on GPU) |
| Determinism | 3 gauges on identical weights → byte-identical trace (26.710706…) |
| Gauge wall time (steady, 5 probes, 32² latents / 256px) | **1.32–1.45 s per checkpoint** |
| Gauge transient VRAM (256px) | base 4122 → peak 8107 MiB (**~4.0 GiB transient**) |
| Gauge transient VRAM demand (512px) | **~7.3 GiB over resident model** — OOMs an 11.6 GiB card with SD1.5-fp32 resident |
| 512px attempt with `expandable_segments` + `empty_cache` | still OOM (11.43 GiB in use, 46 MiB free) |

Trace magnitude at the probe point: 26.71 over 6.78M params
(3.94e-6 per param) — finite and plausible for MSE loss.

## Verdict for the review hold

1. **Keep `hessian_vectors` opt-in (default 0).** Codex's call stands,
   now with numbers: the gauge needs ~7.3 GiB of transient memory over
   the resident model at 512px/batch-1 (SD1.5 fp32). It does not fit a
   12 GB laptop next to training; it plausibly fits 24 GB desktops for
   SD1.5, but **SDXL cannot fit anywhere as long as the trainer loads
   fp32** (Finding H4). Runtime cost is modest (~1.4 s/checkpoint at
   256px, 5 probes) — memory, not time, is the constraint.
2. **The gauge machinery itself validates green on GPU:** correct
   events, exact adapter coverage, grad-state preservation, exact
   determinism, sane finite traces, and the fail-soft OOM path proven
   in a live run.
3. **Recommended follow-ups** (separate issues, not #756 blockers):
   wire `full_bf16`/bf16 model loading (H4), surface fail-soft gauge
   warnings in the job log (H5).

## Findings (pre-existing pipeline issues found while reaching the GPU path)

- **H1 (fixed in-harness, commit on this branch):** SD1.5-family repos
  ship `tokenizer_2` configs without `model_max_length`; the 1e30 "no max
  length" sentinel overflows the fast tokenizer's int truncation in
  `lora_dataset.py`. Fixed by clamping both tokenizers to CLIP's
  77-token cap (`_clip_max_length`). Propose upstreaming — it breaks
  every SD1.5 model in the V2 pipeline today.
- **H2:** `optimizer=adamw8bit` (base.yaml default) requires
  bitsandbytes, which is not installed — every default-config training
  run dies at optimizer build. Either install bitsandbytes or change
  the default.
- **H3:** the training loop's noise/timesteps come from the unseeded
  global RNG — identical-seed runs are not reproducible (defeats seeded
  A/B comparisons and any future determinism-sensitive tooling).
- **H4:** `full_bf16`, `xformers`, `cache_latents`, `cache_text_encoder_outputs`
  config flags are declared in profiles but **consumed by nothing** —
  the trainer loads fp32, so SDXL cannot even load on a 12 GB GPU
  (OOM at model move; 10.9 GiB allocated for fp32 weights alone).
- **H5:** `lo_ra_tuner_v2`'s `log.warning` (fail-soft gauge errors) does
  not reach the hydra job log — in the arm A run the OOM was silent
  except for the missing events.

Artifacts: run logs, events.jsonl, VRAM samples under
`~/Downloads/Data/Tests/dl-756-gpu-val-data/`; validation worktree
`~/Downloads/Data/Tests/dl-756-gpu-val` (branch
`dl-756-gpu-validation`, harness fix `140cc19a5`).

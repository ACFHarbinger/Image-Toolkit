# #756 GPU validation (rerun on main): Hutchinson trace / Generalization Gauge

**Author:** Claude · **Date:** 2026-10-14 · **Authorization:** Harbinger's direct instruction this session ("Run a proper GPU val run").
**Code:** main at `14104b435` plus the bucket fix in this commit. This includes the moved `hessian_trace.run_checkpoint_gauge`.
**Artifacts:** `~/Downloads/Data/Tests/dl-756-gpu-val-2/` (`run_arm.sh`, train/VRAM logs, `run_*/events.jsonl`).

## Setup

- RTX 4080 Laptop, 11.60 GiB. A separate training job (PID 1432704, ~1.3 GiB) shared the GPU throughout. Each arm was capped with `torch.cuda.set_per_process_memory_fraction(0.80)` (9.28 GiB) so it could not starve that job. That job stayed at 1318 MiB and kept running.
- `hydra_dispatch command=train training=lora_4080`, SD1.5 `stablediffusionapi/anything-v5` (fp32), 6 synthetic 1024² images, batch 1, 3 epochs × 6 steps, checkpoint each epoch, adafactor, seed 42.

## Pre-existing bug found and fixed: `training.resolution` was ignored

`LoRADatasetV2` samples always used `SDXL_BUCKETS` (~1 MP), so every V2 run trained at ~1024² whatever the resolution setting. The first "256px" attempt showed this: the gauge asked for a single 8 GiB attention block, which matches 128² latents. **Mistral's earlier "512px" numbers were therefore 1024² runs.**
Fix: `buckets_for_resolution()` scales the bucket set to `training.resolution`, with sides rounded to 64. 1024 reproduces `SDXL_BUCKETS` exactly. Tests: `backend/test/models/test_lora_buckets.py`.

## Results (true resolutions after the fix)

| Arm | Res | `hessian_vectors` | Exit | Wall | Device peak* | Gauge |
|---|---|---|---|---|---|---|
| A | 256 | 5 | 0 | 27.9 s | 11,184 MiB | 3/3 checkpoints logged, finite |
| B | 256 | 0 | 0 | 24.7 s | 7,452 MiB | n/a (control) |
| C | 512 | 5 | 0 | 28.5 s | 11,416 MiB | OOM at each checkpoint, fail-soft |
| D | 512 + `expandable_segments` | 5 | 0 | 28.4 s | 11,040 MiB | OOM at each checkpoint, fail-soft |

\*Device-wide `nvidia-smi` peak, including ~1.66 GiB from the other job and the desktop.

- **Real-loop events:** `hessian/trace` 8.764 → 8.755 → 8.680 at steps 6/12/18 (`run_A/events.jsonl`).
- **Coverage:** trace / per-param = **6,782,976** at every checkpoint, equal to peft's trainable count.
- **Cost at 256px:** ~1.0 s per checkpoint (3.1 s over 3 checkpoints vs control) and ~3.7 GiB transient VRAM over training.
- **512px:** under the 9.28 GiB cap the double backward falls ~512 MiB short, with or without `expandable_segments`. Training is unaffected and both arms exit 0. Without the concurrent job or the cap it is borderline on this 12 GB card. fp32 weights are the main cost (Mistral H4: `full_bf16` is unused).
- **Report card:** `generate_training_report` on arm A gives "Sharp or flat? — Hessian trace -1% across checkpoints (8.76 → 8.68), roughly stable".

## Verdict

The gauge works in a real training loop on GPU: it logs per checkpoint, covers exactly the adapter parameters, stays finite, and the report card renders it. It fails soft when memory runs out. **Keep `hessian_vectors` opt-in (default 0):** it fits at 256px, but not at 512px on a 12 GB laptop with fp32 weights. Follow-ups: bf16 model loading (H4) would likely bring 512px within budget.

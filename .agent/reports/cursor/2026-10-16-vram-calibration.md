# #758 VRAM estimate calibration — 2026-10-16

One in-process torch peak per job type on the RTX 4080 Laptop (12,282 MiB).
Hyperion Comfy was using 186 MiB at start and was not signalled. Peaks are
`torch.cuda.max_memory_allocated` for this process.

| Owner | Formula GiB | Measured GiB | Seed scale |
|---|---|---|---|
| upscale (ESRGAN anime_6B, 512², tile 400) | 1.05 | 1.50 | 1.43 |
| gan-train (AnimeGAN, 1 epoch, batch 1) | 0.93 | 2.08 | 2.24 |
| dataset-advisor (ResNet18 fallback) | 1.80 | 0.07 | 1.0 |
| lora-generate (anything-v5, 512×768, 4 steps, fp16) | 5.00 | 2.91 | 1.0 |
| lora-train (anything-v5, rank 16, 512², 1 epoch, 3 images) | 6.90 | 4.68 | 1.0 |

Scale is `max(1.0, measured/formula)`. Live `GpuLease.release` peaks can only
raise it. Comfy HTTP owners are not calibrated (other process). VLM is HTTP.
Not an OOM guarantee. JSON: `~/Downloads/Data/Tests/dl-758-vram-cal-data/peaks.json`.

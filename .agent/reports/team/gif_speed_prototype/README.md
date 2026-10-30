# GIF speed prototypes (reference only)

Throwaway scripts Claude used for the measurements in `../gif_resample_speed_ideas_2026-10-30.md` (§5.11, §5.12 and the checks in §6).
They are stored as `.txt` so linters and pytest ignore them. **Not production code**: copy ideas, not files, and do not import them.

| File | What it shows |
|---|---|
| `proto.py.txt` | GIF block scan, per-frame parallel LZW decode through Pillow's C decoder (bit-identical to sequential), disposal compositing with the uint32-view trick (1.0 ms/frame), 2-GPU scale + exact index with work stealing, Pillow C encode reused inside an own writer (needs `interlace=False`), and a verification pass. Modes: `check N WORKERS`, `full WORKERS [LIMIT]`. |
| `mgpu.py.txt` | Multi-GPU scaling test: dense `Wy @ x @ Wx^T` resample, batched masked 6-tap clamp, on-device dither and exact nearest-palette index, pinned uploads, one thread per device. |
| `verify_stages.py.txt` | Per-stage timing of the current pipeline pieces and the candidate replacements (sgemm + OpenCV clamp, BLAS-identity index, 7-bit LUT, Pillow C encode). |

Run with `PYTHONPATH=. python <file>` after copying to a scratch directory. They read the 326 MB test GIF under `~/Downloads/Data/Wallpapers/Other/`.
Honor the resource rules in `AGENTS.md`: do not run the whole-file modes yourself; Codex runs those.

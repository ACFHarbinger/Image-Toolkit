#!/usr/bin/env python3
"""
Build panorama_stages/ from source frames.
Uses AnimeStitchPipeline internals (including _filter_edges) to produce
correct affines, then saves all stage files for fast compositing iteration.
"""

import json
import os
import sys
import glob
import gc
import cv2
import numpy as np

sys.path.insert(0, os.path.expanduser("~/Repositories/Image-Toolkit"))
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import torch
from backend.src.animation.core.pipeline import AnimeStitchPipeline
from backend.src.animation.alignment.canvas import (
    _load_frames,
    _normalise_widths,
    _compute_canvas,
    _crop_to_valid,
)
from backend.src.animation.ingestion.masking import _compute_fg_masks
from backend.src.animation.alignment.matching import _pairwise_match
from backend.src.animation.alignment.bundle_adjust import _bundle_adjust_affine
from backend.src.animation.alignment.ecc import _ecc_refine
from backend.src.animation.rendering.rendering import _render_median
from PIL import Image

DIR = os.path.expanduser("~/Downloads/Data/New")
STAGE_DIR = f"{DIR}/panorama_stages"
os.makedirs(STAGE_DIR, exist_ok=True)

# ── Collect source frames ──────────────────────────────────────────────────────
all_pngs = sorted(glob.glob(f"{DIR}/*.png"))
frames_paths = [
    p
    for p in all_pngs
    if "panorama" not in os.path.basename(p)
    and "test_" not in os.path.basename(p)
    and "stage" not in os.path.basename(p)
]
print(f"Source frames ({len(frames_paths)}):")
for p in frames_paths:
    print(f"  {p}")
assert len(frames_paths) >= 2

# ── Stage 1-2: Load and normalise ───────────────────────────────────────────────
print("\nStages 1-2: load + normalise widths...")
frames = _load_frames(frames_paths)
N = len(frames)
frames = _normalise_widths(frames)
H, W = frames[0].shape[:2]
print(f"  {N} frames, {W}×{H}")
for i, f in enumerate(frames):
    cv2.imwrite(f"{STAGE_DIR}/stage02_normalised_frame{i:02d}.png", f)

# ── Stage 4: BiRefNet foreground masks ────────────────────────────────────────
print("Stage 4: BiRefNet foreground masks...")
try:
    from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper

    birefnet = BiRefNetWrapper()
    bg_masks = _compute_fg_masks(frames, birefnet)
    if torch.cuda.is_available():
        try:
            birefnet.offload()
        except Exception:
            pass
    del birefnet
    gc.collect()
    torch.cuda.empty_cache()
    print(f"  BiRefNet OK — {sum(m is not None for m in bg_masks)}/{N} masks")
except Exception as e:
    print(f"  BiRefNet failed ({e}), using None masks")
    bg_masks = [None] * N

for i, m in enumerate(bg_masks):
    img = m if m is not None else np.ones((H, W), dtype=np.uint8) * 255
    cv2.imwrite(f"{STAGE_DIR}/stage04_bgmask_frame{i:02d}.png", img)

# ── Stage 4.5: Background photometric normalisation (same as pipeline) ────────
print("Stage 4.5: background photometric normalisation...")
bg_frame_means = []
for i, (frame, mask) in enumerate(zip(frames, bg_masks)):
    if mask is not None:
        bg_px = frame[mask > 127].astype(np.float32)
        if len(bg_px) >= 1000:
            bg_frame_means.append(bg_px.mean(axis=0))
            continue
    bg_frame_means.append(None)

valid_means = [m for m in bg_frame_means if m is not None]
if len(valid_means) >= 3:
    ref_mean = np.median(valid_means, axis=0)
    for i in range(N):
        if bg_frame_means[i] is None:
            continue
        gain = np.clip(ref_mean / np.maximum(bg_frame_means[i], 1.0), 0.88, 1.14)
        if not np.allclose(gain, 1.0, atol=0.01):
            frames[i] = np.clip(frames[i].astype(np.float32) * gain, 0, 255).astype(
                np.uint8
            )
    print(f"  Normalised {len(valid_means)}/{N} frames")
else:
    print("  Skipped (too few frames with background)")

# ── Stages 5-7: Matching + filter + bundle adjust ─────────────────────────────
# Use a temporary pipeline instance to get _filter_edges (includes velocity
# consistency checks that catch wrong-direction TemplateMatch results).
print("Stages 5-7: matching + filter + bundle adjust...")
try:
    from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper

    loftr = LoFTRWrapper()
except Exception as e:
    print(f"  LoFTR unavailable ({e})")
    loftr = None

edges = _pairwise_match(frames, bg_masks, loftr_wrapper=loftr) # pyrefly: ignore [bad-argument-type]

if loftr is not None:
    if torch.cuda.is_available():
        try:
            loftr.offload()
        except Exception:
            pass
        torch.cuda.empty_cache()
    del loftr
    gc.collect()
    torch.cuda.empty_cache()

# _filter_edges is a pipeline instance method — create a minimal instance
pipe = AnimeStitchPipeline(
    use_basic=False, use_birefnet=False, use_loftr=False, use_ecc=False
)
edges = pipe._filter_edges(edges, frames_paths, H, W, frames, bg_masks) # pyrefly: ignore [bad-argument-type]
print(f"  {len(edges)} edges after filtering")

affines = _bundle_adjust_affine(edges, N)
print("  Bundle adjust complete")

# ── Stage 8: ECC sub-pixel refinement ─────────────────────────────────────────
print("Stage 8: ECC refinement...")
affines = _ecc_refine(frames, affines, bg_masks) # pyrefly: ignore [bad-argument-type]

# ── Stage 9: Canvas construction ──────────────────────────────────────────────
print("Stage 9: canvas...")
canvas_h, canvas_w, T_global = _compute_canvas(frames, affines)
print(f"  Canvas: {canvas_w}×{canvas_h}")
for i in range(N):
    affines[i][0, 2] += T_global[0]
    affines[i][1, 2] += T_global[1]

# Print the frame order for debugging
strip_center_ys = [float(affines[i][1, 2]) + frames[i].shape[0] / 2.0 for i in range(N)]
order = sorted(range(N), key=lambda i: strip_center_ys[i])
print(f"  Frame order (top→bottom): {order}")
print(f"  Strip centers: {[f'{strip_center_ys[i]:.0f}' for i in order]}")

canvas_info = {
    "canvas_h": canvas_h,
    "canvas_w": canvas_w,
    "affines_final": [a.tolist() for a in affines],
}
with open(f"{STAGE_DIR}/stage08_canvas_info.json", "w") as fh:
    json.dump(canvas_info, fh)
print("  Saved stage08_canvas_info.json")

# ── Stage 10: Temporal median render ──────────────────────────────────────────
print("Stage 10: temporal median render...")
canvas, valid_mask, _, _ = _render_median(frames, affines, bg_masks, canvas_h, canvas_w) # pyrefly: ignore [bad-argument-type]
cv2.imwrite(f"{STAGE_DIR}/stage09_temporal_render.png", canvas)
print("  Saved stage09_temporal_render.png")

canvas_crop = _crop_to_valid(canvas.copy(), valid_mask)
ec = 30
if ec * 2 < canvas_crop.shape[0] and ec * 2 < canvas_crop.shape[1]:
    canvas_crop = canvas_crop[ec:-ec, ec:-ec]
rgb = cv2.cvtColor(canvas_crop, cv2.COLOR_BGR2RGB)
Image.fromarray(rgb).save(f"{DIR}/temporal_render_preview.png")
print(
    f"  Saved temporal_render_preview.png ({canvas_crop.shape[1]}×{canvas_crop.shape[0]})"
)

print(f"\nAll stages saved to {STAGE_DIR}/")
print("Run:  python3 run_pipeline.py   (stages 9+11+12)")
print("Or:   python3 test_composite.py (stages 11+12)")

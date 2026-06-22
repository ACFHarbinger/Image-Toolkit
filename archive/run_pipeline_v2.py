#!/usr/bin/env python3
"""
Re-run rendering + composite with improved gain correction.
Uses stage03 (BaSiC-corrected) frames and the stage08 affines to skip
the GPU-heavy matching/alignment stages, then applies the fixed
compositing code with wider gain clamps and strip-gradient correction.
"""

import json
import os
import sys
import cv2
import numpy as np

from PIL import Image

from backend.src.animation.canvas import _crop_to_valid
from backend.src.animation.rendering import _render_median
from backend.src.animation.compositing import _composite_foreground

sys.path.insert(0, "/home/pkhunter/Repositories/Image-Toolkit")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

STAGE_DIR = "/home/pkhunter/Downloads/data/new/output/panorama_stages"
OUT_PATH = "/home/pkhunter/Downloads/data/new/output/panorama_v2.png"

# ── Load stage03 (BaSiC-corrected) frames ────────────────────────────────────
print("Loading stage03 BaSiC-corrected frames...")
frames = []
for i in range(8):
    p = f"{STAGE_DIR}/stage03_basic_corrected_frame{i:02d}.png"
    f = cv2.imread(p)
    assert f is not None, f"Missing: {p}"
    frames.append(f)
H, W = frames[0].shape[:2]
N = len(frames)
print(f"  {N} frames, {W}×{H}")

# ── Load BiRefNet masks ───────────────────────────────────────────────────────
print("Loading stage04 BiRefNet masks...")
bg_masks = []
for i in range(8):
    p = f"{STAGE_DIR}/stage04_bgmask_frame{i:02d}.png"
    m = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    assert m is not None, f"Missing: {p}"
    bg_masks.append(m)

# ── Load canvas info + final affines ─────────────────────────────────────────
print("Loading stage08 canvas info...")
with open(f"{STAGE_DIR}/stage08_canvas_info.json") as fh:
    info = json.load(fh)
canvas_h = info["canvas_h"]
canvas_w = info["canvas_w"]
affines = [np.array(a, dtype=np.float32) for a in info["affines_final"]]
print(f"  Canvas {canvas_w}×{canvas_h}, {N} frames")
for i, a in enumerate(affines):
    print(f"    affine[{i}] tx={a[0, 2]:.1f} ty={a[1, 2]:.1f}")

# ── Stage 9: Temporal median render ──────────────────────────────────────────
print("\nStage 9: temporal median render (improved gain clamp ±12%)...")

canvas, valid_mask, _, _ = _render_median(frames, affines, bg_masks, canvas_h, canvas_w)
cv2.imwrite(f"{STAGE_DIR}/stage09_temporal_render_v2.png", canvas)
print("  Saved stage09_temporal_render_v2.png")

# ── Stage 10: MFSR skipped ────────────────────────────────────────────────────
print("Stage 10: MFSR skipped (DCT blocks harm pan composites).")

# ── Stage 11: Foreground composite (improved gain + strip gradient) ───────────
print("\nStage 11: hard-partition composite (improved gain + strip gradient)...")

canvas = _composite_foreground(
    [], [], canvas, canvas_h, canvas_w, frames, affines, bg_masks
)
cv2.imwrite(f"{STAGE_DIR}/stage11_fg_composite_v2.png", canvas)
print("  Saved stage11_fg_composite_v2.png")

# ── Stage 12: Crop ────────────────────────────────────────────────────────────
print("\nStage 12: crop...")

canvas_out = _crop_to_valid(canvas, valid_mask)
ec = 30
if ec * 2 < canvas_out.shape[0] and ec * 2 < canvas_out.shape[1]:
    canvas_out = canvas_out[ec:-ec, ec:-ec]

# ── Save ──────────────────────────────────────────────────────────────────────
rgb = cv2.cvtColor(canvas_out, cv2.COLOR_BGR2RGB)
Image.fromarray(rgb).save(OUT_PATH)
print(f"\nDone: {canvas_out.shape[1]}×{canvas_out.shape[0]} → {OUT_PATH}")

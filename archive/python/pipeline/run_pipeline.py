#!/usr/bin/env python3
"""
Full AnimeStitchPipeline run — uses pre-computed LoFTR/BiRefNet stages
from panorama_stages/ to avoid GPU-hours, then re-runs rendering + composite
with the improved _GAIN_CLAMP=(0.93,1.07) code.
"""

import json
import os
import sys

import cv2
import numpy as np
from backend.src.animation.alignment.canvas import _crop_to_valid
from backend.src.animation.rendering.compositing import _composite_foreground
from backend.src.animation.rendering.rendering import _render_median
from PIL import Image

sys.path.insert(0, os.path.expanduser("~/Repositories/Image-Toolkit"))
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

STAGE_DIR = os.path.expanduser("~/Downloads/data/new/panorama_stages")
OUT_PATH = os.path.expanduser("~/Downloads/data/new/panorama_v2.png")

# ─── Load pre-computed stage data ────────────────────────────────────────────
print("Stage 2: loading normalised frames...")
frames = []
for i in range(8):
    p = f"{STAGE_DIR}/stage02_normalised_frame{i:02d}.png"
    f = cv2.imread(p)
    assert f is not None
    frames.append(f)
H, W = frames[0].shape[:2]
N = len(frames)

print("Stage 4: loading BiRefNet masks...")
bg_masks = []
for i in range(8):
    p = f"{STAGE_DIR}/stage04_bgmask_frame{i:02d}.png"
    m = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    assert m is not None
    bg_masks.append(m)

print("Stage 8: loading canvas info and final affines...")
with open(f"{STAGE_DIR}/stage08_canvas_info.json") as fh:
    info = json.load(fh)
canvas_h = info["canvas_h"]
canvas_w = info["canvas_w"]
affines = [np.array(a, dtype=np.float32) for a in info["affines_final"]]
print(f"  Canvas {canvas_w}×{canvas_h}, {N} frames")

# ─── Stage 9: Temporal median render (re-run) ────────────────────────────────
print("Stage 9: temporal median render...")
canvas, valid_mask, _, _ = _render_median(frames, affines, bg_masks, canvas_h, canvas_w) # pyrefly: ignore [bad-argument-type]
cv2.imwrite(f"{STAGE_DIR}/stage09_temporal_render_v2.png", canvas)
print("  Saved stage09_temporal_render_v2.png")

# ─── Stage 10: MFSR skipped ───────────────────────────────────────────────────
print("Stage 10: MFSR skipped.")

# ─── Stage 11: Foreground composite (improved gain clamp) ────────────────────
print("Stage 11: hard-partition composite (improved _GAIN_CLAMP=(0.93,1.07))...")
canvas = _composite_foreground([], [], canvas, canvas_h, canvas_w, frames, affines, bg_masks) # pyrefly: ignore [bad-argument-type]
cv2.imwrite(f"{STAGE_DIR}/stage11_fg_composite_v2.png", canvas)
print("  Saved stage11_fg_composite_v2.png")

# ─── Stage 12: Crop ──────────────────────────────────────────────────────────
print("Stage 12: crop...")
canvas = _crop_to_valid(canvas, valid_mask)
ec = 30
if ec * 2 < canvas.shape[0] and ec * 2 < canvas.shape[1]:
    canvas = canvas[ec:-ec, ec:-ec]

# ─── Save ─────────────────────────────────────────────────────────────────────
rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
Image.fromarray(rgb).save(OUT_PATH)
print(f"Done: {canvas.shape[1]}×{canvas.shape[0]} → {OUT_PATH}")

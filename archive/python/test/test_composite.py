#!/usr/bin/env python3
"""
Fast composite test: skips LoFTR/BiRefNet, uses pre-computed stage data.
Runs only the compositing stage with the improved _global_gain_normalize +
_apply_strip_gradient pipeline.
"""

import json
import os
import sys

import cv2
import numpy as np

from backend.src.animation.alignment.canvas import _crop_to_valid
from backend.src.animation.rendering.compositing import _composite_foreground

sys.path.insert(0, "/home/pkhunter/Repositories/Image-Toolkit")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

STAGE_DIR = "/home/pkhunter/Downloads/data/new/panorama_stages"
OUT_PATH = "/home/pkhunter/Downloads/data/new/test_composite.png"

# 1. Load normalised frames (stage02)
print("Loading normalised frames...")
frames = []
for i in range(8):
    p = f"{STAGE_DIR}/stage02_normalised_frame{i:02d}.png"
    f = cv2.imread(p)
    assert f is not None, f"Missing {p}"
    frames.append(f)

# 2. Load bg masks (stage04)
print("Loading foreground masks...")
bg_masks = []
for i in range(8):
    p = f"{STAGE_DIR}/stage04_bgmask_frame{i:02d}.png"
    m = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    assert m is not None, f"Missing {p}"
    bg_masks.append(m)

# 3. Load final affines + canvas dims from stage08
with open(f"{STAGE_DIR}/stage08_canvas_info.json") as fh:
    info = json.load(fh)
canvas_h = info["canvas_h"]
canvas_w = info["canvas_w"]
affines = [np.array(a, dtype=np.float32) for a in info["affines_final"]]
print(f"Canvas: {canvas_w}×{canvas_h}, {len(frames)} frames")

# 4. Load the temporal render as the background canvas (stage09)
print("Loading temporal render canvas (stage09)...")
canvas = cv2.imread(f"{STAGE_DIR}/stage09_temporal_render.png")
assert canvas is not None, "Missing stage09_temporal_render.png"

# Sanity: the temporal render might have been saved at slightly different dims
# due to _crop_to_valid not yet applied — resize to match canvas if needed.
if canvas.shape[0] != canvas_h or canvas.shape[1] != canvas_w:
    print(
        f"  Resizing temporal render {canvas.shape[1]}×{canvas.shape[0]} "
        f"→ {canvas_w}×{canvas_h}"
    )
    canvas = cv2.resize(canvas, (canvas_w, canvas_h), interpolation=cv2.INTER_LINEAR)

# 5. Run improved composite
print("Running improved _composite_foreground...")
canvas_out = _composite_foreground(
    [], [], canvas, canvas_h, canvas_w, frames, affines, bg_masks # pyrefly: ignore [bad-argument-type]
)

# 6. Apply same crop logic as the worker (stage12)
valid_mask = (canvas_out.max(axis=2) > 0).astype(np.uint8) * 255
canvas_out = _crop_to_valid(canvas_out, valid_mask)
ec = 30  # edge_crop default
if ec * 2 < canvas_out.shape[0] and ec * 2 < canvas_out.shape[1]:
    canvas_out = canvas_out[ec:-ec, ec:-ec]

# 7. Save
cv2.imwrite(OUT_PATH, canvas_out)
print(f"Saved {canvas_out.shape[1]}×{canvas_out.shape[0]} → {OUT_PATH}")

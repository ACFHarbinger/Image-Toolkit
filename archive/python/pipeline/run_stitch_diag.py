"""
Diagnostic stitch run — saves intermediate stage images and per-row luma profile.
Run from repo root:  python run_stitch_diag.py
"""
import sys, os
sys.path.insert(0, os.path.expanduser("~/Repositories/Image-Toolkit"))
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import glob
import cv2
import numpy as np
from PIL import Image

OUT_DIR = os.path.join(os.path.expanduser("~/Downloads/data/new/diag29"))
os.makedirs(OUT_DIR, exist_ok=True)

SRC = sorted(glob.glob(os.path.join(os.path.expanduser("~/Downloads/data/new/*ms.png"))))
print(f"Source frames: {len(SRC)}")
for f in SRC:
    print(f"  {os.path.basename(f)}")

OUTPUT_PATH = os.path.join(OUT_DIR, "panorama_diag29.png")

# ── Monkey-patch pipeline to save stage outputs ──────────────────────────────
from backend.src.anim import pipeline as _pip_mod
from backend.src.anim import rendering as _rend_mod
from backend.src.anim import compositing as _comp_mod

_orig_render = _rend_mod._render_median
_orig_composite = _comp_mod._composite_foreground

def _diag_render_median(frames, affines, bg_masks, H, W, **kw):
    result = _orig_render(frames, affines, bg_masks, H, W, **kw)
    canvas = result[0]
    print(f"[DIAG] Saving temporal median canvas ({W}x{H})...")
    cv2.imwrite(os.path.join(OUT_DIR, "stage10_temporal_median.png"), canvas)
    print(f"[DIAG] Canvas size: {canvas.shape}")

    # Per-row luma profile
    luma = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY).astype(np.float32)
    row_luma = luma.mean(axis=1)
    print("[DIAG] Per-row mean luma (every 100 rows):")
    for y in range(0, H, 100):
        print(f"  y={y:4d}: {row_luma[y]:.1f}")
    return result

def _diag_composite(warped_corr, warped_fgs, canvas, H, W, frames, affines, bg_masks):
    # Print per-frame luma (frames are post-stage-4.5)
    print("[DIAG] Per-frame luma after stage 4.5:")
    strip_center_ys = []
    for i, f in enumerate(frames):
        luma_val = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32).mean()
        ty = float(affines[i][1, 2])
        sc = ty + f.shape[0] / 2.0
        strip_center_ys.append(sc)
        print(f"  Frame {i}: luma={luma_val:.1f}  canvas_ty={ty:.1f}  strip_center={sc:.1f}")

    result = _orig_composite(warped_corr, warped_fgs, canvas, H, W, frames, affines, bg_masks)

    # Save composite output
    print(f"[DIAG] Saving composite result ({W}x{H})...")
    cv2.imwrite(os.path.join(OUT_DIR, "stage11_composite.png"), result)

    # Draw strip boundaries on a copy
    annot = result.copy()
    N = len(frames)
    order = np.argsort(strip_center_ys)
    sorted_sc = np.array(strip_center_ys)[order]
    boundaries = (sorted_sc[:-1] + sorted_sc[1:]) / 2.0
    for by in boundaries:
        by_i = int(by)
        if 0 <= by_i < H:
            cv2.line(annot, (0, by_i), (W, by_i), (0, 255, 0), 2)
    cv2.imwrite(os.path.join(OUT_DIR, "stage11_composite_annotated.png"), annot)
    print(f"[DIAG] Saved annotated composite with strip boundaries.")

    # Per-row luma of composite
    luma = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY).astype(np.float32)
    row_luma = luma.mean(axis=1)
    print("[DIAG] Per-row mean luma of composite (every 100 rows):")
    for y in range(0, H, 100):
        print(f"  y={y:4d}: {row_luma[y]:.1f}")

    # Luma jump at each boundary
    print("[DIAG] Luma delta at strip boundaries:")
    for by in boundaries:
        by_i = int(by)
        if 20 <= by_i < H - 20:
            before = row_luma[by_i - 20:by_i].mean()
            after = row_luma[by_i + 1:by_i + 21].mean()
            print(f"  y={by_i}: before={before:.1f}  after={after:.1f}  delta={after-before:.1f}")

    return result

_rend_mod._render_median = _diag_render_median
_comp_mod._composite_foreground = _diag_composite

# ── Run pipeline ──────────────────────────────────────────────────────────────
from backend.src.anim.pipeline import AnimeStitchPipeline

pipe = AnimeStitchPipeline(
    use_basic=True,
    use_birefnet=True,
    use_loftr=True,
    use_ecc=True,
    renderer="median",
    composite_fg=True,
    edge_crop=30,
    motion_model="translation",
)
result = pipe.run(SRC, OUTPUT_PATH)
print(f"\nOutput saved: {OUTPUT_PATH}")
print(f"Size: {result.size}")

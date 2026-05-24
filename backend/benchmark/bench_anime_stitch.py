#!/usr/bin/env python3
import json, os, sys, glob, gc, shutil
import cv2, numpy as np
import torch

sys.path.insert(0, "/home/pkhunter/Repositories/Image-Toolkit")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

from backend.src.anim.pipeline import AnimeStitchPipeline
from backend.src.anim.canvas import (
    _load_frames,
    _normalise_widths,
    _compute_canvas,
    _crop_to_valid,
    _scan_stitch_fallback,
)
from backend.src.anim.validation import _validate_affines
from backend.src.anim.masking import _compute_fg_masks
from backend.src.anim.matching import _pairwise_match
from backend.src.anim.bundle_adjust import _bundle_adjust_affine
from backend.src.anim.ecc import _ecc_refine
from backend.src.anim.rendering import _render_median
from backend.src.anim.compositing import _composite_foreground


def process_dataset(dataset_dir: str):
    print(f"\n{'=' * 60}\nProcessing dataset: {dataset_dir}\n{'=' * 60}")

    stage_dir = os.path.join(dataset_dir, "output", "panorama_stages")
    out_path = os.path.join(dataset_dir, "output", "panorama.png")

    # 1. Clean old outputs
    if os.path.exists(out_path):
        os.remove(out_path)
    if os.path.exists(stage_dir):
        shutil.rmtree(stage_dir)
    os.makedirs(stage_dir, exist_ok=True)

    # 2. Collect frames
    all_pngs = sorted(
        glob.glob(os.path.join(dataset_dir, "*.png"))
        + glob.glob(os.path.join(dataset_dir, "*.jpg"))
    )
    frames_paths = [
        p
        for p in all_pngs
        if "panorama" not in os.path.basename(p)
        and "test_" not in os.path.basename(p)
        and "stage" not in os.path.basename(p)
    ]
    if len(frames_paths) < 2:
        print(f"Skipping {dataset_dir}: not enough frames.")
        return

    print(f"Source frames ({len(frames_paths)}):")
    for p in frames_paths:
        print(f"  {os.path.basename(p)}")

    # 3. Stage 1-2: Load & normalise
    frames = _load_frames(frames_paths)
    N = len(frames)
    frames = _normalise_widths(frames)
    H, W = frames[0].shape[:2]
    for i, f in enumerate(frames):
        cv2.imwrite(os.path.join(stage_dir, f"stage02_normalised_frame{i:02d}.png"), f)

    # 4. Stage 4: BiRefNet foreground masks
    try:
        from backend.src.models.birefnet_wrapper import BiRefNetWrapper

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
    except Exception as e:
        print(f"  BiRefNet failed ({e}), using None masks")
        bg_masks = [None] * N

    for i, m in enumerate(bg_masks):
        img = m if m is not None else np.ones((H, W), dtype=np.uint8) * 255
        cv2.imwrite(os.path.join(stage_dir, f"stage04_bgmask_frame{i:02d}.png"), img)

    # 5. Stage 4.5: Background photometric normalisation
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

    # Save stage 3 as basic corrected to match expected
    for i, f in enumerate(frames):
        cv2.imwrite(
            os.path.join(stage_dir, f"stage03_basic_corrected_frame{i:02d}.png"), f
        )

    # 6. Stages 5-7: Matching + filter + bundle adjust
    try:
        from backend.src.models.loftr_wrapper import LoFTRWrapper

        loftr = LoFTRWrapper()
    except Exception as e:
        loftr = None

    edges = _pairwise_match(frames, bg_masks, loftr_wrapper=loftr)
    if loftr is not None:
        if torch.cuda.is_available():
            try:
                loftr.offload()
            except Exception:
                pass
        del loftr
        gc.collect()
        torch.cuda.empty_cache()

    pipe = AnimeStitchPipeline(
        use_basic=False, use_birefnet=False, use_loftr=False, use_ecc=False
    )
    edges = pipe._filter_edges(edges, frames_paths, H, W, frames, bg_masks)
    affines = _bundle_adjust_affine(edges, N)

    # Validate affines — redirect structurally broken datasets to SCANS fallback
    health = _validate_affines(affines)
    print(
        f"  Affine health: valid={health.valid}, reason={health.reason}, ratio={health.ratio:.2f}, min_gap={health.min_gap:.1f}px"
    )
    if not health.valid:
        print("  Validation FAILED → SCANS fallback.")
        _scan_stitch_fallback(frames, out_path)
        _dataset_name = os.path.basename(dataset_dir)
        _central_out_dir = os.path.join(os.path.dirname(dataset_dir), "output")
        os.makedirs(_central_out_dir, exist_ok=True)
        _central_path = os.path.join(
            _central_out_dir, f"{_dataset_name}_anime_stitch.png"
        )
        shutil.copy2(out_path, _central_path)
        print(f"\nFinished (SCANS): {dataset_dir} -> {out_path}")
        return

    # 7. Stage 8: ECC sub-pixel refinement
    affines = _ecc_refine(frames, affines, bg_masks)

    # 8. Stage 9: Canvas construction
    canvas_h, canvas_w, T_global = _compute_canvas(frames, affines)
    for i in range(N):
        affines[i][0, 2] += T_global[0]
        affines[i][1, 2] += T_global[1]

    canvas_info = {
        "canvas_h": canvas_h,
        "canvas_w": canvas_w,
        "affines_final": [a.tolist() for a in affines],
    }
    with open(os.path.join(stage_dir, "stage08_canvas_info.json"), "w") as fh:
        json.dump(canvas_info, fh)

    # 9. Stage 10: Temporal median render
    canvas, valid_mask, _, _ = _render_median(
        frames, affines, bg_masks, canvas_h, canvas_w
    )
    cv2.imwrite(os.path.join(stage_dir, "stage09_temporal_render.png"), canvas)

    # 10. Stage 11: Foreground composite
    canvas = _composite_foreground(
        [], [], canvas, canvas_h, canvas_w, frames, affines, bg_masks
    )
    cv2.imwrite(os.path.join(stage_dir, "stage11_fg_composite.png"), canvas)

    # 11. Stage 12: Crop to valid
    canvas_out = _crop_to_valid(canvas, valid_mask)
    ec = 30
    if ec * 2 < canvas_out.shape[0] and ec * 2 < canvas_out.shape[1]:
        canvas_out = canvas_out[ec:-ec, ec:-ec]

    # Save final panorama
    from PIL import Image

    rgb = cv2.cvtColor(canvas_out, cv2.COLOR_BGR2RGB)
    Image.fromarray(rgb).save(out_path)
    print(f"\nFinished: {dataset_dir} -> {out_path}")

    # Copy to centralized data/output directory
    dataset_name = os.path.basename(dataset_dir)
    central_out_dir = os.path.join(os.path.dirname(dataset_dir), "output")
    os.makedirs(central_out_dir, exist_ok=True)

    central_anime_stitch_path = os.path.join(
        central_out_dir, f"{dataset_name}_anime_stitch.png"
    )
    central_simple_stitch_path = os.path.join(
        central_out_dir, f"{dataset_name}_simple_stitch.png"
    )

    shutil.copy2(out_path, central_anime_stitch_path)

    simple_stitch_src = os.path.join(dataset_dir, "output", "simple_stitch.png")
    if os.path.exists(simple_stitch_src):
        shutil.copy2(simple_stitch_src, central_simple_stitch_path)
    else:
        print(f"Warning: {simple_stitch_src} not found.")


if __name__ == "__main__":
    base_dir = "/home/pkhunter/Repositories/Image-Toolkit/data"
    datasets = sorted(glob.glob(os.path.join(base_dir, "asp_test*")))
    for ds in datasets:
        if os.path.isdir(ds):
            process_dataset(ds)

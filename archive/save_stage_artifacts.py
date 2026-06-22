"""
save_stage_artifacts.py
=======================
Monkey-patches AnimeStitchPipeline to save the intermediate outputs from
each stage as named PNG files and a JSON metadata file.

Saved artefacts (in <output_dir>/panorama_stages/):
  stage02_normalised_frame{N}.png     ← width-normalised frames
  stage03_basic_frame{N}.png          ← BaSiC-corrected frames (if enabled)
  stage04_bgmask_frame{N}.png         ← BiRefNet bg masks (255=bg)
  stage05_edges.json                  ← pairwise match edges (M, pts, weight)
  stage07_ba_affines.json             ← bundle-adjusted affines (pre-ECC)
  stage08_canvas_info.json            ← ECC-refined affines + canvas dimensions
  stage09_temporal_render.png         ← temporal median render output
  stage11_composite.png               ← foreground composite output

Usage
-----
    from save_stage_artifacts import instrument_pipeline
    from backend.src.animation import AnimeStitchPipeline

    pipeline = AnimeStitchPipeline(use_birefnet=True, use_loftr=True)
    instrument_pipeline(pipeline, output_dir="/path/to/dataset/output")
    pipeline.run(image_paths, "/path/to/dataset/output/panorama.png")

    # Or as a full replacement for the standard run:
    from save_stage_artifacts import run_and_save
    run_and_save(image_paths, output_dir="/path/to/dataset/output")

Notes
-----
- The monkey-patch intercepts the internal `_render`, `_composite_foreground`,
  `_bundle_adjust_affine`, and `_ecc_refine` calls via method override on
  the instance — it does not modify the module-level functions.
- All stage images are saved as lossless PNG.
- JSON affine schema: {"affines": [[a,b,tx,c,d,ty], ...], "canvas_h": H, "canvas_w": W}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _affine_to_list(M: np.ndarray) -> List[float]:
    """Convert (2,3) affine to flat list [a,b,tx,c,d,ty]."""
    return M.flatten().tolist()


def _save_png(arr: np.ndarray, path: Path) -> None:
    """Save a BGR uint8 numpy array as a lossless PNG."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), arr)


def _save_mask_png(mask: Optional[np.ndarray], path: Path) -> None:
    """Save an 8-bit mask (None → all-zero placeholder)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if mask is None:
        cv2.imwrite(str(path), np.zeros((4, 4), dtype=np.uint8))
    else:
        cv2.imwrite(str(path), mask)


def _edges_to_json(edges: List[Dict]) -> List[Dict]:
    """Serialise edge dicts: convert numpy arrays to nested lists."""
    out = []
    for e in edges:
        entry = {k: v for k, v in e.items() if k not in ("M", "pts_i", "pts_j")}
        if "M" in e:
            entry["M"] = e["M"].tolist()
        if "pts_i" in e:
            entry["pts_i"] = e["pts_i"].tolist()
        if "pts_j" in e:
            entry["pts_j"] = e["pts_j"].tolist()
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Instrumented pipeline wrapper
# ---------------------------------------------------------------------------


def instrument_pipeline(pipeline: Any, output_dir: str) -> None:
    """
    Monkey-patch a live AnimeStitchPipeline instance to intercept internal
    stage calls and write artefacts to <output_dir>/panorama_stages/.

    All original logic is preserved — this only adds save() calls.
    """
    stages_dir = Path(output_dir) / "panorama_stages"
    stages_dir.mkdir(parents=True, exist_ok=True)

    # ---- Keep references to original bound methods ----
    _orig_normalise = pipeline._normalise_widths.__func__  # staticmethod
    _orig_apply_basic = pipeline._apply_basic
    _orig_fg_masks = pipeline._compute_fg_masks
    _orig_pairwise_match = pipeline._pairwise_match
    _orig_ba = pipeline._ecc_refine  # save post-ECC (stage 8)
    _orig_render = pipeline._render
    _orig_composite = pipeline._composite_foreground

    # ---- Stage 2: width-normalised frames ----
    # original_run = pipeline.run

    def patched_run(image_paths: List[str], output_path: str) -> Image.Image:
        """
        Full replacement for pipeline.run() that saves artefacts at each stage.
        Reimplements the calling sequence from pipeline.py so we can intercept
        each intermediate result.  This keeps the monkey-patch self-contained
        and does not require modifying the original source.
        """
        import gc
        import warnings
        from backend.src.animation.bundle_adjust import _bundle_adjust_affine
        from backend.src.animation.canvas import (
            _compute_canvas,
            _crop_to_valid,
            _load_frames,
            _normalise_widths,
            _scan_stitch_fallback,
        )
        from backend.src.animation.compositing import _composite_foreground
        from backend.src.animation.ecc import _ecc_refine
        from backend.src.animation.masking import _compute_fg_masks
        from backend.src.animation.matching import _pairwise_match
        from backend.src.animation.photometric import _apply_basic, _correct_vignetting
        from backend.src.animation.rendering import _render

        import torch

        out_abs = os.path.abspath(output_path)
        image_paths = [p for p in image_paths if os.path.abspath(p) != out_abs]

        print(f"[SaveStages] Saving artefacts to {stages_dir}")
        pipeline._baselines = None

        # Stage 1: load
        frames = _load_frames(image_paths)
        N = len(frames)
        if N < 2:
            raise ValueError("Need at least 2 frames.")

        # Stage 2: width normalise — save
        frames = _normalise_widths(frames)
        for i, f in enumerate(frames):
            _save_png(f, stages_dir / f"stage02_normalised_frame{i:02d}.png")
        print(f"[SaveStages] Stage 2: saved {N} normalised frames.")
        H, W = frames[0].shape[:2]

        # Stage 3: BaSiC
        # bg_masks_photometric: List[Optional[np.ndarray]] = [None] * N
        if pipeline.use_basic:
            from backend.src.models.basic_wrapper import BaSiCWrapper

            if pipeline._basic is None:
                pipeline._basic = BaSiCWrapper()
            frames, baselines = _apply_basic(frames, pipeline._basic)
            pipeline._baselines = baselines
            frames = _correct_vignetting(frames)
            for i, f in enumerate(frames):
                _save_png(f, stages_dir / f"stage03_basic_frame{i:02d}.png")
            print(f"[SaveStages] Stage 3: saved {N} BaSiC-corrected frames.")

        # Stage 4: fg masks — save
        if pipeline.use_birefnet and pipeline._birefnet is None:
            from backend.src.models.birefnet_wrapper import BiRefNetWrapper

            pipeline._birefnet = BiRefNetWrapper()
        bg_masks = _compute_fg_masks(
            frames, pipeline._birefnet, use_birefnet=pipeline.use_birefnet
        )
        for i, m in enumerate(bg_masks):
            _save_mask_png(m, stages_dir / f"stage04_bgmask_frame{i:02d}.png")
        print(f"[SaveStages] Stage 4: saved {N} bg masks.")

        # Offload BiRefNet
        if torch.cuda.is_available() and pipeline._birefnet is not None:
            try:
                pipeline._birefnet.offload()
            except Exception:
                pass
            pipeline._birefnet = None
            torch.cuda.empty_cache()

        # Stage 4.5: background photometric normalisation (same as pipeline.run)
        bg_frame_means = []
        for _frame, _mask in zip(frames, bg_masks):
            if _mask is not None:
                _bg_px = _frame[_mask > 127].astype(np.float32)
                if len(_bg_px) >= 1000:
                    bg_frame_means.append(_bg_px.mean(axis=0))
                    continue
            bg_frame_means.append(None)
        _valid_means = [m for m in bg_frame_means if m is not None]
        if len(_valid_means) >= 3:
            _ref_mean = np.median(_valid_means, axis=0)
            for _i in range(N):
                if bg_frame_means[_i] is None:
                    continue
                _gain = np.clip(
                    _ref_mean / np.maximum(bg_frame_means[_i], 1.0), 0.88, 1.14
                )
                if not np.allclose(_gain, 1.0, atol=0.01):
                    frames[_i] = np.clip(
                        frames[_i].astype(np.float32) * _gain, 0, 255
                    ).astype(np.uint8)

        # Stage 5-6: pairwise matching — save edges
        if pipeline.use_loftr and pipeline._loftr is None:
            from backend.src.models.loftr_wrapper import LoFTRWrapper

            pipeline._loftr = LoFTRWrapper()
        edges = _pairwise_match(
            frames,
            bg_masks,
            loftr_wrapper=pipeline._loftr,
            use_loftr=pipeline.use_loftr,
            motion_model=pipeline.motion_model,
        )
        edges = pipeline._filter_edges(edges, image_paths, H, W, frames, bg_masks)
        with open(stages_dir / "stage05_edges.json", "w") as f:
            json.dump(_edges_to_json(edges), f, indent=2)
        print(f"[SaveStages] Stage 5-6: saved {len(edges)} edges.")

        if torch.cuda.is_available() and pipeline._loftr is not None:
            try:
                pipeline._loftr.offload()
            except Exception:
                pass
            torch.cuda.empty_cache()
            gc.collect()
            pipeline._loftr = None
            torch.cuda.empty_cache()

        if not edges:
            warnings.warn("[SaveStages] No valid edges — falling back to scan stitch.")
            return _scan_stitch_fallback(frames, output_path)

        # Stage 7: bundle adjustment — save pre-ECC affines
        use_affine_ba = getattr(pipeline, "motion_model", "affine") == "affine"
        affines_ba = _bundle_adjust_affine(edges, N, use_affine=use_affine_ba)
        ba_data = {
            "affines": [_affine_to_list(M) for M in affines_ba],
            "stage": "bundle_adjust",
        }
        with open(stages_dir / "stage07_ba_affines.json", "w") as f:
            json.dump(ba_data, f, indent=2)
        print("[SaveStages] Stage 7: saved bundle-adjusted affines.")

        # Stage 8: ECC refinement — save final affines + canvas info
        if pipeline.use_ecc:
            affines = _ecc_refine(frames, affines_ba, bg_masks)
        else:
            affines = affines_ba

        canvas_h, canvas_w, T_global = _compute_canvas(frames, affines)
        for i in range(N):
            affines[i][0, 2] += T_global[0]
            affines[i][1, 2] += T_global[1]

        canvas_data = {
            "affines": [_affine_to_list(M) for M in affines],
            "canvas_h": canvas_h,
            "canvas_w": canvas_w,
            "T_global": T_global.tolist(),
            "frames": [
                {
                    "frame": i,
                    "tx": float(affines[i][0, 2]),
                    "ty": float(affines[i][1, 2]),
                }
                for i in range(N)
            ],
        }
        with open(stages_dir / "stage08_canvas_info.json", "w") as f:
            json.dump(canvas_data, f, indent=2)
        print(f"[SaveStages] Stage 8: canvas {canvas_w}×{canvas_h}, saved affines.")

        # Stage 9: temporal render — save
        canvas, valid_mask, warped_corr, warped_fgs = _render(
            frames,
            affines,
            bg_masks,
            canvas_h,
            canvas_w,
            renderer=pipeline.renderer,
            baselines=pipeline._baselines,
        )
        _save_png(canvas, stages_dir / "stage09_temporal_render.png")
        print("[SaveStages] Stage 9: saved temporal render.")

        # Stage 11: composite — save
        if pipeline.composite_fg and pipeline.use_birefnet:
            canvas_composite = _composite_foreground(
                [], [], canvas.copy(), canvas_h, canvas_w, frames, affines, bg_masks
            )
            _save_png(canvas_composite, stages_dir / "stage11_composite.png")
            print("[SaveStages] Stage 11: saved composite.")
        else:
            canvas_composite = canvas
            _save_png(canvas_composite, stages_dir / "stage11_composite.png")

        # Stage 13: crop + save final
        canvas_final = _crop_to_valid(canvas_composite, valid_mask)
        ec = getattr(pipeline, "edge_crop", 0)
        if ec > 0 and ec * 2 < canvas_final.shape[0] and ec * 2 < canvas_final.shape[1]:
            canvas_final = canvas_final[ec:-ec, ec:-ec]

        rgb = cv2.cvtColor(canvas_final, cv2.COLOR_BGR2RGB)
        out = Image.fromarray(rgb)
        out.save(output_path)
        gc.collect()
        print(f"[SaveStages] Done. Panorama saved to '{output_path}'.")
        return out

    pipeline.run = patched_run
    print(f"[SaveStages] Pipeline instrumented. Artefacts → {stages_dir}")


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------


def run_and_save(
    image_paths: List[str],
    output_dir: str,
    pipeline_kwargs: Optional[Dict] = None,
) -> Image.Image:
    """
    Create a fresh AnimeStitchPipeline, instrument it, and run it.

    Parameters
    ----------
    image_paths    : ordered list of source frame paths.
    output_dir     : directory for panorama.png and panorama_stages/.
    pipeline_kwargs: kwargs forwarded to AnimeStitchPipeline constructor.

    Returns the final PIL Image.
    """
    from backend.src.animation import AnimeStitchPipeline

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = str(Path(output_dir) / "panorama.png")

    kwargs = pipeline_kwargs or {
        "use_basic": False,
        "use_loftr": True,
        "use_ecc": False,
        "renderer": "median",
        "composite_fg": True,
        "motion_model": "translation",
        "edge_crop": 80,
    }

    pipeline = AnimeStitchPipeline(**kwargs)
    instrument_pipeline(pipeline, output_dir)
    return pipeline.run(image_paths, output_path)


# ---------------------------------------------------------------------------
# CLI (simple batch runner)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import glob
    import sys

    parser = argparse.ArgumentParser(
        description="Run AnimeStitchPipeline with stage artefact saving."
    )
    parser.add_argument(
        "--frames-dir", required=True, help="Directory containing source frame images."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for panorama.png and panorama_stages/.",
    )
    parser.add_argument(
        "--pattern",
        default="*.png",
        help="Glob pattern for source frames (default: *.png).",
    )
    parser.add_argument("--no-birefnet", action="store_true")
    parser.add_argument("--no-loftr", action="store_true")
    args = parser.parse_args()

    frames = sorted(glob.glob(os.path.join(args.frames_dir, args.pattern)))
    if len(frames) < 2:
        print(f"ERROR: need at least 2 frames in '{args.frames_dir}'", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(frames)} frames in '{args.frames_dir}'.")
    run_and_save(
        frames,
        args.output_dir,
        pipeline_kwargs={
            "use_basic": False,
            "use_birefnet": not args.no_birefnet,
            "use_loftr": not args.no_loftr,
            "use_ecc": False,
            "renderer": "median",
            "composite_fg": not args.no_birefnet,
            "motion_model": "translation",
            "edge_crop": 80,
        },
    )

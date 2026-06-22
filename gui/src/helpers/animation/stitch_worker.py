"""
gui/src/helpers/models/stitch_worker.py
========================================
Worker threads for the EditTab (panorama stitching, per-image adjustment,
and canvas composition).

Workers
-------
  StitchWorker       Full AnimeStitchPipeline in a QThread with per-stage
                     progress signals and optional manual affine overrides.
"""

from __future__ import annotations

import gc
import json
import os
import os as _os
import shutil
import warnings
import tempfile
import time as _time
import datetime as _dt
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image as _Image
import torch
from PySide6.QtCore import QMutex, QObject, QWaitCondition, Signal

from backend.src.animation import AnimeStitchPipeline
from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper
from backend.src.animation.rendering.compositing import _compute_initial_boundaries
from backend.src.animation.alignment.bundle_adjust import _bundle_adjust_affine
from backend.src.animation.core.data_serialization import create_session_serializers
from backend.src.animation.core.pipeline import _build_manual_edge
from backend.src.animation.mfsr import run_mfsr
from backend.src.animation.rlhf.feedback_store import FeedbackStore, StitchAnnotation
from backend.src.animation.hitl.hitl_session import (
    save_session as _save_session_impl,
    load_session,
    autosave_path,
)
from backend.src.animation.ingestion.video_ingestion import ingest_video

# ---------------------------------------------------------------------------
# _ProgressPipeline — AnimeStitchPipeline subclass with progress callbacks
# ---------------------------------------------------------------------------

_STAGE_LABELS = [
    "Loading & trimming frames",  # 1
    "Normalising widths",  # 2
    "BaSiC photometric correction",  # 3
    "BiRefNet foreground masking",  # 4
    "Pairwise matching & edge filter",  # 5
    "Bundle adjustment",  # 6
    "ECC sub-pixel refinement",  # 7
    "Building canvas",  # 8
    "Temporal render",  # 9
    "MFSR super-resolution",  # 10
    "Compositing foreground",  # 11
    "Boundary crop",  # 12
    "Saving output",  # 13
]
_TOTAL_STAGES = len(_STAGE_LABELS)


def _build_pipeline_kwargs(cfg: dict) -> dict:
    """Translate a pipeline_config dict into AnimeStitchPipeline keyword args."""
    return dict(
        use_basic=cfg.get("use_basic", True),
        use_birefnet=cfg.get("use_birefnet", True),
        use_loftr=cfg.get("use_loftr", True),
        use_ecc=cfg.get("use_ecc", True),
        renderer=cfg.get("renderer", "median"),
        composite_fg=cfg.get("composite_fg", True),
        laplacian_bands=cfg.get("laplacian_bands", 5),
        stitch_net_ckpt=cfg.get("stitch_net_ckpt", ""),
        edge_crop=cfg.get("edge_crop", 30),
        motion_model=cfg.get("motion_model", "translation"),
        mfsr_mode=cfg.get("mfsr_mode", False),
    )


class _ProgressPipeline(AnimeStitchPipeline):
    """
    Subclass of AnimeStitchPipeline with per-stage progress callbacks,
    manual affine overrides, cancellation support, and the direction-
    consensus edge filter wired in via _filter_edges().
    """

    def __init__(
        self,
        progress_cb,
        log_cb,
        manual_affines: Optional[Dict] = None,
        cancel_flag: Optional[list] = None,
        mfsr_n_dct_iter: int = 20,
        mfsr_use_prior: bool = True,
        mfsr_use_diffusion: bool = False,
        save_intermediate: bool = False,
        intermediate_dir: str = "",
        pause_cb: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._progress_cb = progress_cb
        self._log_cb = log_cb
        self._manual_affines = manual_affines or {}
        self._cancel_flag = cancel_flag or [False]
        self._mfsr_n_dct_iter = mfsr_n_dct_iter
        self._mfsr_use_prior = mfsr_use_prior
        self._mfsr_use_diffusion = mfsr_use_diffusion
        self._save_intermediate = save_intermediate
        self._intermediate_dir = intermediate_dir
        self._pause_cb: Callable = pause_cb or (lambda event, data: {})

    def _hitl_pause(self, event: str, data: dict) -> dict:
        """Emit a HITL checkpoint event and block until the UI calls resume()."""
        return self._pause_cb(event, data)

    def _check_cancel(self):
        if self._cancel_flag[0]:
            raise InterruptedError("Stitch cancelled by user.")

    def run(self, image_paths: List[str], output_path: str):
        out_abs = os.path.abspath(output_path)
        image_paths = [p for p in image_paths if os.path.abspath(p) != out_abs]

        # Intermediate output helpers ─────────────────────────────────────
        idir = self._intermediate_dir
        if self._save_intermediate and idir:
            os.makedirs(idir, exist_ok=True)

        def _save_frames(stage_idx: int, label: str, frame_list):
            if not (self._save_intermediate and idir):
                return
            for k, f in enumerate(frame_list):
                path = os.path.join(
                    idir, f"stage{stage_idx:02d}_{label}_frame{k:02d}.png"
                )
                try:
                    cv2.imwrite(path, f)
                except Exception as exc:
                    self._log_cb(f"[Debug] Could not save {path}: {exc}")

        def _save_masks(stage_idx: int, mask_list):
            if not (self._save_intermediate and idir):
                return
            for k, m in enumerate(mask_list):
                path = os.path.join(
                    idir, f"stage{stage_idx:02d}_bgmask_frame{k:02d}.png"
                )
                try:
                    cv2.imwrite(path, m)
                except Exception as exc:
                    self._log_cb(f"[Debug] Could not save {path}: {exc}")

        def _save_canvas(stage_idx: int, label: str, canvas_bgr):
            if not (self._save_intermediate and idir):
                return
            path = os.path.join(idir, f"stage{stage_idx:02d}_{label}.png")
            try:
                cv2.imwrite(path, canvas_bgr)
            except Exception as exc:
                self._log_cb(f"[Debug] Could not save {path}: {exc}")

        def _save_json(stage_idx: int, label: str, data):
            if not (self._save_intermediate and idir):
                return
            path = os.path.join(idir, f"stage{stage_idx:02d}_{label}.json")
            try:
                with open(path, "w") as fh:
                    json.dump(
                        data,
                        fh,
                        indent=2,
                        default=lambda x: x.tolist()
                        if hasattr(x, "tolist")
                        else str(x),
                    )
            except Exception as exc:
                self._log_cb(f"[Debug] Could not save {path}: {exc}")

        # ─────────────────────────────────────────────────────────────────

        # ── Execution trace (item 2.13) ───────────────────────────────────
        _trace_start = _time.perf_counter()
        _trace: dict = {
            "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "output_path": output_path,
            "frames_input": 0,
            "edges_found": 0,
            "canvas_size": None,
            "fallback_used": False,
            "stage_timings": [],
            "success": False,
            "error": None,
            "finished_at": None,
            "elapsed_seconds": None,
        }
        _stage_t0 = _time.perf_counter()

        def _write_trace():
            _trace["finished_at"] = _dt.datetime.now().isoformat(timespec="seconds")
            _trace["elapsed_seconds"] = round(_time.perf_counter() - _trace_start, 2)
            try:
                trace_dir = os.path.join(
                    os.path.expanduser("~"), ".image-toolkit", "traces"
                )
                os.makedirs(trace_dir, exist_ok=True)
                ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                trace_path = os.path.join(trace_dir, f"stitch_{ts}.json")
                with open(trace_path, "w") as _tf:
                    json.dump(_trace, _tf, indent=2)
                self._log_cb(f"[Trace] Execution trace saved to: {trace_path}")
            except Exception as _te:
                self._log_cb(f"[Trace] Could not write trace: {_te}")

        # ─────────────────────────────────────────────────────────────────

        # Issue 10B: HITL annotation serialization (lazy, no-op if not installed)
        try:
            _hitl_dir = os.path.join(
                os.path.expanduser("~"), ".image-toolkit", "hitl_annotations"
            )
            _coco_builder, _ls_exporter, _hitl_session_dir = create_session_serializers(
                _hitl_dir
            )
            _serialization_ok = True
        except Exception as _se:
            _serialization_ok = False
            _coco_builder = _ls_exporter = None
            self._log_cb(f"[HITL] Annotation serialization unavailable: {_se}")

        def _save_hitl_annotations():
            """Flush COCO + Label Studio annotations to disk (called at each checkpoint)."""
            if not (_serialization_ok and _hitl_session_dir):
                return
            try:
                _os.makedirs(_hitl_session_dir, exist_ok=True)
                _coco_builder.save(
                    _os.path.join(_hitl_session_dir, "annotations_coco.json")
                )
                _ls_exporter.save(
                    _os.path.join(_hitl_session_dir, "annotations_ls.json")
                )
            except Exception as _ae:
                self._log_cb(f"[HITL] Could not save annotations: {_ae}")

        # ─────────────────────────────────────────────────────────────────

        def _emit(idx: int):
            nonlocal _stage_t0
            elapsed = round(_time.perf_counter() - _stage_t0, 3)
            _trace["stage_timings"].append(
                {
                    "stage": idx,
                    "label": _STAGE_LABELS[idx - 1],
                    "elapsed_s": elapsed,
                }
            )
            _stage_t0 = _time.perf_counter()
            self._progress_cb(idx, _STAGE_LABELS[idx - 1])
            self._log_cb(f"[Stage {idx}/{_TOTAL_STAGES}] {_STAGE_LABELS[idx - 1]}")

        _emit(1)
        self._check_cancel()
        frames = self._load_frames(image_paths)
        N = len(frames)
        _trace["frames_input"] = N
        if N < 2:
            raise ValueError("Need at least 2 valid frames to stitch.")
        _save_frames(1, "loaded", frames)

        _emit(2)
        self._check_cancel()
        frames = self._normalise_widths(frames)
        H, W = frames[0].shape[:2]
        _save_frames(2, "normalised", frames)

        _emit(3)
        self._check_cancel()
        if self.use_basic:
            frames = self._apply_basic(frames)
        _save_frames(3, "basic_corrected", frames)

        _emit(4)
        self._check_cancel()
        bg_masks = self._compute_fg_masks(frames)
        _save_masks(4, bg_masks)
        if torch.cuda.is_available() and self._birefnet:
            try:
                BiRefNetWrapper.purge_all_models()
            except Exception:
                pass
            self._birefnet = None
            torch.cuda.empty_cache()

        # HITL checkpoint 1 — frame selection review
        _thumbs = []
        for _f in frames:
            _fh, _fw = _f.shape[:2]
            _sc = min(1.0, 256 / max(_fh, _fw, 1))
            _thumbs.append(
                cv2.resize(
                    _f,
                    (max(1, int(_fw * _sc)), max(1, int(_fh * _sc))),
                    cv2.INTER_AREA,
                )
            )
        _diffs = [0.0]
        for _i in range(1, N):
            _a = (
                cv2.resize(frames[_i - 1], (64, 64), cv2.INTER_AREA).astype(np.float32)
                / 255.0
            )
            _b = (
                cv2.resize(frames[_i], (64, 64), cv2.INTER_AREA).astype(np.float32)
                / 255.0
            )
            _diffs.append(float(np.mean(np.abs(_a - _b))))
        _ov1 = self._hitl_pause(
            "frames",
            {
                "paths": list(image_paths),
                "thumbnails": _thumbs,
                "bg_masks": list(bg_masks),
                "frame_diffs": _diffs,
            },
        )
        if "frame_override" in _ov1:
            _new_paths = _ov1["frame_override"]
            _path_idx = {p: i for i, p in enumerate(image_paths)}
            _keep = [_path_idx[p] for p in _new_paths if p in _path_idx]
            if len(_keep) >= 2:
                image_paths = [image_paths[i] for i in _keep]
                frames = [frames[i] for i in _keep]
                bg_masks = [bg_masks[i] for i in _keep]
                N = len(frames)
                _trace["frames_input"] = N
                self._log_cb(f"[HITL] Frame selection updated: {N} frames.")
        del _thumbs, _diffs

        # HITL checkpoint 1.5 — segmentation / mask review (Issue 10A2 / S83)
        # Passes live SAM-2 predictor+state so MaskReviewDialog click refinement works.
        _ov1_5 = self._hitl_pause(
            "masks",
            {
                "frames": list(frames),
                "bg_masks": list(bg_masks),
                "image_paths": list(image_paths),
                "sam2_predictor": self._sam2_predictor,
                "sam2_inference_state": self._sam2_inference_state,
                "sam2_frame_h": self._sam2_frame_h,
                "sam2_frame_w": self._sam2_frame_w,
            },
        )
        # Free SAM-2 GPU/disk resources now that the dialog has closed
        self._cleanup_sam2_state()
        if "bg_masks" in _ov1_5:
            _new_masks = _ov1_5["bg_masks"]
            if len(_new_masks) == len(frames):
                bg_masks = _new_masks
                self._log_cb("[HITL] Segmentation masks updated by user.")
        if "exclusion_masks" in _ov1_5:
            _ex = _ov1_5["exclusion_masks"]
            if _ex:
                self.exclusion_masks = _ex
                self._log_cb("[HITL] Seam exclusion masks updated by user.")

        # Record confirmed masks into COCO / Label Studio annotation files
        if _serialization_ok:
            for _fi, (_fpath, _mask) in enumerate(zip(image_paths, bg_masks)):
                _fh, _fw = frames[_fi].shape[:2] if _fi < len(frames) else (0, 0)
                _img_id = _coco_builder.add_image(
                    os.path.basename(_fpath), width=_fw, height=_fh, temporal_id=_fi
                )
                if _mask is not None:
                    _coco_builder.add_segmentation_mask(_img_id, _mask)
                _ls_exporter.add_task(_fpath, temporal_id=_fi, model_mask=_mask)
            _save_hitl_annotations()
            self._log_cb(f"[HITL] Annotations saved to {_hitl_session_dir}")

        _emit(5)
        self._check_cancel()
        edges = self._pairwise_match(frames, bg_masks)
        edges = self._filter_edges(edges, image_paths, H, W, frames, bg_masks)
        _save_json(
            5,
            "edges",
            [
                {
                    "i": e["i"],
                    "j": e["j"],
                    "dx": float(e["M"][0, 2]),
                    "dy": float(e["M"][1, 2]),
                    "conf": float(e.get("weight", 0.0)),
                    "method": e.get("method", "?"),
                }
                for e in edges
            ],
        )
        # Purge LoFTR
        if torch.cuda.is_available():
            if self._loftr is not None:
                try:
                    self._loftr.offload()
                except Exception:
                    pass
                self._loftr = None
            torch.cuda.empty_cache()
            gc.collect()
        _trace["edges_found"] = len(edges)

        # HITL checkpoint 2 — edge graph review
        _edge_data = [
            {
                "i": e["i"],
                "j": e["j"],
                "dx": float(e["M"][0, 2]),
                "dy": float(e["M"][1, 2]),
                "conf": float(e.get("weight", 0.0)),
                "method": e.get("method", "?"),
            }
            for e in edges
        ]
        _ov2 = self._hitl_pause(
            "edges",
            {
                "edges": _edge_data,
                "image_paths": list(image_paths),
                "n_frames": N,
            },
        )
        if "edges" in _ov2:
            _e_lookup = {(e["i"], e["j"]): e for e in edges}
            _filtered = []
            _n_manual = 0
            for ed in _ov2["edges"]:
                key = (ed["i"], ed["j"])
                if key in _e_lookup:
                    _filtered.append(_e_lookup[key])
                elif ed.get("method") == "manual":
                    try:
                        _filtered.append(
                            _build_manual_edge(
                                ed["i"],
                                ed["j"],
                                ed["dx"],
                                ed["dy"],
                                weight=ed.get("conf", 0.9),
                            )
                        )
                        _n_manual += 1
                    except Exception as _me:
                        self._log_cb(f"[HITL] Skipping manual edge: {_me}")
            if _filtered:
                edges = _filtered
                _trace["edges_found"] = len(edges)
                self._log_cb(
                    f"[HITL] Edges updated: {len(edges)} kept"
                    f"{f', {_n_manual} manual' if _n_manual else ''}."
                )

        if not edges:
            warnings.warn("[Stitch] No valid edges — falling back to scan stitch.")
            _trace["fallback_used"] = True
            result = self._scan_stitch_fallback(frames, output_path)
            _trace["success"] = True
            _write_trace()
            return result

        _emit(6)
        self._check_cancel()
        use_affine_ba = self.motion_model == "affine"
        affines = _bundle_adjust_affine(edges, N, use_affine=use_affine_ba)
        _save_json(6, "affines_ba", [a.tolist() for a in affines])

        _emit(7)
        self._check_cancel()
        if self.use_ecc:
            affines = self._ecc_refine(frames, affines, bg_masks)
        _save_json(7, "affines_ecc", [a.tolist() for a in affines])

        _emit(8)
        self._check_cancel()
        canvas_h, canvas_w, T_global = self._compute_canvas(frames, affines)
        _trace["canvas_size"] = [canvas_h, canvas_w]
        if canvas_h <= 0 or canvas_w <= 0:
            raise RuntimeError("Computed canvas has zero size.")
        for i in range(N):
            affines[i][0, 2] += T_global[0]
            affines[i][1, 2] += T_global[1]
        _save_json(
            8,
            "canvas_info",
            {
                "canvas_h": canvas_h,
                "canvas_w": canvas_w,
                "frame_h": int(H),
                "frame_w": int(W),
                "T_global": list(T_global),
                "affines_final": [a.tolist() for a in affines],
            },
        )

        # HITL checkpoint 3 — canvas layout inspector (with nudge)
        _c_thumbs = []
        for _f in frames:
            _fh, _fw = _f.shape[:2]
            _sc = min(1.0, 160 / max(_fh, _fw, 1))
            _c_thumbs.append(
                cv2.resize(
                    _f,
                    (max(1, int(_fw * _sc)), max(1, int(_fh * _sc))),
                    cv2.INTER_AREA,
                )
            )
        # Per-row frame count for coverage overlay
        _cov = np.zeros(canvas_h, dtype=np.int32)
        for _a in affines:
            _ty = int(_a[1, 2])
            _r0, _r1 = max(0, _ty), min(canvas_h, _ty + H)
            if _r0 < _r1:
                _cov[_r0:_r1] += 1
        _ov3 = self._hitl_pause(
            "canvas",
            {
                "canvas_h": canvas_h,
                "canvas_w": canvas_w,
                "frame_h": int(H),
                "frame_w": int(W),
                "affines": [a.tolist() for a in affines],
                "image_paths": list(image_paths),
                "thumbnails": _c_thumbs,
                "frame_count_per_row": _cov,
            },
        )
        if "affines" in _ov3:
            _new_aff = _ov3["affines"]
            if len(_new_aff) == N:
                affines = [np.array(a, dtype=np.float64) for a in _new_aff]
                self._log_cb("[HITL] Affines updated from canvas inspector.")
        del _c_thumbs, _cov

        if torch.cuda.is_available():
            try:
                BiRefNetWrapper.purge_all_models()
            except Exception:
                pass
            self._birefnet = self._loftr = self._stitch_net = None
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            gc.collect()

        _emit(9)
        self._check_cancel()
        canvas, valid_mask, warped_corr, warped_fgs = self._render(
            frames, affines, bg_masks, canvas_h, canvas_w
        )
        _save_canvas(9, "temporal_render", canvas)

        # HITL checkpoint 4 — render review (coverage heatmap + preview)
        _prev_sc = min(1.0, 600 / max(canvas_h, 1))
        _canvas_prev = cv2.resize(
            canvas,
            (max(1, int(canvas_w * _prev_sc)), max(1, int(canvas_h * _prev_sc))),
            cv2.INTER_AREA,
        )
        _cov2 = np.zeros(canvas_h, dtype=np.int32)
        for _a in affines:
            _ty = int(_a[1, 2])
            _r0, _r1 = max(0, _ty), min(canvas_h, _ty + H)
            if _r0 < _r1:
                _cov2[_r0:_r1] += 1
        _ov4 = self._hitl_pause(
            "render",
            {
                "canvas_preview": _canvas_prev,
                "frame_count_per_row": _cov2,
                "canvas_h": canvas_h,
                "canvas_w": canvas_w,
            },
        )
        del _canvas_prev, _cov2
        # No override at render stage — review only (user may cancel to retry)
        if _ov4.get("cancel"):
            raise InterruptedError("Stitch cancelled at render review.")

        _emit(10)
        self._check_cancel()
        if self.mfsr_mode:
            try:
                canvas = run_mfsr(
                    frames,
                    affines,
                    canvas_h,
                    canvas_w,
                    quality=75,
                    use_prior=self._mfsr_use_prior,
                    use_diffusion_inpaint=self._mfsr_use_diffusion,
                    n_dct_iter=self._mfsr_n_dct_iter,
                )
                valid_mask = (canvas.max(axis=2) > 0).astype(np.uint8) * 255
                self._log_cb("[Stitch] MFSR refinement complete.")
            except Exception as exc:
                self._log_cb(f"[Stitch] MFSR failed ({exc}); keeping median canvas.")
        else:
            self._log_cb("[Stitch] Stage 10 skipped (mfsr_mode=False).")
        _save_canvas(10, "mfsr", canvas)

        _emit(11)
        self._check_cancel()
        _preset_boundaries = None
        if self.composite_fg and self.use_birefnet:
            # HITL checkpoint 3.5 — seam boundary editor (S85)
            if _compute_initial_boundaries is not None:
                _init_bnd = _compute_initial_boundaries(affines, frames)
                _prev_sc = min(1.0, 600 / max(canvas_h, 1))
                _bnd_prev = cv2.resize(
                    canvas,
                    (
                        max(1, int(canvas_w * _prev_sc)),
                        max(1, int(canvas_h * _prev_sc)),
                    ),
                    cv2.INTER_AREA,
                )
                _ov3_5 = self._hitl_pause(
                    "boundaries",
                    {
                        "canvas_preview": _bnd_prev,
                        "boundaries": _init_bnd.tolist(),
                        "canvas_h": canvas_h,
                        "canvas_w": canvas_w,
                        "frame_count": len(frames),
                    },
                )
                del _bnd_prev
                if "boundaries" in _ov3_5:
                    _user_bnd = _ov3_5["boundaries"]
                    if len(_user_bnd) == len(_init_bnd):
                        _preset_boundaries = np.array(_user_bnd, dtype=np.float64)
                        self._log_cb(
                            f"[HITL] Seam boundaries updated by user: {len(_preset_boundaries)} boundaries."
                        )
            # HITL checkpoint 4.6 — seam diagnostic inspector (S95)
            # Run initial composite to collect per-seam metadata, then surface
            # it to the user before the seam-painter loop.  On non-HITL runs
            # _hitl_pause returns {} immediately and _seam_overrides stays empty.
            _seam_meta: dict = {}
            _seam_overrides: dict = {}
            canvas = self._composite_foreground(
                [],
                [],
                canvas,
                canvas_h,
                canvas_w,
                frames,
                affines,
                bg_masks,
                preset_boundaries=_preset_boundaries,
                seam_meta_out=_seam_meta,
            )
            _prev_sc46 = min(1.0, 600 / max(canvas_h, 1))
            _diag_prev = cv2.resize(
                canvas,
                (
                    max(1, int(canvas_w * _prev_sc46)),
                    max(1, int(canvas_h * _prev_sc46)),
                ),
                cv2.INTER_AREA,
            )
            _ov4_6 = self._hitl_pause(
                "seams",
                {
                    "canvas_preview": _diag_prev,
                    "boundaries": _seam_meta.get("boundaries", []),
                    "seam_post_diffs": _seam_meta.get("seam_post_diffs", {}),
                    "seam_single_pose_keys": list(
                        _seam_meta.get("seam_single_pose", {}).keys()
                    ),
                    "canvas_h": canvas_h,
                    "canvas_w": canvas_w,
                },
            )
            del _diag_prev
            if _ov4_6.get("cancel"):
                raise InterruptedError(
                    "Stitch cancelled at seam-diagnostic checkpoint."
                )
            _seam_overrides = _ov4_6.get("seam_overrides") or {}
            if _seam_overrides:
                canvas = self._composite_foreground(
                    [],
                    [],
                    canvas,
                    canvas_h,
                    canvas_w,
                    frames,
                    affines,
                    bg_masks,
                    preset_boundaries=_preset_boundaries,
                    seam_overrides=_seam_overrides,
                    seam_meta_out=_seam_meta,
                )
                self._log_cb(
                    f"[HITL] Re-composited with {len(_seam_overrides)} seam override(s)."
                )

            # HITL checkpoint 4.5 — post-composite seam painter (S86)
            _paint_mask = None
            _cp45_iter = 0
            while True:
                if _cp45_iter > 0 or _paint_mask is not None:
                    canvas = self._composite_foreground(
                        [],
                        [],
                        canvas,
                        canvas_h,
                        canvas_w,
                        frames,
                        affines,
                        bg_masks,
                        preset_boundaries=_preset_boundaries,
                        paint_mask=_paint_mask,
                        seam_overrides=_seam_overrides,
                    )
                _cp45_iter += 1
                _prev_sc45 = min(1.0, 600 / max(canvas_h, 1))
                _comp_prev = cv2.resize(
                    canvas,
                    (
                        max(1, int(canvas_w * _prev_sc45)),
                        max(1, int(canvas_h * _prev_sc45)),
                    ),
                    cv2.INTER_AREA,
                )
                _ov4_5 = self._hitl_pause(
                    "composite",
                    {
                        "canvas_preview": _comp_prev,
                        "canvas_h": canvas_h,
                        "canvas_w": canvas_w,
                        "iteration": _cp45_iter,
                    },
                )
                del _comp_prev
                _new_mask = _ov4_5.get("paint_mask")
                if _new_mask is None:
                    if _ov4_5.get("cancel"):
                        raise InterruptedError(
                            "Stitch cancelled at seam-painter checkpoint."
                        )
                    break  # user accepted output
                _paint_mask = _new_mask
                self._log_cb(
                    f"[HITL] Re-compositing with seam paint mask (iteration {_cp45_iter + 1})…"
                )

        _save_canvas(11, "fg_composite", canvas)

        _emit(12)
        self._check_cancel()
        canvas = self._crop_to_valid(canvas, valid_mask)
        if self.edge_crop > 0:
            ec = self.edge_crop
            if ec * 2 < canvas.shape[0] and ec * 2 < canvas.shape[1]:
                canvas = canvas[ec:-ec, ec:-ec]
        _save_canvas(12, "cropped", canvas)

        _emit(13)
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out = _Image.fromarray(rgb)
        out.save(output_path)
        gc.collect()
        if self._save_intermediate and idir:
            self._log_cb(f"[Debug] Intermediate outputs saved to: {idir}")
        self._log_cb(f"[Stitch] Saved to '{output_path}'.")

        # HITL checkpoint 5 — final output RLHF feedback (S87)
        _prev_sc5 = min(1.0, 600 / max(canvas_h, 1))
        _out_prev = cv2.resize(
            canvas,
            (max(1, int(canvas_w * _prev_sc5)), max(1, int(canvas_h * _prev_sc5))),
            cv2.INTER_AREA,
        )
        _ov5 = self._hitl_pause(
            "output",
            {
                "canvas_preview": _out_prev,
                "output_path": output_path,
                "pipeline_config": self._pipeline_config,
            },
        )
        del _out_prev
        _fb = _ov5.get("output_feedback")
        if _fb is not None:
            try:
                _store = FeedbackStore()
                _anns = [StitchAnnotation(**a) for a in _fb.get("annotations", [])]
                _store.add_from_image(
                    image_path=output_path,
                    overall_rating=float(_fb.get("overall_rating", 5.0)),
                    annotations=_anns,
                    pipeline_config=self._pipeline_config,
                )
                self._log_cb(
                    f"[HITL] RLHF feedback saved (rating={_fb.get('overall_rating', 5.0):.1f}/10, "
                    f"{len(_anns)} annotation(s))."
                )
            except Exception as _fb_exc:
                self._log_cb(f"[HITL] Could not save RLHF feedback: {_fb_exc}")

        _trace["success"] = True
        _write_trace()

        # S88: autosave HITL session after successful run
        if self._hitl_session_overrides:
            try:
                _sp = autosave_path()
                _save_session_impl(self._hitl_session_overrides, _sp)
                self._current_session_path = _sp
                self._log_cb(f"[HITL] Session saved to '{_sp}'.")
            except Exception as _se:
                self._log_cb(f"[HITL] Could not autosave session: {_se}")

        return out

    def _pairwise_match(self, frames, bg_masks):
        edges = super()._pairwise_match(frames, bg_masks)
        for edge in edges:
            key = (edge["i"], edge["j"])
            if key in self._manual_affines:
                self._log_cb(
                    f"[Stitch] Manual affine override for pair {edge['i']}→{edge['j']}."
                )
                edge["M"] = self._manual_affines[key].copy()
        return edges


# ---------------------------------------------------------------------------
# StitchWorker
# ---------------------------------------------------------------------------


class StitchWorker(QObject):
    sig_stage = Signal(int, int, str)  # (current_stage, total_stages, label)
    sig_log = Signal(str)
    sig_finished = Signal(str)  # output_path
    sig_error = Signal(str)

    # HITL checkpoint signals — emitted when the pipeline pauses for review.
    # Each carries a plain dict of intermediate state (numpy arrays included).
    sig_review_video = Signal(object)  # checkpoint 0: video frame review (Issue 9 S84)
    sig_review_frames = Signal(object)  # after Stage 4: frame selection review
    sig_review_masks = Signal(
        object
    )  # after Stage 4.5: mask / segmentation review (Issue 10A2)
    sig_review_edges = Signal(object)  # after Stage 5: edge graph review
    sig_review_canvas = Signal(object)  # after Stage 8: canvas layout review
    sig_review_boundaries = Signal(object)  # checkpoint 3.5: seam boundary editor (S85)
    sig_review_seams = Signal(object)  # checkpoint 4.6: seam diagnostic inspector (S95)
    sig_review_composite = Signal(
        object
    )  # checkpoint 4.5: post-composite seam painter (S86)
    sig_review_render = Signal(object)  # after Stage 9: render / coverage review
    sig_review_output = Signal(object)  # checkpoint 5: final output RLHF feedback (S87)

    TOTAL_STAGES = _TOTAL_STAGES

    def __init__(
        self,
        image_paths: List[str],
        output_path: str,
        pipeline_config: dict,
        manual_affines: Optional[Dict] = None,
        hitl_mode: bool = False,
        video_path: Optional[str] = None,
        video_n_frames: int = 20,
        video_mode: str = "uniform",
        session_path: Optional[str] = None,
    ):
        super().__init__()
        self._image_paths = image_paths
        self._output_path = output_path
        self._pipeline_config = pipeline_config
        self._manual_affines = manual_affines or {}
        self._cancel_flag: list = [False]
        self._hitl_mode = hitl_mode

        # Issue 9 S84: optional video source for frame extraction
        self._video_path: Optional[str] = video_path
        self._video_n_frames: int = video_n_frames
        self._video_mode: str = video_mode

        # Derive intermediate output directory from output path if requested.
        self._save_intermediate = pipeline_config.get("save_intermediate", False)
        if self._save_intermediate:
            stem = os.path.splitext(os.path.abspath(output_path))[0]
            self._intermediate_dir = stem + "_stages"
        else:
            self._intermediate_dir = ""

        # HITL pause/resume synchronization
        self._hitl_mutex = QMutex()
        self._hitl_wait = QWaitCondition()
        self._hitl_paused: bool = False
        self._hitl_override: dict = {}

        # Issue 10A3: NL seam-routing exclusion masks (set via set_exclusion_masks())
        self._exclusion_masks: Optional[List] = None

        # S88: session persistence — accumulated overrides + optional replay source
        self._hitl_session_overrides: Dict[str, dict] = {}
        self._current_session_path: Optional[str] = None
        self._replay_session: Dict[str, dict] = {}
        if session_path:
            try:
                self._replay_session = load_session(session_path)
            except Exception:
                pass  # bad session file → run interactively

    def cancel(self):
        self._cancel_flag[0] = True
        # Wake up any paused HITL checkpoint so cancel propagates immediately
        if self._hitl_paused:
            self.resume()

    def resume(self):
        """Call from the main thread to resume a paused pipeline checkpoint."""
        self._hitl_mutex.lock()
        self._hitl_paused = False
        self._hitl_wait.wakeAll()
        self._hitl_mutex.unlock()

    def set_frame_override(self, paths: List[str]) -> None:
        """Set frame list override (call before resume() at the frame checkpoint)."""
        self._hitl_override["frame_override"] = paths

    def set_mask_override(self, masks: list) -> None:
        """Set bg_mask list override (call before resume() at the mask checkpoint)."""
        self._hitl_override["bg_masks"] = masks

    def set_exclusion_masks(self, exclusion_masks: list) -> None:
        """Set NL seam-routing exclusion masks (Issue 10A3). Call before resume()."""
        self._hitl_override["exclusion_masks"] = exclusion_masks

    def set_edge_override(self, edges: List[dict]) -> None:
        """Set edge list override (call before resume() at the edge checkpoint)."""
        self._hitl_override["edges"] = edges

    def set_affine_override(self, affines: list) -> None:
        """Set affine matrix override (call before resume() at the canvas checkpoint)."""
        self._hitl_override["affines"] = affines

    def set_boundary_override(self, boundaries: list) -> None:
        """Set seam-boundary y-coordinate override (call before resume() at checkpoint 3.5)."""
        self._hitl_override["boundaries"] = boundaries

    def set_seam_override(self, overrides: dict) -> None:
        """Set per-seam override dict for HITL checkpoint 4.6.

        *overrides* maps seam index k (int or str) → option dict with optional
        keys ``"force_single_pose"`` (bool) and ``"force_blend"`` (bool).
        Call before :meth:`resume` at the seam-diagnostic checkpoint.
        """
        self._hitl_override["seam_overrides"] = {
            int(k): v for k, v in overrides.items()
        }

    def set_paint_mask(self, mask: np.ndarray) -> None:
        """Set canvas-space paint mask for re-composite (call before resume() at checkpoint 4.5)."""
        self._hitl_override["paint_mask"] = mask

    def set_render_cancel(self) -> None:
        """Signal the pipeline to abort at the render review checkpoint."""
        self._hitl_override["cancel"] = True

    def set_output_feedback(self, overall_rating: float, annotations: list) -> None:
        """Store RLHF feedback to persist after checkpoint 5 (call before resume())."""
        self._hitl_override["output_feedback"] = {
            "overall_rating": overall_rating,
            "annotations": annotations,
        }

    # S88 ----------------------------------------------------------------- #

    @property
    def current_session_path(self) -> Optional[str]:
        """Path of the autosaved session JSON (set after a successful run)."""
        return self._current_session_path

    def save_session(self, path: str) -> None:
        """Write accumulated checkpoint overrides to *path*."""
        try:
            _save_session_impl(self._hitl_session_overrides, path)
            self._current_session_path = path
        except Exception:
            pass

    def _make_hitl_pause_cb(self) -> Callable:
        """Return a callable that emits the right signal then blocks the worker thread."""
        _signal_map = {
            "frames": self.sig_review_frames,
            "masks": self.sig_review_masks,
            "edges": self.sig_review_edges,
            "canvas": self.sig_review_canvas,
            "boundaries": self.sig_review_boundaries,
            "seams": self.sig_review_seams,
            "composite": self.sig_review_composite,
            "render": self.sig_review_render,
            "output": self.sig_review_output,
        }

        def _pause_cb(event: str, data: dict) -> dict:
            # Replay mode: return stored override without blocking the worker
            if not self._hitl_mode:
                override = dict(self._replay_session.get(event, {}))
                if override:
                    self._hitl_session_overrides[event] = override
                return override
            sig = _signal_map.get(event)
            if sig is not None:
                sig.emit(data)
            self._hitl_mutex.lock()
            self._hitl_paused = True
            self._hitl_override = {}
            while self._hitl_paused:
                self._hitl_wait.wait(self._hitl_mutex)
            override = dict(self._hitl_override)
            self._hitl_mutex.unlock()
            # Accumulate override for session autosave (skip empty/cancel)
            if override and not override.get("cancel"):
                self._hitl_session_overrides[event] = override
            return override

        return _pause_cb

    def _hitl_video_pause(self, data: dict) -> dict:
        """Pause StitchWorker.run() for video frame review (HITL checkpoint 0 — S84)."""
        # Replay mode: return stored video override without blocking
        if not self._hitl_mode:
            override = dict(self._replay_session.get("video", {}))
            if override:
                self._hitl_session_overrides["video"] = override
            return override
        self.sig_review_video.emit(data)
        self._hitl_mutex.lock()
        self._hitl_paused = True
        self._hitl_override = {}
        while self._hitl_paused:
            self._hitl_wait.wait(self._hitl_mutex)
        override = dict(self._hitl_override)
        self._hitl_mutex.unlock()
        if override and not override.get("cancel"):
            self._hitl_session_overrides["video"] = override
        return override

    def run(self):
        cfg = self._pipeline_config

        def _progress_cb(idx: int, label: str):
            self.sig_stage.emit(idx, _TOTAL_STAGES, label)

        def _log_cb(msg: str):
            self.sig_log.emit(msg)

        # ── Video ingestion pre-run (Issue 9 / S84) ──────────────────────
        image_paths = list(self._image_paths)
        _video_tmp_dir: Optional[str] = None

        if self._video_path:
            self.sig_log.emit(f"[Video] Extracting frames from '{self._video_path}'…")
            try:
                _video_tmp_dir = tempfile.mkdtemp(prefix="asp_video_")
                _vframes, image_paths = ingest_video(
                    self._video_path,
                    _video_tmp_dir,
                    n_frames=self._video_n_frames,
                    mode=self._video_mode,
                )
                self.sig_log.emit(f"[Video] Extracted {len(image_paths)} frames.")
            except Exception as _ve:
                self.sig_error.emit(f"[Video] Ingestion failed: {_ve}")
                return

            # HITL checkpoint 0: let user review and deselect video frames
            if self._hitl_mode and image_paths:
                _thumbs = []
                for _f in _vframes:
                    _fh, _fw = _f.shape[:2]
                    _sc = min(1.0, 256 / max(_fh, _fw, 1))
                    _thumbs.append(
                        cv2.resize(
                            _f,
                            (max(1, int(_fw * _sc)), max(1, int(_fh * _sc))),
                            cv2.INTER_AREA,
                        )
                    )
                _diffs = [0.0]
                for _i in range(1, len(_vframes)):
                    _a = (
                        cv2.resize(_vframes[_i - 1], (64, 64), cv2.INTER_AREA).astype(
                            np.float32
                        )
                        / 255.0
                    )
                    _b = (
                        cv2.resize(_vframes[_i], (64, 64), cv2.INTER_AREA).astype(
                            np.float32
                        )
                        / 255.0
                    )
                    _diffs.append(float(np.mean(np.abs(_a - _b))))

                _ov0 = self._hitl_video_pause(
                    {
                        "paths": list(image_paths),
                        "thumbnails": _thumbs,
                        "frame_diffs": _diffs,
                        "video_path": self._video_path,
                    }
                )
                if "frame_override" in _ov0:
                    _new_paths = _ov0["frame_override"]
                    if len(_new_paths) >= 2:
                        image_paths = _new_paths
                        self.sig_log.emit(
                            f"[HITL] Video frame selection: {len(image_paths)} frames accepted."
                        )

        try:
            pipeline = _ProgressPipeline(
                progress_cb=_progress_cb,
                log_cb=_log_cb,
                manual_affines=self._manual_affines,
                cancel_flag=self._cancel_flag,
                mfsr_n_dct_iter=cfg.get("mfsr_n_dct_iter", 20),
                mfsr_use_prior=cfg.get("mfsr_use_prior", True),
                mfsr_use_diffusion=cfg.get("mfsr_use_diffusion", False),
                save_intermediate=self._save_intermediate,
                intermediate_dir=self._intermediate_dir,
                pause_cb=self._make_hitl_pause_cb(),
                **_build_pipeline_kwargs(cfg),
            )
            # Apply any exclusion masks set via set_exclusion_masks() before run
            if self._exclusion_masks:
                pipeline.exclusion_masks = self._exclusion_masks
            pipeline.run(image_paths, self._output_path)
            self.sig_finished.emit(self._output_path)
        except InterruptedError as e:
            self.sig_error.emit(f"Cancelled: {e}")
        except Exception as e:
            self.sig_error.emit(str(e))
        finally:
            if _video_tmp_dir:
                shutil.rmtree(_video_tmp_dir, ignore_errors=True)

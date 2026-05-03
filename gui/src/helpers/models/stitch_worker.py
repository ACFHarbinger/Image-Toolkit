"""
gui/src/helpers/models/stitch_worker.py
========================================
Worker threads for the EditTab (panorama stitching, per-image adjustment,
and canvas composition).

Workers
-------
  StitchWorker       Full AnimeStitchPipeline in a QThread with per-stage
                     progress signals and optional manual affine overrides.
  MatchWorker        LoFTR match preview on a single frame pair.
  MaskPreviewWorker  BiRefNet foreground mask for a single frame.
  AdjustWorker       PIL-based per-image tone/color/geometric adjustments.
  CanvasWorker       PIL-based multi-image layout composer.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal

# ---------------------------------------------------------------------------
# Optional dependencies — guarded so the tab can load even if not installed
# ---------------------------------------------------------------------------

try:
    from backend.src.core.anime_stitch_pipeline import AnimeStitchPipeline
    _PIPELINE_OK = True
except ImportError:
    _PIPELINE_OK = False
    AnimeStitchPipeline = None  # type: ignore[misc,assignment]

try:
    from backend.src.models.loftr_wrapper import LoFTRWrapper
    _LOFTR_OK = True
except ImportError:
    _LOFTR_OK = False
    LoFTRWrapper = None  # type: ignore[misc,assignment]

try:
    from backend.src.models.birefnet_wrapper import BiRefNetWrapper
    _BIREFNET_OK = True
except ImportError:
    _BIREFNET_OK = False
    BiRefNetWrapper = None  # type: ignore[misc,assignment]

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    _PIL_OK = True
except ImportError:
    _PIL_OK = False
    Image = ImageEnhance = ImageFilter = ImageOps = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# _ProgressPipeline — AnimeStitchPipeline subclass with progress callbacks
# ---------------------------------------------------------------------------

_STAGE_LABELS = [
    "Loading & trimming frames",          # 1
    "Normalising widths",                 # 2
    "BaSiC photometric correction",       # 3
    "BiRefNet foreground masking",        # 4
    "LoFTR pairwise matching",            # 5
    "Bundle adjustment",                  # 6
    "ECC sub-pixel refinement",           # 7
    "Building canvas",                    # 8
    "Temporal median render",             # 9
    "Compositing foreground",             # 10
    "Multi-band seam blend",              # 11
    "Boundary crop",                      # 12
    "Saving output",                      # 13
]
_TOTAL_STAGES = len(_STAGE_LABELS)


if _PIPELINE_OK:
    class _ProgressPipeline(AnimeStitchPipeline):
        """
        Thin subclass of AnimeStitchPipeline that adds per-stage progress
        callbacks and optional manual affine overrides for specific frame pairs.
        """

        def __init__(
            self,
            progress_cb,
            log_cb,
            manual_affines: Optional[Dict] = None,
            cancel_flag: Optional[list] = None,
            **kwargs,
        ):
            super().__init__(**kwargs)
            self._progress_cb = progress_cb
            self._log_cb = log_cb
            self._manual_affines = manual_affines or {}
            self._cancel_flag = cancel_flag or [False]

        def _check_cancel(self):
            if self._cancel_flag[0]:
                raise InterruptedError("Stitch cancelled by user.")

        def run(self, image_paths: List[str], output_path: str):
            import gc
            import warnings
            from PIL import Image as _Image
            from backend.src.core.anime_stitch_pipeline import _bundle_adjust_affine

            def _emit(idx: int):
                self._progress_cb(idx, _STAGE_LABELS[idx - 1])
                self._log_cb(f"[Stage {idx}/{_TOTAL_STAGES}] {_STAGE_LABELS[idx - 1]}")

            _emit(1)
            self._check_cancel()
            frames = self._load_frames(image_paths)
            N = len(frames)
            if N < 2:
                raise ValueError("Need at least 2 valid frames to stitch.")

            _emit(2)
            self._check_cancel()
            frames = self._normalise_widths(frames)

            _emit(3)
            self._check_cancel()
            if self.use_basic:
                frames = self._apply_basic(frames)

            _emit(4)
            self._check_cancel()
            bg_masks = self._compute_fg_masks(frames)

            _emit(5)
            self._check_cancel()
            edges = self._pairwise_match(frames, bg_masks)
            if not edges:
                warnings.warn("[Stitch] No valid edges — falling back to scan stitch.")
                return self._scan_stitch_fallback(frames, output_path)

            _emit(6)
            self._check_cancel()
            affines = _bundle_adjust_affine(edges, N)

            _emit(7)
            self._check_cancel()
            if self.use_ecc:
                affines = self._ecc_refine(frames, affines, bg_masks)

            _emit(8)
            self._check_cancel()
            canvas_h, canvas_w, T_global = self._compute_canvas(frames, affines)
            if canvas_h <= 0 or canvas_w <= 0:
                raise RuntimeError("Computed canvas has zero size.")
            for i in range(N):
                affines[i][0, 2] += T_global[0]
                affines[i][1, 2] += T_global[1]

            _emit(9)
            self._check_cancel()
            canvas, valid_mask = self._render(frames, affines, bg_masks, canvas_h, canvas_w)

            _emit(10)
            self._check_cancel()
            if self.composite_fg and self.use_birefnet:
                canvas = self._composite_foreground(
                    frames, affines, bg_masks, canvas, canvas_h, canvas_w
                )

            _emit(11)
            self._check_cancel()

            _emit(12)
            self._check_cancel()
            canvas = self._crop_to_valid(canvas, valid_mask)

            _emit(13)
            rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            out = _Image.fromarray(rgb)
            out.save(output_path)
            gc.collect()
            self._log_cb(f"[Stitch] Saved to '{output_path}'.")
            return out

        def _pairwise_match(self, frames, bg_masks):
            edges = super()._pairwise_match(frames, bg_masks)
            for edge in edges:
                key = (edge["i"], edge["j"])
                if key in self._manual_affines:
                    self._log_cb(
                        f"[Stitch] Using manual affine override for pair "
                        f"{edge['i']}→{edge['j']}."
                    )
                    edge["M"] = self._manual_affines[key].copy()
            return edges


# ---------------------------------------------------------------------------
# StitchWorker
# ---------------------------------------------------------------------------


class StitchWorker(QObject):
    sig_stage = Signal(int, int, str)   # (current_stage, total_stages, label)
    sig_log = Signal(str)
    sig_finished = Signal(str)          # output_path
    sig_error = Signal(str)

    TOTAL_STAGES = _TOTAL_STAGES

    def __init__(
        self,
        image_paths: List[str],
        output_path: str,
        pipeline_config: dict,
        manual_affines: Optional[Dict] = None,
    ):
        super().__init__()
        self._image_paths = image_paths
        self._output_path = output_path
        self._pipeline_config = pipeline_config
        self._manual_affines = manual_affines or {}
        self._cancel_flag: list = [False]

    def cancel(self):
        self._cancel_flag[0] = True

    def run(self):
        if not _PIPELINE_OK:
            self.sig_error.emit(
                "AnimeStitchPipeline is not available. "
                "Ensure scipy, kornia, and transformers are installed."
            )
            return

        cfg = self._pipeline_config

        def _progress_cb(idx: int, label: str):
            self.sig_stage.emit(idx, _TOTAL_STAGES, label)

        def _log_cb(msg: str):
            self.sig_log.emit(msg)

        try:
            pipeline = _ProgressPipeline(
                progress_cb=_progress_cb,
                log_cb=_log_cb,
                manual_affines=self._manual_affines,
                cancel_flag=self._cancel_flag,
                use_basic=cfg.get("use_basic", True),
                use_birefnet=cfg.get("use_birefnet", True),
                use_loftr=cfg.get("use_loftr", True),
                use_ecc=cfg.get("use_ecc", True),
                renderer=cfg.get("renderer", "median"),
                composite_fg=cfg.get("composite_fg", True),
                laplacian_bands=cfg.get("laplacian_bands", 5),
                stitch_net_ckpt=cfg.get("stitch_net_ckpt", ""),
            )
            pipeline.run(self._image_paths, self._output_path)
            self.sig_finished.emit(self._output_path)
        except InterruptedError as e:
            self.sig_error.emit(f"Cancelled: {e}")
        except Exception as e:
            self.sig_error.emit(str(e))


# ---------------------------------------------------------------------------
# MatchWorker — lightweight LoFTR worker for the match preview
# ---------------------------------------------------------------------------


class MatchWorker(QObject):
    sig_finished = Signal(object, object, object)  # pts1 (K,2), pts2 (K,2), conf (K,)
    sig_error = Signal(str)

    def __init__(
        self,
        img_path_a: str,
        img_path_b: str,
        conf_thresh: float = 0.4,
        use_birefnet: bool = True,
    ):
        super().__init__()
        self._path_a = img_path_a
        self._path_b = img_path_b
        self._conf_thresh = conf_thresh
        self._use_birefnet = use_birefnet

    def run(self):
        if not _LOFTR_OK:
            self.sig_error.emit("LoFTR is not available. Ensure kornia is installed.")
            return
        try:
            img_a = cv2.imread(self._path_a)
            img_b = cv2.imread(self._path_b)
            if img_a is None or img_b is None:
                self.sig_error.emit("Could not read one or both images.")
                return

            mask_a: Optional[np.ndarray] = None
            mask_b: Optional[np.ndarray] = None
            if self._use_birefnet and _BIREFNET_OK:
                br = BiRefNetWrapper()
                if hasattr(br, "get_background_mask"):
                    mask_a = br.get_background_mask(img_a)
                    mask_b = br.get_background_mask(img_b)

            wrapper = LoFTRWrapper()
            pts1, pts2, conf = wrapper.match_masked(
                img_a, img_b, mask_a, mask_b, conf_thresh=self._conf_thresh
            )
            self.sig_finished.emit(pts1, pts2, conf)
        except Exception as e:
            self.sig_error.emit(str(e))


# ---------------------------------------------------------------------------
# MaskPreviewWorker — runs BiRefNet on a single frame
# ---------------------------------------------------------------------------


class MaskPreviewWorker(QObject):
    sig_finished = Signal(object)   # np.ndarray (H,W) uint8
    sig_error = Signal(str)

    def __init__(self, img_path: str):
        super().__init__()
        self._path = img_path

    def run(self):
        if not _BIREFNET_OK:
            self.sig_error.emit("BiRefNet is not available.")
            return
        try:
            img = cv2.imread(self._path)
            if img is None:
                self.sig_error.emit("Could not read image.")
                return
            br = BiRefNetWrapper()
            if hasattr(br, "get_background_mask"):
                mask = br.get_background_mask(img)
            else:
                fg = br.get_mask(img)
                mask = cv2.bitwise_not(fg)
            self.sig_finished.emit(mask)
        except Exception as e:
            self.sig_error.emit(str(e))


# ---------------------------------------------------------------------------
# Shared PIL helpers (used by AdjustWorker and CanvasWorker)
# ---------------------------------------------------------------------------


def _pil_to_qimage(pil_img):
    """Convert a PIL Image to a QImage (thread-safe — no QPixmap)."""
    from PySide6.QtGui import QImage
    rgb = pil_img.convert("RGB")
    data = rgb.tobytes()
    w, h = rgb.size
    return QImage(data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


def _apply_adjustments(pil_img, params: dict):
    """
    Apply layered adjustments to a PIL Image and return the result.

    params keys (all optional, sensible defaults):
        crop_ar       (int, int) | None   — target aspect ratio (w, h) for center-crop
        rotate        float               — CW rotation in degrees
        flip_h        bool
        flip_v        bool
        brightness    int  -100..100      — 0 = no change
        contrast      int  -100..100
        gamma         int  10..500        — stored as gamma*100; 100 = 1.00
        saturation    int  -100..100
        hue           int  -180..180      — hue shift in degrees
        sharpen       int  0..100
        blur          int  0..50
    """
    img = pil_img.copy()

    # 1. Aspect-ratio center-crop
    ar = params.get("crop_ar")
    if ar:
        aw, ah = ar
        iw, ih = img.size
        target_ratio = aw / ah
        current_ratio = iw / ih
        if current_ratio > target_ratio:
            new_w = int(ih * target_ratio)
            left = (iw - new_w) // 2
            img = img.crop((left, 0, left + new_w, ih))
        elif current_ratio < target_ratio:
            new_h = int(iw / target_ratio)
            top = (ih - new_h) // 2
            img = img.crop((0, top, iw, top + new_h))

    # 2. Rotation (positive = CW, PIL rotates CCW so negate)
    angle = params.get("rotate", 0.0)
    if abs(angle) > 0.01:
        img = img.rotate(-angle, expand=True, resample=Image.Resampling.BICUBIC)

    # 3. Flip
    if params.get("flip_h", False):
        img = ImageOps.mirror(img)
    if params.get("flip_v", False):
        img = ImageOps.flip(img)

    if img.mode != "RGB":
        img = img.convert("RGB")

    # 4. Brightness  (-100..100 → PIL factor 0.0..2.0)
    b = params.get("brightness", 0) / 100.0
    if b != 0.0:
        img = ImageEnhance.Brightness(img).enhance(max(0.0, 1.0 + b))

    # 5. Contrast
    c = params.get("contrast", 0) / 100.0
    if c != 0.0:
        img = ImageEnhance.Contrast(img).enhance(max(0.0, 1.0 + c))

    # 6. Gamma  (stored as int*100; 100=1.00; applied as power 1/gamma)
    gamma = params.get("gamma", 100) / 100.0
    if abs(gamma - 1.0) > 0.005:
        arr = np.array(img, dtype=np.float32)
        arr = np.clip(np.power(arr / 255.0, 1.0 / gamma) * 255.0, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

    # 7. Saturation
    s = params.get("saturation", 0) / 100.0
    if s != 0.0:
        img = ImageEnhance.Color(img).enhance(max(0.0, 1.0 + s))

    # 8. Hue shift  (OpenCV H is 0-179, half of 360°)
    hue_deg = params.get("hue", 0)
    if hue_deg != 0:
        arr = np.array(img)
        hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV).astype(np.int32)
        hsv[..., 0] = (hsv[..., 0] + hue_deg // 2 + 900) % 180
        img = Image.fromarray(cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB))

    # 9. Sharpen  (0..100 → PIL factor 1.0..11.0)
    sh = params.get("sharpen", 0)
    if sh > 0:
        img = ImageEnhance.Sharpness(img).enhance(1.0 + sh / 10.0)

    # 10. Blur  (0..50 → Gaussian radius 0..10)
    bl = params.get("blur", 0)
    if bl > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=bl / 5.0))

    if img.mode != "RGB":
        img = img.convert("RGB")

    # 11. White balance temperature (+100=warm/amber, -100=cool/blue)
    temp = params.get("temperature", 0)
    if temp != 0:
        arr = np.array(img, dtype=np.float32)
        t = temp / 100.0
        arr[:, :, 0] = np.clip(arr[:, :, 0] * (1.0 + t * 0.30), 0, 255)  # R
        arr[:, :, 2] = np.clip(arr[:, :, 2] * (1.0 - t * 0.25), 0, 255)  # B
        img = Image.fromarray(arr.astype(np.uint8))

    # 12. Tint (+100=magenta, -100=green)
    tint_v = params.get("tint", 0)
    if tint_v != 0:
        arr = np.array(img, dtype=np.float32)
        t = tint_v / 100.0
        arr[:, :, 0] = np.clip(arr[:, :, 0] * (1.0 + t * 0.15), 0, 255)
        arr[:, :, 1] = np.clip(arr[:, :, 1] * (1.0 - t * 0.20), 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] * (1.0 + t * 0.10), 0, 255)
        img = Image.fromarray(arr.astype(np.uint8))

    # 13. Shadows (-100=crush, +100=lift)
    shadows = params.get("shadows", 0)
    if shadows != 0:
        arr = np.array(img, dtype=np.float32) / 255.0
        fade = np.clip(1.0 - arr * 2.0, 0.0, 1.0)
        arr = np.clip(arr + (shadows / 200.0) * fade, 0.0, 1.0)
        img = Image.fromarray((arr * 255).astype(np.uint8))

    # 14. Highlights (-100=recover, +100=boost)
    highlights = params.get("highlights", 0)
    if highlights != 0:
        arr = np.array(img, dtype=np.float32) / 255.0
        fade = np.clip((arr - 0.5) * 2.0, 0.0, 1.0)
        arr = np.clip(arr + (highlights / 200.0) * fade, 0.0, 1.0)
        img = Image.fromarray((arr * 255).astype(np.uint8))

    # 15. Vibrance — selective saturation (boosts desaturated colours more)
    vibrance = params.get("vibrance", 0)
    if vibrance != 0:
        arr = np.array(img)
        hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV).astype(np.float32)
        s_ch = hsv[:, :, 1] / 255.0
        boost = (vibrance / 100.0) * (1.0 - s_ch)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] + boost * 100.0, 0, 255)
        img = Image.fromarray(cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB))

    # 16. Auto white balance (gray-world assumption)
    if params.get("auto_wb", False):
        arr = np.array(img, dtype=np.float32)
        r_m = arr[:, :, 0].mean()
        g_m = arr[:, :, 1].mean()
        b_m = arr[:, :, 2].mean()
        mu = (r_m + g_m + b_m) / 3.0
        if r_m > 1:
            arr[:, :, 0] = np.clip(arr[:, :, 0] * mu / r_m, 0, 255)
        if g_m > 1:
            arr[:, :, 1] = np.clip(arr[:, :, 1] * mu / g_m, 0, 255)
        if b_m > 1:
            arr[:, :, 2] = np.clip(arr[:, :, 2] * mu / b_m, 0, 255)
        img = Image.fromarray(arr.astype(np.uint8))

    return img


def _scale_pil_image(im, cell_w: int, cell_h: int, scale_mode: str):
    """Scale a PIL Image to fit a cell according to scale_mode (fit/fill/stretch)."""
    if cell_w <= 0 or cell_h <= 0:
        return im
    iw, ih = im.size
    if scale_mode == "stretch":
        return im.resize((cell_w, cell_h), Image.Resampling.LANCZOS)
    elif scale_mode == "fill":
        r_cell = cell_w / cell_h
        r_img = iw / ih
        if r_img > r_cell:
            new_h = cell_h
            new_w = int(iw * cell_h / ih)
            resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - cell_w) // 2
            return resized.crop((left, 0, left + cell_w, cell_h))
        else:
            new_w = cell_w
            new_h = int(ih * cell_w / iw)
            resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
            top = (new_h - cell_h) // 2
            return resized.crop((0, top, cell_w, top + cell_h))
    else:  # fit — letterbox with black bars
        r_cell = cell_w / cell_h
        r_img = iw / ih
        if r_img > r_cell:
            new_w = cell_w
            new_h = int(ih * cell_w / iw)
        else:
            new_h = cell_h
            new_w = int(iw * cell_h / ih)
        resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        bg_img = Image.new("RGB", (cell_w, cell_h), (0, 0, 0))
        bg_img.paste(resized, ((cell_w - new_w) // 2, (cell_h - new_h) // 2))
        return bg_img


# ---------------------------------------------------------------------------
# AdjustWorker
# ---------------------------------------------------------------------------


class AdjustWorker(QObject):
    """
    Applies color/tone/geometric adjustments to a single image in a QThread.

    Emits sig_finished(QImage) on success.  Pass max_size to downscale the
    source image first for faster preview rendering.
    """

    sig_finished = Signal(object)   # QImage
    sig_error = Signal(str)

    def __init__(self, img_path: str, params: dict, max_size: Optional[int] = None):
        super().__init__()
        self._path = img_path
        self._params = params
        self._max_size = max_size

    def run(self):
        if not _PIL_OK:
            self.sig_error.emit("Pillow is not installed.")
            return
        try:
            img = Image.open(self._path)
            if self._max_size:
                w, h = img.size
                if max(w, h) > self._max_size:
                    scale = self._max_size / max(w, h)
                    img = img.resize(
                        (int(w * scale), int(h * scale)),
                        Image.Resampling.LANCZOS,
                    )
            result = _apply_adjustments(img, self._params)
            self.sig_finished.emit(_pil_to_qimage(result))
        except Exception as e:
            self.sig_error.emit(str(e))


# ---------------------------------------------------------------------------
# CanvasWorker
# ---------------------------------------------------------------------------


class GraphStitchWorker(QObject):
    """
    Executes a DAG of stitch operations in topological order.

    Each plan step is a dict:
        {
          "id":     str,         # unique step identifier (referenced by later steps)
          "name":   str,         # display name
          "inputs": list[str],   # image paths or step IDs from earlier steps
          "output": str,         # output file path
        }

    Steps are executed sequentially in list order. After each step its output
    path is stored under its ID so later steps can reference it by ID.
    """

    sig_step  = Signal(int, int, str)   # (current_step, total_steps, step_name)
    sig_stage = Signal(int, int, str)   # (stage, total_stages, label) within step
    sig_log   = Signal(str)
    sig_finished = Signal(list)         # list of output paths
    sig_error    = Signal(str)

    def __init__(self, plan: List[Dict], pipeline_config: dict):
        super().__init__()
        self._plan = plan
        self._cfg  = pipeline_config
        self._cancel_flag: list = [False]

    def cancel(self):
        self._cancel_flag[0] = True

    def run(self):
        if not _PIPELINE_OK:
            self.sig_error.emit(
                "AnimeStitchPipeline is not available. "
                "Ensure scipy, kornia, and transformers are installed."
            )
            return

        cfg          = self._cfg
        step_outputs: Dict[str, str] = {}
        output_paths: List[str]      = []
        total = len(self._plan)

        for idx, step in enumerate(self._plan):
            if self._cancel_flag[0]:
                self.sig_error.emit("Cancelled.")
                return

            step_id   = step.get("id",     f"step_{idx}")
            step_name = step.get("name",   f"Step {idx + 1}")
            self.sig_step.emit(idx + 1, total, step_name)
            self.sig_log.emit(f"\n=== {step_name} ===")

            # Resolve inputs: may be file paths or IDs of earlier steps
            resolved: List[str] = []
            for inp in step.get("inputs", []):
                resolved.append(step_outputs.get(inp, inp))

            if len(resolved) < 2:
                self.sig_error.emit(
                    f"Step '{step_name}' needs ≥ 2 inputs; got {len(resolved)}."
                )
                return

            out_path = step.get("output", "")
            if not out_path:
                self.sig_error.emit(f"Step '{step_name}' has no output path set.")
                return

            def _progress_cb(stage_idx: int, label: str):
                self.sig_stage.emit(stage_idx, _TOTAL_STAGES, label)

            def _log_cb(msg: str):
                self.sig_log.emit(msg)

            try:
                pipeline = _ProgressPipeline(
                    progress_cb=_progress_cb,
                    log_cb=_log_cb,
                    cancel_flag=self._cancel_flag,
                    use_basic      = cfg.get("use_basic",       True),
                    use_birefnet   = cfg.get("use_birefnet",    True),
                    use_loftr      = cfg.get("use_loftr",       True),
                    use_ecc        = cfg.get("use_ecc",         True),
                    renderer       = cfg.get("renderer",        "median"),
                    composite_fg   = cfg.get("composite_fg",    True),
                    laplacian_bands= cfg.get("laplacian_bands", 5),
                    stitch_net_ckpt= cfg.get("stitch_net_ckpt", ""),
                )
                pipeline.run(resolved, out_path)
                step_outputs[step_id] = out_path
                output_paths.append(out_path)
                self.sig_log.emit(f"[Graph] '{step_name}' → '{out_path}'")
            except InterruptedError:
                self.sig_error.emit("Cancelled.")
                return
            except Exception as e:
                self.sig_error.emit(f"Step '{step_name}' failed: {e}")
                return

        self.sig_finished.emit(output_paths)


class CanvasWorker(QObject):
    """
    Composes multiple images into a single canvas in a QThread.

    params keys:
        output_w      int
        output_h      int
        layout        str  'horizontal' | 'vertical' | 'grid'
        grid_cols     int  (grid layout only)
        gap           int  pixels between cells
        bg_color      (R, G, B)
        scale_mode    str  'fit' | 'fill' | 'stretch'

    When preview=True the output is downscaled to max 900px on the long side.
    """

    sig_finished = Signal(object)   # QImage
    sig_error = Signal(str)

    def __init__(self, paths: List[str], params: dict, preview: bool = False):
        super().__init__()
        self._paths = paths
        self._params = params
        self._preview = preview

    def run(self):
        if not _PIL_OK:
            self.sig_error.emit("Pillow is not installed.")
            return
        try:
            import math

            out_w = self._params["output_w"]
            out_h = self._params["output_h"]
            layout = self._params.get("layout", "horizontal")
            gap = self._params.get("gap", 8)
            bg = tuple(self._params.get("bg_color", (0, 0, 0)))
            scale_mode = self._params.get("scale_mode", "fit")
            grid_cols = max(1, self._params.get("grid_cols", 2))

            images = []
            for p in self._paths:
                try:
                    images.append(Image.open(p).convert("RGB"))
                except Exception:
                    continue

            if not images:
                self.sig_error.emit("No valid images to compose.")
                return

            canvas = Image.new("RGB", (out_w, out_h), bg)
            n = len(images)

            if layout == "horizontal":
                avail_w = out_w - gap * max(0, n - 1)
                cell_w = max(1, avail_w // n)
                cell_h = out_h
                for i, im in enumerate(images):
                    x = i * (cell_w + gap)
                    canvas.paste(_scale_pil_image(im, cell_w, cell_h, scale_mode), (x, 0))

            elif layout == "vertical":
                avail_h = out_h - gap * max(0, n - 1)
                cell_w = out_w
                cell_h = max(1, avail_h // n)
                for i, im in enumerate(images):
                    y = i * (cell_h + gap)
                    canvas.paste(_scale_pil_image(im, cell_w, cell_h, scale_mode), (0, y))

            else:  # grid
                rows = max(1, math.ceil(n / grid_cols))
                cols = grid_cols
                avail_w = out_w - gap * max(0, cols - 1)
                avail_h = out_h - gap * max(0, rows - 1)
                cell_w = max(1, avail_w // cols)
                cell_h = max(1, avail_h // rows)
                for i, im in enumerate(images):
                    row_i = i // cols
                    col_i = i % cols
                    x = col_i * (cell_w + gap)
                    y = row_i * (cell_h + gap)
                    canvas.paste(_scale_pil_image(im, cell_w, cell_h, scale_mode), (x, y))

            if self._preview:
                max_dim = 900
                w, h = canvas.size
                if max(w, h) > max_dim:
                    scale = max_dim / max(w, h)
                    canvas = canvas.resize(
                        (int(w * scale), int(h * scale)),
                        Image.Resampling.LANCZOS,
                    )

            self.sig_finished.emit(_pil_to_qimage(canvas))
        except Exception as e:
            self.sig_error.emit(str(e))

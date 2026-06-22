"""
GroundingDINO wrapper — Issue 10A1 (text prompt → bounding box detection).

Provides a thin, lazy-loading wrapper around GroundingDINO so the rest of the
pipeline can call ``_detect_objects(frame, "the girl with the blue uniform")``
and receive a list of [x1, y1, x2, y2] bounding boxes without caring whether
GroundingDINO is installed.

When GroundingDINO is not available the functions return empty lists and emit a
warning exactly once per process. This keeps the pipeline running without the
optional dependency.

Install: pip install groundingdino-py  (or the SAM2+GroundingDINO bundle)
Checkpoint: ~/.grounding_dino/groundingdino_swint_ogc.pth
Config:     ~/.grounding_dino/GroundingDINO_SwinT_OGC.py
"""

from __future__ import annotations

# --- Relocated Nested Imports ---
try:
    import groundingdino  # noqa: F401  type: ignore
except ImportError:
    groundingdino = None

try:
    import torch
except ImportError:
    torch = None

try:
    from groundingdino.util.inference import load_model  # type: ignore
except ImportError:
    load_model = None

try:
    from groundingdino.util.inference import predict  # type: ignore
except ImportError:
    predict = None

try:
    from torchvision.transforms import functional as TF  # type: ignore
except ImportError:
    TF = None
# --------------------------------


import os
import warnings
from typing import List, Optional, Tuple

import cv2
import numpy as np

# Module-level lazy singletons so the heavy model loads only once per process.
_gdino_model = None
_gdino_warned = False


def _gdino_available() -> bool:
    """Return True if groundingdino can be imported."""
    return groundingdino is not None


def _load_grounding_dino():
    """Lazy-load the GroundingDINO model. Returns None if not available."""
    global _gdino_model, _gdino_warned
    if _gdino_model is not None:
        return _gdino_model

    if not _gdino_available():
        if not _gdino_warned:
            warnings.warn(
                "[ASP] GroundingDINO not installed. "
                "Text-prompt segmentation is unavailable. "
                "Install with: pip install groundingdino-py",
                ImportWarning,
                stacklevel=3,
            )
            _gdino_warned = True
        return None

    try:
        # relocated: import torch
        # relocated: from groundingdino.util.inference import load_model  # type: ignore

        ckpt = os.path.expanduser(
            os.environ.get(
                "GROUNDING_DINO_CKPT",
                "~/.grounding_dino/groundingdino_swint_ogc.pth",
            )
        )
        cfg = os.path.expanduser(
            os.environ.get(
                "GROUNDING_DINO_CFG",
                "~/.grounding_dino/GroundingDINO_SwinT_OGC.py",
            )
        )
        if not os.path.isfile(ckpt):
            warnings.warn(
                f"[ASP] GroundingDINO checkpoint not found at {ckpt}. "
                "Download from the GroundingDINO release page and set GROUNDING_DINO_CKPT.",
                RuntimeWarning,
                stacklevel=3,
            )
            return None
        if not os.path.isfile(cfg):
            warnings.warn(
                f"[ASP] GroundingDINO config not found at {cfg}. "
                "Set GROUNDING_DINO_CFG to the correct path.",
                RuntimeWarning,
                stacklevel=3,
            )
            return None

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _gdino_model = load_model(cfg, ckpt, device=device)
        print(f"[ASP] GroundingDINO loaded ({device})")
        return _gdino_model

    except Exception as e:
        if not _gdino_warned:
            warnings.warn(f"[ASP] GroundingDINO load failed: {e}", RuntimeWarning, stacklevel=3)
            _gdino_warned = True
        return None


def _detect_objects(
    frame: np.ndarray,
    text_prompt: str,
    *,
    box_threshold: float = 0.35,
    text_threshold: float = 0.25,
) -> List[np.ndarray]:
    """
    Detect objects matching *text_prompt* in *frame* using GroundingDINO.

    Parameters
    ----------
    frame : uint8 BGR (H, W, 3) — the input frame.
    text_prompt : natural language description, e.g. ``"girl with blue uniform"``.
    box_threshold : minimum confidence for a box to be kept (default 0.35).
    text_threshold : minimum text-token confidence (default 0.25).

    Returns
    -------
    boxes : list of float32 arrays shaped (4,) each as [x1, y1, x2, y2] in
            pixel coordinates of the original frame. Empty list if GroundingDINO
            is unavailable or no detection exceeds the threshold.
    """
    model = _load_grounding_dino()
    if model is None:
        return []
    if not text_prompt.strip():
        return []

    try:
        # relocated: import torch
        # relocated: from groundingdino.util.inference import predict  # type: ignore
        # relocated: from torchvision.transforms import functional as TF  # type: ignore

        H, W = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # GroundingDINO expects a normalised float tensor (ImageNet stats)
        img_tensor = TF.to_tensor(rgb)
        img_tensor = TF.normalize(
            img_tensor, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
        )

        # Predict returns boxes in (cx, cy, w, h) normalised [0,1]
        with torch.no_grad():
            boxes_norm, logits, _ = predict(
                model=model,
                image=img_tensor,
                caption=text_prompt.lower().strip().rstrip("."),
                box_threshold=box_threshold,
                text_threshold=text_threshold,
            )

        if boxes_norm is None or len(boxes_norm) == 0:
            return []

        # Convert normalised (cx, cy, w, h) → absolute pixel (x1, y1, x2, y2)
        boxes_arr = boxes_norm.cpu().numpy()  # (N, 4) float32
        results: List[np.ndarray] = []
        for cx, cy, bw, bh in boxes_arr:
            x1 = max(0.0, (cx - bw / 2) * W)
            y1 = max(0.0, (cy - bh / 2) * H)
            x2 = min(float(W), (cx + bw / 2) * W)
            y2 = min(float(H), (cy + bh / 2) * H)
            results.append(np.array([x1, y1, x2, y2], dtype=np.float32))
        return results

    except Exception as e:
        warnings.warn(f"[ASP] GroundingDINO inference failed: {e}", RuntimeWarning, stacklevel=2)
        return []


def _detect_best_box(
    frame: np.ndarray,
    text_prompt: str,
    *,
    box_threshold: float = 0.35,
    text_threshold: float = 0.25,
) -> Optional[np.ndarray]:
    """
    Return the single highest-confidence bounding box for *text_prompt*, or None.

    This is the primary entry point for Grounded SAM-2:
      bbox = _detect_best_box(frame, "the girl with the blue uniform")
      # → float32 [x1, y1, x2, y2] or None
    """
    boxes = _detect_objects(
        frame, text_prompt,
        box_threshold=box_threshold,
        text_threshold=text_threshold,
    )
    return boxes[0] if boxes else None


def _detect_exclusion_mask(
    frame: np.ndarray,
    text_prompt: str,
    *,
    box_threshold: float = 0.30,
    text_threshold: float = 0.25,
    dilate_px: int = 10,
) -> Optional[np.ndarray]:
    """
    Detect *text_prompt* in *frame* and return a binary exclusion mask (uint8).

    Used for Issue 10A3 — natural language seam routing. The caller injects
    the returned mask as a hard barrier in ``_build_seam_cost_map()``.

    Returns
    -------
    mask : uint8 (H, W) — 255 inside the detected region (exclude from seam),
           0 elsewhere.  None if no detection.
    """
    boxes = _detect_objects(frame, text_prompt, box_threshold=box_threshold, text_threshold=text_threshold)
    if not boxes:
        return None

    H, W = frame.shape[:2]
    mask = np.zeros((H, W), dtype=np.uint8)
    for box in boxes:
        x1, y1, x2, y2 = box.astype(int)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W - 1, x2), min(H - 1, y2)
        mask[y1:y2 + 1, x1:x2 + 1] = 255

    if dilate_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1))
        mask = cv2.dilate(mask, k)

    return mask


def reset_grounding_dino_model() -> None:
    """Unload the GroundingDINO model and free GPU memory (call between long jobs)."""
    global _gdino_model, _gdino_warned
    if _gdino_model is not None:
        try:
            # relocated: import torch
            del _gdino_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        _gdino_model = None
    _gdino_warned = False


__all__ = [
    "_detect_objects",
    "_detect_best_box",
    "_detect_exclusion_mask",
    "_load_grounding_dino",
    "reset_grounding_dino_model",
]

"""Subject extraction / segmentation for the source pane.

Primary path: SAM 2 (Segment Anything Model 2) — GPU-accelerated, prompted by
a hover/click point, returns a subject mask.

Fallbacks (in order): SAM 1 (`segment_anything`), OpenCV GrabCut around a
bounding box, and finally the raw bounding box itself. Everything is lazy so
the tab loads without the heavy weights present.

All functions return an ``alpha`` mask (uint8 HxW, 0/255) and the tight bbox.
The C++ core turns the mask into an RGBA cutout via :func:`alpha_cutout`.
"""

import logging
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_SAM = {"model": None, "predictor": None, "kind": None}


def _try_load_sam() -> Optional[str]:
    """Load SAM 2 (preferred) or SAM 1 once; return the kind or None."""
    if _SAM["predictor"] is not None:
        return _SAM["kind"]
    # SAM 2
    try:
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = build_sam2(
            "sam2_hiera_s.yaml", None, device=device
        )  # weights resolved from the SAM2 package config
        _SAM.update(model=model, predictor=SAM2ImagePredictor(model), kind="sam2")
        logger.info("SAM 2 loaded on %s", device)
        return "sam2"
    except Exception as e:
        logger.info("SAM 2 unavailable (%s); trying SAM 1", e)
    # SAM 1
    try:
        from segment_anything import SamPredictor, sam_model_registry

        sam = sam_model_registry["vit_b"]()
        _SAM.update(model=sam, predictor=SamPredictor(sam), kind="sam1")
        return "sam1"
    except Exception as e:
        logger.info("SAM 1 unavailable (%s); using GrabCut fallback", e)
    _SAM["kind"] = "grabcut"
    return "grabcut"


def _bbox_of_mask(mask: np.ndarray) -> Tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        h, w = mask.shape[:2]
        return 0, 0, w, h
    return int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)


def segment_at_point(
    image: np.ndarray, x: int, y: int
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """Return (alpha_mask, bbox) for the subject under point (x, y)."""
    kind = _try_load_sam()
    h, w = image.shape[:2]

    if kind in ("sam2", "sam1"):
        try:
            predictor = _SAM["predictor"]
            predictor.set_image(image)
            masks, scores, _ = predictor.predict(
                point_coords=np.array([[x, y]]),
                point_labels=np.array([1]),
                multimask_output=True,
            )
            best = masks[int(np.argmax(scores))]
            alpha = (best.astype(np.uint8) * 255)
            return alpha, _bbox_of_mask(alpha)
        except Exception as e:
            logger.warning("SAM inference failed (%s); GrabCut fallback", e)

    return _grabcut_around_point(image, x, y)


def _grabcut_around_point(
    image: np.ndarray, x: int, y: int, half: int = 96
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    import cv2

    h, w = image.shape[:2]
    x0, y0 = max(0, x - half), max(0, y - half)
    x1, y1 = min(w, x + half), min(h, y + half)
    rect = (x0, y0, max(1, x1 - x0), max(1, y1 - y0))
    mask = np.zeros((h, w), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(image, mask, rect, bgd, fgd, 3, cv2.GC_INIT_WITH_RECT)
        alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        if alpha.sum() == 0:
            raise ValueError("empty grabcut")
        return alpha, _bbox_of_mask(alpha)
    except Exception:
        alpha = np.zeros((h, w), np.uint8)
        alpha[y0:y1, x0:x1] = 255
        return alpha, (x0, y0, x1, y1)


def segment_bbox(
    image: np.ndarray, bbox: Tuple[int, int, int, int]
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """Manual fallback: treat the whole bounding box as the subject."""
    h, w = image.shape[:2]
    x0, y0, x1, y1 = bbox
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(w, int(x1)), min(h, int(y1))
    alpha = np.zeros((h, w), np.uint8)
    alpha[y0:y1, x0:x1] = 255
    return alpha, (x0, y0, x1, y1)


def alpha_cutout(image: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Compose an RGBA cutout (background fully transparent) cropped to bbox."""
    import cv2

    x0, y0, x1, y1 = _bbox_of_mask(alpha)
    crop = image[y0:y1, x0:x1]
    a = alpha[y0:y1, x0:x1]
    if crop.ndim == 2:
        crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
    rgba = np.dstack([crop[:, :, :3], a])
    return rgba


def cutout_to_png_bytes(rgba: np.ndarray) -> bytes:
    import cv2

    bgra = rgba[:, :, [2, 1, 0, 3]]
    ok, buf = cv2.imencode(".png", bgra)
    return buf.tobytes() if ok else b""

"""Seam renderer: OpenCV Stitcher's SCANS composer on ASP affines.

Graph-cut (COST_COLOR) seams at ~0.1 MP pick one owner frame per region,
then a multiband blend hides the seams. No exposure compensation, matching
SCANS. The 2026-11-03 contrast measured ASP poses through this composer at
+0.049 mean GT SSIM over ASP's median + FG composite.
"""

from __future__ import annotations

import logging
import math

import cv2
import numpy as np

logger = logging.getLogger(__name__)

SEAM_MEGAPIX = 0.1
BLEND_BANDS = 5


def _warp_roi(img: np.ndarray, M: np.ndarray, scale: float, interp: int, border: int):
    """Warp ``img`` by frame->canvas ``M`` at ``scale`` into its own ROI.

    Returns (warped, (x0, y0)) with the ROI corner in scaled canvas pixels.
    """
    A = np.asarray(M, np.float64).copy()
    A[:, 2] *= scale  # the source is resized by ``scale``, so only t scales
    src = img if scale == 1.0 else cv2.resize(
        img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR_EXACT
    )
    h, w = src.shape[:2]
    c = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float64)
    pts = c @ A[:, :2].T + A[:, 2]
    x0, y0 = np.floor(pts.min(axis=0)).astype(int)
    x1, y1 = np.ceil(pts.max(axis=0)).astype(int)
    A[:, 2] -= (x0, y0)
    out = cv2.warpAffine(
        src, A, (max(1, int(x1 - x0)), max(1, int(y1 - y0))), flags=interp, borderMode=border
    )
    return out, (int(x0), int(y0))


def _paste(dst: np.ndarray, src: np.ndarray, x0: int, y0: int, union: bool = False) -> None:
    """Copy ``src`` into ``dst`` at (x0, y0), clipped to ``dst``.

    ``union`` max-combines instead (masks: a ROI's zero border must not
    clear pixels another frame covers).
    """
    H, W = dst.shape[:2]
    h, w = src.shape[:2]
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(W, x0 + w), min(H, y0 + h)
    if dx1 <= dx0 or dy1 <= dy0:
        return
    patch = src[dy0 - y0 : dy1 - y0, dx0 - x0 : dx1 - x0]
    if union:
        np.maximum(dst[dy0:dy1, dx0:dx1], patch, out=dst[dy0:dy1, dx0:dx1])
    else:
        dst[dy0:dy1, dx0:dx1] = patch


def _render_seam(
    frames: list[np.ndarray],
    affines: list[np.ndarray],
    H: int,
    W: int,
    seam_megapix: float = SEAM_MEGAPIX,
    bands: int = BLEND_BANDS,
) -> tuple[np.ndarray, np.ndarray]:
    """Graph-cut seams + multiband blend into an ``H x W`` canvas.

    Returns ``(canvas uint8 BGR, valid_mask uint8 {0,255})``.
    """
    N = len(frames)
    canvas = np.zeros((H, W, 3), np.uint8)
    valid = np.zeros((H, W), np.uint8)
    if N == 0:
        return canvas, valid
    ones = [np.full(f.shape[:2], 255, np.uint8) for f in frames]

    if N == 1:
        w, c = _warp_roi(frames[0], affines[0], 1.0, cv2.INTER_LINEAR, cv2.BORDER_REFLECT)
        m, _ = _warp_roi(ones[0], affines[0], 1.0, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT)
        w[m == 0] = 0
        _paste(canvas, w, *c)
        _paste(valid, m, *c)
        return canvas, valid

    fh, fw = frames[0].shape[:2]
    ss = min(1.0, math.sqrt(seam_megapix * 1e6 / max(fh * fw, 1)))
    s_imgs, s_masks, s_corners = [], [], []
    for f, o, M in zip(frames, ones, affines, strict=True):
        wi, c = _warp_roi(f, M, ss, cv2.INTER_LINEAR, cv2.BORDER_REFLECT)
        wm, _ = _warp_roi(o, M, ss, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT)
        s_imgs.append(wi.astype(np.float32))
        s_masks.append(wm)
        s_corners.append(c)
    seams = cv2.detail_GraphCutSeamFinder("COST_COLOR").find(s_imgs, s_corners, s_masks)
    del s_imgs

    blender = cv2.detail_MultiBandBlender(0, int(bands))
    feeds, corners = [], []
    for k, (f, o, M) in enumerate(zip(frames, ones, affines, strict=True)):
        wi, c = _warp_roi(f, M, 1.0, cv2.INTER_LINEAR, cv2.BORDER_REFLECT)
        wm, _ = _warp_roi(o, M, 1.0, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT)
        seam = seams[k].get() if hasattr(seams[k], "get") else seams[k]
        seam = cv2.resize(
            cv2.dilate(seam, None), (wm.shape[1], wm.shape[0]),
            interpolation=cv2.INTER_LINEAR_EXACT,
        )
        _paste(valid, wm, *c, union=True)
        feeds.append((wi, cv2.bitwise_and(seam, wm)))
        corners.append(c)
    sizes = [(wi.shape[1], wi.shape[0]) for wi, _ in feeds]
    blender.prepare(cv2.detail.resultRoi(corners=corners, sizes=sizes))
    for (wi, wm), c in zip(feeds, corners, strict=True):
        blender.feed(wi.astype(np.int16), wm, c)
    del feeds
    result, rmask = blender.blend(None, None)
    result = np.clip(result, 0, 255).astype(np.uint8)
    result[rmask == 0] = 0
    ox = min(c[0] for c in corners)
    oy = min(c[1] for c in corners)
    _paste(canvas, result, ox, oy)
    canvas[valid == 0] = 0
    logger.info(
        "[Stitch]   Seam renderer: %d frames, seam scale %.3f, %d bands.", N, ss, bands
    )
    return canvas, valid


__all__ = ["_render_seam", "SEAM_MEGAPIX", "BLEND_BANDS"]

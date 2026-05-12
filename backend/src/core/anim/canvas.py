"""
Canvas geometry, frame loading & normalization, and SCANS-mode fallback.
"""

from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

from .constants import _CANVAS_MAX_DIM
from .stateless import _trim_dark_border


def _load_frames(paths: List[str]) -> List[np.ndarray]:
    """Read frames from disk, trim broadcast dark borders, drop unreadables."""
    frames = []
    for p in paths:
        img = cv2.imread(p)
        if img is None:
            print(f"[Stitch] Warning: could not read '{p}' — skipping.")
            continue
        img = _trim_dark_border(img)
        frames.append(img)
    return frames


def _normalise_widths(frames: List[np.ndarray]) -> List[np.ndarray]:
    """Resize every frame to match the width of the first frame (Lanczos)."""
    target_w = frames[0].shape[1]
    out = []
    for img in frames:
        h, w = img.shape[:2]
        if w != target_w:
            nh = int(round(h * target_w / w))
            img = cv2.resize(img, (target_w, nh), interpolation=cv2.INTER_LANCZOS4)
        out.append(img)
    return out


def _compute_canvas(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
) -> Tuple[int, int, np.ndarray]:
    """
    Compute canvas dimensions and the global translation offset T_global
    that maps all warped corners into positive coordinates.

    Returns (canvas_h, canvas_w, T_global) where T_global is a (2,) array
    of (tx, ty) offsets to add to every affine's translation column.
    """
    all_corners = []
    for i, img in enumerate(frames):
        h, w = img.shape[:2]
        M = affines[i]
        corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
        warped = (M[:2, :2] @ corners.T + M[:2, 2:3]).T
        all_corners.append(warped)

    all_corners = np.vstack(all_corners)
    min_xy = all_corners.min(axis=0)
    max_xy = all_corners.max(axis=0)

    T_global = -min_xy
    canvas_w = int(np.ceil(max_xy[0] - min_xy[0]))
    canvas_h = int(np.ceil(max_xy[1] - min_xy[1]))

    canvas_w = min(canvas_w, _CANVAS_MAX_DIM)
    canvas_h = min(canvas_h, _CANVAS_MAX_DIM)
    return canvas_h, canvas_w, T_global


def _crop_to_valid(canvas: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    """
    Crop to the tight bounding box of all valid (non-black) pixels.
    Uses a direct row/column projection — robust and O(H+W).
    """
    if valid_mask.max() == 0:
        return canvas

    row_has_content = np.any(valid_mask > 0, axis=1)
    col_has_content = np.any(valid_mask > 0, axis=0)

    row_idx = np.where(row_has_content)[0]
    col_idx = np.where(col_has_content)[0]

    if row_idx.size == 0 or col_idx.size == 0:
        return canvas

    r0, r1 = int(row_idx[0]), int(row_idx[-1]) + 1
    c0, c1 = int(col_idx[0]), int(col_idx[-1]) + 1
    print(f"[Stitch]   crop_to_valid: ({c0},{r0}) → ({c1},{r1})")
    return canvas[r0:r1, c0:c1]


def _scan_stitch_fallback(
    frames: List[np.ndarray],
    output_path: str,
) -> Image.Image:
    """
    Fall back to OpenCV SCANS mode when the main pipeline cannot find
    enough edges.  Mirrors _merge_images_scan_stitch.
    """
    print("[Stitch] FALLBACK: using OpenCV SCANS mode.")
    cv2.ocl.setUseOpenCL(False)
    try:
        stitcher = cv2.Stitcher_create(mode=1)
    except AttributeError:
        stitcher = cv2.createStitcher(True)
    stitcher.setRegistrationResol(0.8)
    status, pano = stitcher.stitch(frames)
    if status != cv2.Stitcher_OK:
        raise RuntimeError(f"SCANS fallback failed (status={status}).")
    rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
    out = Image.fromarray(rgb)
    out.save(output_path)
    return out


def find_optimal_sequence(
    ref_path: str,
    candidates: List[str],
    min_inliers: int = 30,
    max_overlap: float = 0.85,
) -> List[str]:
    """
    Finds the longest coherent sequence while dropping redundant frames.
    Prioritizes frames that extend the panorama furthest while maintaining
    robust overlap.
    """
    # 1. Feature Extraction (SIFT)
    sift = cv2.SIFT_create(nfeatures=1200)

    def get_feats(p):
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None, None, None
        h, w = img.shape
        if w > 1024:
            img = cv2.resize(img, (1024, int(h * 1024 / w)))
        kp, des = sift.detectAndCompute(img, None)
        return kp, des, img.shape

    feats = {}
    for p in [ref_path] + list(candidates):
        if p not in feats:
            kp, des, shape = get_feats(p)
            if kp is not None:
                feats[p] = (kp, des, shape[0], shape[1])

    if ref_path not in feats:
        return []

    sequence = [ref_path]
    used = {ref_path}
    bf = cv2.BFMatcher()

    def find_optimal_extension(query_path, pool, direction="forward"):
        q_kp, q_des, q_h, q_w = feats[query_path]
        best_p = None
        max_dist = -1.0

        for p in pool:
            if p in used or p not in feats:
                continue
            t_kp, t_des, t_h, t_w = feats[p]

            matches = bf.knnMatch(q_des, t_des, k=2)
            good = [m for m, n in matches if m.distance < 0.75 * n.distance]
            if len(good) < min_inliers:
                continue

            src_pts = np.float32([q_kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([t_kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            if M is None or mask is None:
                continue

            inliers = int(mask.sum())
            if inliers < min_inliers:
                continue

            dist = np.sqrt(M[0, 2] ** 2 + M[1, 2] ** 2)
            if dist < 0.15 * max(q_h, q_w):
                continue

            if dist > max_dist:
                max_dist = dist
                best_p = p

        return best_p

    # Expand Forward
    while True:
        nxt = find_optimal_extension(sequence[-1], candidates, "forward")
        if nxt:
            sequence.append(nxt)
            used.add(nxt)
        else:
            break

    # Expand Backward
    while True:
        prev = find_optimal_extension(sequence[0], candidates, "backward")
        if prev:
            sequence.insert(0, prev)
            used.add(prev)
        else:
            break

    return sequence


__all__ = [
    "_load_frames",
    "_normalise_widths",
    "_compute_canvas",
    "_crop_to_valid",
    "_scan_stitch_fallback",
    "find_optimal_sequence",
]

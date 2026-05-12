"""
Foreground composite using component-aware deghosting + alpha blending.
"""

from __future__ import annotations

from typing import List, Optional

import cv2
import numpy as np


def _composite_foreground(
    warped_corr: List[np.ndarray],
    warped_fgs: List[np.ndarray],
    canvas: np.ndarray,
    H: int,
    W: int,
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
) -> np.ndarray:
    """
    Advanced Foreground Composite using Optical Flow Deghosting.
    """
    N = len(frames)

    # 1. Identify Foreground Pixels and assign Best Frame per Component
    global_fg_mask = np.zeros((H, W), np.uint8)
    warped_masks: List[Optional[np.ndarray]] = []

    print("[Stitch]   Compositing foreground with component-aware deghosting...")

    for i in range(N):
        if bg_masks[i] is None:
            warped_masks.append(None)
            continue
        fg = (bg_masks[i] < 127).astype(np.uint8) * 255
        w_fg = cv2.warpAffine(
            fg,
            affines[i],
            (W, H),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        warped_masks.append(w_fg)
        global_fg_mask[w_fg > 127] = 255

    # Use connected components to identify individual characters/parts
    num_labels, labels = cv2.connectedComponents(global_fg_mask)
    frame_best_fg = np.full((H, W), -1, np.int16)

    for label in range(1, num_labels):
        comp_mask = labels == label

        best_i = -1
        max_score = -1.0

        for i in range(N):
            w_fg = warped_masks[i]
            if w_fg is None:
                continue

            overlap = np.logical_and(comp_mask, w_fg > 127)
            area = overlap.sum()
            if area == 0:
                continue

            orig_fg = (bg_masks[i] < 127).astype(np.uint8) * 255
            ys, xs = np.where(orig_fg > 127)
            if len(ys) == 0:
                continue

            fh, fw = orig_fg.shape
            min_dist_edge = min(xs.min(), fw - xs.max(), ys.min(), fh - ys.max())

            score = float(area) * (1.0 + min_dist_edge / max(fw, fh))

            if score > max_score:
                max_score = score
                best_i = i

        if best_i != -1:
            frame_best_fg[comp_mask] = best_i

    # 2. Warp character pixels on-the-fly
    final_fg = canvas.copy()
    for i in range(N):
        px = frame_best_fg == i
        if not px.any():
            continue

        w_corr = cv2.warpAffine(
            frames[i],
            affines[i],
            (W, H),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )

        orig_valid = (
            np.ones((frames[i].shape[0], frames[i].shape[1]), np.uint8) * 255
        )
        warped_valid = cv2.warpAffine(
            orig_valid,
            affines[i],
            (W, H),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

        update_mask = px & (warped_valid > 127)
        final_fg[update_mask] = w_corr[update_mask]

    # 3. Poisson Blending (Seamless Character Integration)
    if global_fg_mask.any():
        try:
            num_labels, labels = cv2.connectedComponents(
                global_fg_mask.astype(np.uint8)
            )

            kernel_erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

            for label in range(1, num_labels):
                comp_mask = (labels == label).astype(np.uint8) * 255

                comp_mask = cv2.erode(comp_mask, kernel_erode, iterations=1)
                if not comp_mask.any():
                    continue

                comp_mask = cv2.dilate(comp_mask, kernel_dilate, iterations=4)

                ys, xs = np.where(comp_mask > 0)
                if len(ys) == 0:
                    continue
                y0, y1 = ys.min(), ys.max() + 1
                x0, x1 = xs.min(), xs.max() + 1

                roi_fg = final_fg[y0:y1, x0:x1]
                roi_mask = comp_mask[y0:y1, x0:x1]

                dist = cv2.distanceTransform(roi_mask, cv2.DIST_L2, 3)
                feather = 8.0
                weights = np.clip(dist / feather, 0, 1).astype(np.float32)

                bg_roi = canvas[y0:y1, x0:x1].astype(np.float32)
                fg_roi = roi_fg.astype(np.float32)
                w3 = cv2.merge([weights, weights, weights])
                blended = (1.0 - w3) * bg_roi + w3 * fg_roi
                canvas[y0:y1, x0:x1] = blended.astype(np.uint8)

        except Exception as e:
            print(
                f"[Stitch]   Alpha blending failed ({e}); using direct composite."
            )
            canvas[global_fg_mask > 0] = final_fg[global_fg_mask > 0]

    return canvas


__all__ = ["_composite_foreground"]

"""
BiRefNet foreground / background masking for anime frames.
"""

from __future__ import annotations

import gc
from typing import List, Optional

import cv2
import numpy as np
import torch

from .constants import _FOREGROUND_DILATION, _FOREGROUND_EROSION


def _compute_fg_masks(
    frames: List[np.ndarray],
    birefnet_wrapper,
    use_birefnet: bool = True,
) -> List[Optional[np.ndarray]]:
    """Returns list of background masks (255 = safe background, 0 = character)."""
    if not use_birefnet or birefnet_wrapper is None:
        return [None] * len(frames)

    # Detect which API version is loaded
    has_new_api = hasattr(birefnet_wrapper, "get_background_mask")

    masks: List[Optional[np.ndarray]] = []
    for i, img in enumerate(frames):
        try:
            if has_new_api:
                # New API: returns 255=background, 0=foreground, with dilation/erosion
                bg = birefnet_wrapper.get_background_mask(
                    img,
                    dilate_px=_FOREGROUND_DILATION,
                    erode_px=_FOREGROUND_EROSION,
                )
            else:
                # Legacy API: get_mask returns 255=foreground; invert + dilate manually
                fg = birefnet_wrapper.get_mask(img)
                bg = cv2.bitwise_not(fg)
                if _FOREGROUND_DILATION > 0:
                    k = cv2.getStructuringElement(
                        cv2.MORPH_ELLIPSE,
                        (
                            2 * _FOREGROUND_DILATION + 1,
                            2 * _FOREGROUND_DILATION + 1,
                        ),
                    )
                    fg_dilated = cv2.dilate(fg, k)
                    bg = cv2.bitwise_not(fg_dilated)
            masks.append(bg)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
        except Exception as e:
            print(f"[Stitch]   BiRefNet failed on frame {i}: {e}")
            masks.append(None)
    return masks


__all__ = ["_compute_fg_masks"]

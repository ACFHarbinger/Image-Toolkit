"""
BiRefNet foreground / background masking for anime frames.
"""

from __future__ import annotations

import gc
from typing import List, Optional

import cv2
import numpy as np
import torch

from backend.src.constants import FOREGROUND_DILATION, FOREGROUND_EROSION


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
                    dilate_px=FOREGROUND_DILATION,
                    erode_px=FOREGROUND_EROSION,
                )
            else:
                # Legacy API: get_mask returns 255=foreground; invert + dilate manually
                fg = birefnet_wrapper.get_mask(img)
                bg = cv2.bitwise_not(fg)
                if FOREGROUND_DILATION > 0:
                    k = cv2.getStructuringElement(
                        cv2.MORPH_ELLIPSE,
                        (
                            2 * FOREGROUND_DILATION + 1,
                            2 * FOREGROUND_DILATION + 1,
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


def _compute_fg_masks_sam2(
    frames: List[np.ndarray],
    birefnet_wrapper,
    use_birefnet: bool = True,
) -> List[Optional[np.ndarray]]:
    """
    SAM-2 video masking (§5.2) — temporally consistent foreground masks.

    Strategy:
      1. Run BiRefNet on frame 0 to get an initial fg bounding box prompt.
      2. Use SAM2VideoPredictor to propagate the bbox across all frames in one
         forward pass — hidden states keep mask boundaries stable across holds.
      3. Falls back to ``_compute_fg_masks`` (per-frame BiRefNet) on any error.

    Requires ``pip install sam2`` and checkpoint at ``$SAM2_CKPT``
    (default: ``~/.sam2/sam2_hiera_base_plus.pt``).

    Return convention: 255 = safe background, 0 = character foreground.
    """
    if not use_birefnet or birefnet_wrapper is None:
        return [None] * len(frames)

    has_new_api = hasattr(birefnet_wrapper, "get_background_mask")
    try:
        if has_new_api:
            _bg0 = birefnet_wrapper.get_background_mask(
                frames[0], dilate_px=FOREGROUND_DILATION, erode_px=FOREGROUND_EROSION
            )
        else:
            _bg0 = cv2.bitwise_not(birefnet_wrapper.get_mask(frames[0]))
        _fg_bin = (_bg0 < 128).astype(np.uint8) * 255
    except Exception:
        return _compute_fg_masks(frames, birefnet_wrapper, use_birefnet)

    _ys, _xs = np.where(_fg_bin > 127)
    if len(_ys) == 0:
        return _compute_fg_masks(frames, birefnet_wrapper, use_birefnet)

    _bbox = np.array(
        [[int(_xs.min()), int(_ys.min()), int(_xs.max()), int(_ys.max())]],
        dtype=np.float32,
    )

    try:
        import os
        import tempfile
        from sam2.build_sam import build_sam2_video_predictor  # type: ignore

        _ckpt = os.path.expanduser(
            os.environ.get("SAM2_CKPT", "~/.sam2/sam2_hiera_base_plus.pt")
        )
        _cfg = os.environ.get("SAM2_CFG", "sam2_hiera_b+.yaml")
        _device = "cuda" if torch.cuda.is_available() else "cpu"

        predictor = build_sam2_video_predictor(_cfg, _ckpt, device=_device)
        _H, _W = frames[0].shape[:2]

        with tempfile.TemporaryDirectory() as _tmp:
            for _i, _f in enumerate(frames):
                cv2.imwrite(os.path.join(_tmp, f"{_i:06d}.jpg"), _f)

            _state = predictor.init_state(video_path=_tmp)
            predictor.add_new_points_or_box(
                inference_state=_state, frame_idx=0, obj_id=1, box=_bbox
            )

            masks_out: List[Optional[np.ndarray]] = [None] * len(frames)
            for _idx, _obj_ids, _logits in predictor.propagate_in_video(_state):
                if 1 in _obj_ids:
                    _li = list(_obj_ids).index(1)
                    _prob = torch.sigmoid(_logits[_li, 0]).cpu().numpy()
                    if _prob.shape != (_H, _W):
                        _prob = cv2.resize(_prob, (_W, _H), cv2.INTER_LINEAR)
                    _fg_i = (_prob > 0.5).astype(np.uint8) * 255
                    if FOREGROUND_DILATION > 0:
                        _k = cv2.getStructuringElement(
                            cv2.MORPH_ELLIPSE,
                            (2 * FOREGROUND_DILATION + 1, 2 * FOREGROUND_DILATION + 1),
                        )
                        _fg_i = cv2.dilate(_fg_i, _k)
                    masks_out[_idx] = cv2.bitwise_not(_fg_i)

            predictor.reset_state(_state)
            del predictor
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

        # Fill any missed frames with per-frame BiRefNet
        for _i, _m in enumerate(masks_out):
            if _m is None:
                try:
                    if has_new_api:
                        masks_out[_i] = birefnet_wrapper.get_background_mask(frames[_i])
                    else:
                        masks_out[_i] = cv2.bitwise_not(birefnet_wrapper.get_mask(frames[_i]))
                except Exception:
                    pass

        return masks_out

    except Exception as _e:
        print(f"[Stitch] SAM-2 unavailable ({_e}); falling back to per-frame BiRefNet.")
        return _compute_fg_masks(frames, birefnet_wrapper, use_birefnet)


__all__ = ["_compute_fg_masks", "_compute_fg_masks_sam2"]

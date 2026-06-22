"""§3.1A AnimeInterp SGM + §3.2A ConvGRU — anime-aware optical flow engine.

Trapped-ball segmentation extracts flat-color regions; VGG-19 region features
match segments across frames; Matching Degree Matrix builds a soft warp field;
ConvGRU refines it iteratively.  Falls back to DIS when torch unavailable.

Enable: ASP_FLOW_ENGINE=animeinterp
Pretrained weights: ASP_ANIMEINTERP_WEIGHTS (path to .pth, or empty to use
                    random-init ConvGRU with VGG-19 ImageNet weights).
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

from backend.src.constants.animation import (
    ANIMEINTERP_GRU_ITERS,
    ANIMEINTERP_SPATIAL_SIGMA,
    ANIMEINTERP_TRAPPED_BALL_MAX_R,
    ANIMEINTERP_TRAPPED_BALL_MIN_R,
)

logger = logging.getLogger(__name__)

__all__ = [
    "AnimeInterpFlow",
    "trapped_ball_segment",
    "compute_region_features",
    "build_mdm",
    "ConvGRUCell",
    "compute_animeinterp_flow",
]

# ---------------------------------------------------------------------------
# Optional torch — imported lazily inside functions
# ---------------------------------------------------------------------------
try:
    import torch
    import torch.nn as nn

    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore
    nn = None  # type: ignore
    _TORCH_OK = False

_VGG19_SINGLETON = None
_VGG19_DEVICE: Optional[str] = None
_GRU_SINGLETON = None
_GRU_DEVICE: Optional[str] = None


# ---------------------------------------------------------------------------
# Trapped-ball segmentation (§3.1A, pure OpenCV/NumPy)
# ---------------------------------------------------------------------------


def trapped_ball_segment(
    image_bgr: np.ndarray,
    min_radius: int = ANIMEINTERP_TRAPPED_BALL_MIN_R,
    max_radius: int = ANIMEINTERP_TRAPPED_BALL_MAX_R,
    n_iter: int = 3,
) -> np.ndarray:
    """
    Segment flat-color regions via iterative seeded flood-fill (trapped-ball).

    Returns (H, W) int32 label map where each flat-color region has a unique
    non-negative integer label.  Background pixels that remain unlabeled after
    all iterations are assigned to the nearest labeled neighbor.
    """
    H, W = image_bgr.shape[:2]
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    labels = np.full((H, W), -1, dtype=np.int32)
    next_label = 0

    rng = np.random.default_rng(seed=42)

    for iteration in range(n_iter):
        radius = min_radius + iteration * max(
            1, (max_radius - min_radius) // max(n_iter - 1, 1)
        )
        # unlabeled_mask = (labels == -1).astype(np.uint8) * 255

        unlabeled_ys, unlabeled_xs = np.where(labels == -1)
        if len(unlabeled_ys) == 0:
            break

        n_seeds = max(1, len(unlabeled_ys) // max(radius * radius, 1))
        indices = rng.choice(
            len(unlabeled_ys), size=min(n_seeds, len(unlabeled_ys)), replace=False
        )
        seed_ys = unlabeled_ys[indices]
        seed_xs = unlabeled_xs[indices]

        tol = radius * 4
        flood_flags = cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)

        for sy, sx in zip(seed_ys, seed_xs):
            if labels[sy, sx] != -1:
                continue
            flood_mask = np.zeros((H + 2, W + 2), dtype=np.uint8)
            lo = (tol, tol, tol)
            hi = (tol, tol, tol)
            area, _, _, _ = cv2.floodFill(
                lab.copy(),
                flood_mask,
                (int(sx), int(sy)),
                0,
                loDiff=lo,
                upDiff=hi,
                flags=flood_flags,
            )
            if area < 1:
                continue
            filled = flood_mask[1:-1, 1:-1].astype(bool)
            new_pixels = filled & (labels == -1)
            if new_pixels.any():
                labels[new_pixels] = next_label
                next_label += 1

    # Assign remaining unlabeled pixels to nearest labeled neighbor
    still_unlabeled = labels == -1
    if still_unlabeled.any() and (~still_unlabeled).any():
        # dist_map = cv2.distanceTransform(
        #     still_unlabeled.astype(np.uint8) * 255, cv2.DIST_L2, 3
        # )
        labeled_img = np.where(still_unlabeled, 0, labels + 1).astype(np.int32)
        kernel = np.ones((2 * max_radius + 1, 2 * max_radius + 1), np.uint8)
        for _ in range(max(1, H // 32)):
            dilated = cv2.dilate(labeled_img.astype(np.float32), kernel).astype(
                np.int32
            )
            fill = still_unlabeled & (dilated > 0)
            labels[fill] = dilated[fill] - 1
            still_unlabeled = labels == -1
            if not still_unlabeled.any():
                break
        # Any remaining → label 0
        labels[labels == -1] = 0

    return labels.astype(np.int32)


# ---------------------------------------------------------------------------
# Region features (VGG-19 or LAB color fallback)
# ---------------------------------------------------------------------------


def _get_vgg19() -> Tuple[Optional[object], Optional[str]]:
    global _VGG19_SINGLETON, _VGG19_DEVICE
    if _VGG19_SINGLETON is not None or _VGG19_DEVICE == "FAILED":
        return _VGG19_SINGLETON, _VGG19_DEVICE
    if not _TORCH_OK:
        _VGG19_DEVICE = "FAILED"
        return None, None
    try:
        import torchvision.models as tvm

        device = "cuda" if torch.cuda.is_available() else "cpu"
        vgg = tvm.vgg19(weights=tvm.VGG19_Weights.IMAGENET1K_V1).features
        partial = nn.Sequential(*list(vgg.children())[:19]).to(device).eval()
        _VGG19_SINGLETON = partial
        _VGG19_DEVICE = device
        return _VGG19_SINGLETON, _VGG19_DEVICE
    except Exception as e:
        logger.debug("AnimeInterp VGG-19 unavailable (%s); using LAB fallback", e)
        _VGG19_DEVICE = "FAILED"
        return None, None


def compute_region_features(
    image_bgr: np.ndarray,
    label_map: np.ndarray,
    use_vgg: bool = True,
) -> Dict[int, np.ndarray]:
    """
    Map each region label → feature vector.

    When use_vgg=True and torch is available, extracts 256-d VGG-19 conv3_4
    mean-pooled features.  Falls back to 3-d mean LAB color vector.
    """
    H, W = image_bgr.shape[:2]
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    unique_labels = np.unique(label_map)

    model, device = (None, None)
    feat_map = None
    if use_vgg:
        model, device = _get_vgg19()
        if model is not None:
            rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            rgb = (rgb - mean) / std
            t = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(device)
            with torch.no_grad():
                feat_t = model(t)[0]  # (C, H', W')
            feat_map = feat_t.cpu().numpy()

    feats: Dict[int, np.ndarray] = {}
    for lbl in unique_labels:
        mask = label_map == lbl
        if not mask.any():
            continue

        if feat_map is not None:
            _C, _fH, _fW = feat_map.shape
            ys, xs = np.where(mask)
            fy = np.clip((ys * _fH / H).astype(int), 0, _fH - 1)
            fx = np.clip((xs * _fW / W).astype(int), 0, _fW - 1)
            vec = feat_map[:, fy, fx].mean(axis=1).astype(np.float32)
        else:
            vec = lab[mask].mean(axis=0).astype(np.float32)

        norm = float(np.linalg.norm(vec))
        if norm > 1e-8:
            vec = vec / norm
        feats[int(lbl)] = vec

    return feats


# ---------------------------------------------------------------------------
# Matching Degree Matrix
# ---------------------------------------------------------------------------


def build_mdm(
    feats_a: Dict[int, np.ndarray],
    feats_b: Dict[int, np.ndarray],
    centroids_a: Dict[int, Tuple[float, float]],
    centroids_b: Dict[int, Tuple[float, float]],
    spatial_sigma: float = ANIMEINTERP_SPATIAL_SIGMA,
) -> np.ndarray:
    """
    Build (Na, Nb) Matching Degree Matrix with row-wise soft assignment.

    MDM[i, j] = cosine_sim(feats_a[i], feats_b[j]) * exp(-dist²/(2σ²))
    Rows are L1-normalized to sum to 1.
    """
    keys_a = list(feats_a.keys())
    keys_b = list(feats_b.keys())
    Na, Nb = len(keys_a), len(keys_b)

    if Na == 0 or Nb == 0:
        return np.zeros((max(Na, 1), max(Nb, 1)), dtype=np.float32)

    fa_mat = np.stack([feats_a[k] for k in keys_a], axis=0).astype(
        np.float32
    )  # (Na, C)
    fb_mat = np.stack([feats_b[k] for k in keys_b], axis=0).astype(
        np.float32
    )  # (Nb, C)

    # Cosine similarity — features are L2-normalised, so this is a dot product
    cos_sim = (fa_mat @ fb_mat.T).clip(-1.0, 1.0)  # (Na, Nb)

    # Spatial weight
    ca = np.array([centroids_a[k] for k in keys_a], dtype=np.float32)  # (Na, 2)
    cb = np.array([centroids_b[k] for k in keys_b], dtype=np.float32)  # (Nb, 2)
    diff = ca[:, None, :] - cb[None, :, :]  # (Na, Nb, 2)
    dist2 = (diff**2).sum(axis=-1)  # (Na, Nb)
    spatial = np.exp(-dist2 / (2.0 * spatial_sigma**2 + 1e-8))  # (Na, Nb)

    mdm = (cos_sim * spatial).clip(0.0, None).astype(np.float32)

    # Soft row-normalize
    row_sums = mdm.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums < 1e-8, 1.0, row_sums)
    mdm = mdm / row_sums

    return mdm


# ---------------------------------------------------------------------------
# ConvGRU cell (§3.2A) — defined only when torch is available
# ---------------------------------------------------------------------------

if _TORCH_OK:

    class ConvGRUCell(nn.Module):
        """Single ConvGRU step for iterative flow refinement (§3.2A)."""

        def __init__(
            self, input_dim: int = 2, hidden_dim: int = 32, kernel_size: int = 3
        ):
            super().__init__()
            pad = kernel_size // 2
            self.reset_gate = nn.Conv2d(
                input_dim + hidden_dim, hidden_dim, kernel_size, padding=pad
            )
            self.update_gate = nn.Conv2d(
                input_dim + hidden_dim, hidden_dim, kernel_size, padding=pad
            )
            self.out_gate = nn.Conv2d(
                input_dim + hidden_dim, hidden_dim, kernel_size, padding=pad
            )
            self.flow_head = nn.Conv2d(hidden_dim, 2, 1)

        def forward(
            self,
            flow_in: "torch.Tensor",
            h: "torch.Tensor",
        ) -> Tuple["torch.Tensor", "torch.Tensor"]:
            combined = torch.cat([flow_in, h], dim=1)
            r = torch.sigmoid(self.reset_gate(combined))
            z = torch.sigmoid(self.update_gate(combined))
            o = torch.tanh(self.out_gate(torch.cat([flow_in, r * h], dim=1)))
            h_new = (1 - z) * h + z * o
            delta = self.flow_head(h_new)
            return flow_in + delta, h_new

else:

    class ConvGRUCell:  # type: ignore[no-redef]
        """Stub when torch is unavailable."""

        def __init__(self, *args, **kwargs):
            raise ImportError("torch is required for ConvGRUCell")


def _get_gru(
    weights_path: Optional[str] = None,
) -> Tuple[Optional[object], Optional[str]]:
    global _GRU_SINGLETON, _GRU_DEVICE
    if _GRU_SINGLETON is not None or _GRU_DEVICE == "FAILED":
        return _GRU_SINGLETON, _GRU_DEVICE
    if not _TORCH_OK:
        _GRU_DEVICE = "FAILED"
        return None, None
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        cell = ConvGRUCell(input_dim=2, hidden_dim=32, kernel_size=3).to(device).eval()
        if weights_path and os.path.isfile(weights_path):
            state = torch.load(weights_path, map_location=device)
            cell.load_state_dict(state)
            logger.info("AnimeInterp ConvGRU weights loaded from %s", weights_path)
        _GRU_SINGLETON = cell
        _GRU_DEVICE = device
        return _GRU_SINGLETON, _GRU_DEVICE
    except Exception as e:
        logger.debug("ConvGRU init failed (%s); skipping GRU refinement", e)
        _GRU_DEVICE = "FAILED"
        return None, None


# ---------------------------------------------------------------------------
# Main flow computation
# ---------------------------------------------------------------------------


def compute_animeinterp_flow(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    n_gru_iters: int = ANIMEINTERP_GRU_ITERS,
    weights_path: Optional[str] = None,
) -> np.ndarray:
    """
    Compute dense flow frame_a → frame_b using trapped-ball SGM + ConvGRU.

    Returns (H, W, 2) float32 flow in pixel units (dx, dy).
    When no regions are matched, returns zero flow.
    """
    H, W = frame_a.shape[:2]
    zero_flow = np.zeros((H, W, 2), dtype=np.float32)

    label_map_a = trapped_ball_segment(frame_a)
    label_map_b = trapped_ball_segment(frame_b)

    feats_a = compute_region_features(frame_a, label_map_a, use_vgg=True)
    feats_b = compute_region_features(frame_b, label_map_b, use_vgg=True)

    if not feats_a or not feats_b:
        return zero_flow

    # Compute centroids for each label
    def _centroids(label_map: np.ndarray, label_ids) -> Dict[int, Tuple[float, float]]:
        cents = {}
        for lbl in label_ids:
            ys, xs = np.where(label_map == lbl)
            if len(ys) == 0:
                continue
            cents[int(lbl)] = (float(ys.mean()), float(xs.mean()))
        return cents

    cents_a = _centroids(label_map_a, list(feats_a.keys()))
    cents_b = _centroids(label_map_b, list(feats_b.keys()))

    if not cents_a or not cents_b:
        return zero_flow

    mdm = build_mdm(feats_a, feats_b, cents_a, cents_b)

    keys_a = list(feats_a.keys())
    keys_b = list(feats_b.keys())
    label_to_row_a = {lbl: i for i, lbl in enumerate(keys_a)}

    cb_arr = np.array(
        [cents_b[k] for k in keys_b], dtype=np.float32
    )  # (Nb, 2) [cy, cx]
    ca_arr = np.array([cents_a[k] for k in keys_a], dtype=np.float32)  # (Na, 2)

    # Per-pixel: flow[y,x] = (MDM[row_a, :] @ cb_arr) - ca_arr[row_a]
    # Build label→row lookup via index array
    max_lbl_a = int(label_map_a.max()) + 1
    row_lookup = np.full(max_lbl_a, -1, dtype=np.int32)
    for lbl, row in label_to_row_a.items():
        if lbl < max_lbl_a:
            row_lookup[lbl] = row

    flat_labels = label_map_a.ravel()
    valid = (flat_labels < max_lbl_a) & (
        row_lookup[flat_labels.clip(0, max_lbl_a - 1)] >= 0
    )
    flat_rows = np.where(valid, row_lookup[flat_labels.clip(0, max_lbl_a - 1)], 0)

    # (Npx, Nb) @ (Nb, 2) → (Npx, 2)  weighted target centroid
    mdm_rows = mdm[flat_rows]  # (Npx, Nb)
    weighted_cb = mdm_rows @ cb_arr  # (Npx, 2) [cy, cx]
    src_ca = ca_arr[flat_rows]  # (Npx, 2) [cy, cx]
    pixel_flow_yx = weighted_cb - src_ca  # (Npx, 2) [dy, dx]

    flow_flat = np.zeros((H * W, 2), dtype=np.float32)
    flow_flat[valid] = pixel_flow_yx[valid][:, [1, 0]]  # reorder to [dx, dy]

    flow = flow_flat.reshape(H, W, 2)

    # §3.2A — ConvGRU iterative refinement
    if n_gru_iters > 0:
        gru, gru_device = _get_gru(weights_path)
        if gru is not None:
            try:
                t_flow = (
                    torch.from_numpy(flow).permute(2, 0, 1).unsqueeze(0).to(gru_device)
                )
                h = torch.zeros(1, 32, H, W, device=gru_device)
                with torch.no_grad():
                    for _ in range(n_gru_iters):
                        t_flow, h = gru(t_flow, h)
                flow = t_flow[0].permute(1, 2, 0).cpu().numpy().astype(np.float32)
            except Exception as e:
                logger.debug("ConvGRU refinement failed (%s); using coarse flow", e)

    return flow


# ---------------------------------------------------------------------------
# AnimeInterpFlow wrapper class (convenience)
# ---------------------------------------------------------------------------


class AnimeInterpFlow:
    """Stateful wrapper that holds GRU weights path and default parameters."""

    def __init__(
        self,
        weights_path: Optional[str] = None,
        n_gru_iters: int = ANIMEINTERP_GRU_ITERS,
    ):
        self.weights_path = weights_path
        self.n_gru_iters = n_gru_iters

    def __call__(self, frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
        return compute_animeinterp_flow(
            frame_a,
            frame_b,
            n_gru_iters=self.n_gru_iters,
            weights_path=self.weights_path,
        )

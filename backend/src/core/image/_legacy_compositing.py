"""Legacy/experimental compositing helpers, not called by any current
``ImageMerger`` public method (``merge_images``/``perfect_stitch`` delegate
panorama stitching entirely to OpenCV/Hugin/Overmix/AnimeStitchPipeline).

Preserved as-is from the pre-split module rather than removed -- deleting
unused code is a separate, deliberate cleanup decision outside the scope of
a mechanical file split.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.optimize import least_squares

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]


class _LegacyCompositingMixin:
    """Unused advanced compositing/warping helpers, kept for ``ImageMerger``."""

    @staticmethod
    def _detect_structural_lines(img: np.ndarray) -> List[np.ndarray]:
        """
        Uses Line Segment Detector (LSD) to find sub-pixel accurate structural lines.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
        lines, _, _, _ = lsd.detect(gray)
        return lines if lines is not None else []

    @staticmethod
    def _compute_apap_mesh(
        shape: Tuple[int, int],
        pts_src: np.ndarray,
        pts_dst: np.ndarray,
        grid_size: Tuple[int, int] = (20, 20),
        sigma: float = 0.1,  # Relative to image diagonal
        gamma: float = 0.05,
        weights_bias: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        As-Projective-As-Possible (APAP) warping using Moving DLT.
        Computes a local homography for each mesh vertex.
        """
        h, w = shape[:2]
        grid_h, grid_w = grid_size

        if weights_bias is None:
            weights_bias = np.ones(len(pts_src))

        # 1. Create mesh grid
        xs = np.linspace(0, w - 1, grid_w + 1)
        ys = np.linspace(0, h - 1, grid_h + 1)
        grid_x, grid_y = np.meshgrid(xs, ys)
        vertices = np.stack([grid_x, grid_y], axis=-1).reshape(-1, 2)

        # 2. Pre-compute A matrix for DLT (Ah = 0)
        # For each point pair (x,y) -> (u,v), A_i is 2x9
        num_pts = len(pts_src)
        A = np.zeros((2 * num_pts, 9))
        for i in range(num_pts):
            x, y = pts_src[i]
            u, v = pts_dst[i]
            A[2 * i] = [x, y, 1, 0, 0, 0, -u * x, -u * y, -u]
            A[2 * i + 1] = [0, 0, 0, x, y, 1, -v * x, -v * y, -v]

        local_homographies = []

        # 3. Solve Moving DLT for each vertex
        # We use a global sigma for the Gaussian weighting
        # sigma is relative to the image size (normalized)
        norm_factor = np.sqrt(w**2 + h**2)

        for v in vertices:
            # Gaussian weights based on distance to src points
            dists = np.linalg.norm(pts_src - v, axis=1) / norm_factor
            # We use the squared distance for Gaussian weighting
            weights = np.exp(-(dists**2) / (2 * sigma**2))

            if weights_bias is not None:
                weights = weights * weights_bias

            # Numerical stability guard: prevent weights from becoming too small
            # which causes SVD to solve for noise.
            weights = np.maximum(weights, gamma)

            # Weighted A matrix
            W_A = A.copy()
            for i in range(num_pts):
                W_A[2 * i] *= weights[i]
                W_A[2 * i + 1] *= weights[i]

            # SVD to find h (last column of V)
            _, _, Vh = np.linalg.svd(W_A)
            h_local = Vh[-1].reshape(3, 3)
            local_homographies.append(h_local)

        return np.array(local_homographies).reshape(grid_h + 1, grid_w + 1, 3, 3)

    @staticmethod
    def _apply_radiometric_normalization(
        img: np.ndarray, target_stats: Dict[str, np.ndarray]
    ) -> np.ndarray:
        """
        Reverses broadcast dimming and equalizes exposure via gain compensation.
        """
        img_f = img.astype(np.float32)
        # Gain compensation per channel
        current_mean = np.mean(img_f, axis=(0, 1))
        gain = np.clip(target_stats["mean"] / (current_mean + 1e-6), 0.7, 1.4)

        # Apply gain
        img_f *= gain

        # Optional: Contrast matching if needed
        current_std = np.std(img_f, axis=(0, 1))
        contrast_adj = np.clip(target_stats["std"] / (current_std + 1e-6), 0.8, 1.2)
        img_f = (img_f - target_stats["mean"]) * contrast_adj + target_stats["mean"]

        return np.clip(img_f, 0, 255).astype(np.uint8)

    @staticmethod
    def _neural_synthesis_blending(
        blended_region: np.ndarray,
        device: Optional[str] = None,
    ) -> np.ndarray:
        """
        Uses AnimeGAN2 to refine the transition zone, ensuring structural and stylistic integrity.
        """
        try:
            # Use cached GAN instance -- deferred import: this mixin and
            # _ModelCacheMixin are both composed into the final ImageMerger
            # class, but importing that class at module load time here would
            # create a circular import between this module and manager.py.
            from .manager import ImageMerger

            gan = ImageMerger._get_gan()

            tmp_dir = tempfile.gettempdir()
            tmp_in = os.path.join(tmp_dir, f"stitch_in_{uuid.uuid4()}.png")
            tmp_out = os.path.join(tmp_dir, f"stitch_out_{uuid.uuid4()}.png")

            cv2.imwrite(tmp_in, blended_region)
            gan.generate(tmp_in, tmp_out)
            refined = cv2.imread(tmp_out)

            if os.path.exists(tmp_in):
                os.remove(tmp_in)
            if os.path.exists(tmp_out):
                os.remove(tmp_out)

            if refined is not None:
                refined = cv2.resize(
                    refined, (blended_region.shape[1], blended_region.shape[0])
                )
                return refined
        except Exception as e:
            print(f"[Stitch] Neural synthesis failed: {e}")

        return blended_region

    @staticmethod
    def _apply_apap_warp(
        img: np.ndarray, mesh: np.ndarray, grid_size: Tuple[int, int]
    ) -> np.ndarray:
        """
        Applies the APAP mesh warp using bilinear interpolation between local homographies.
        """
        h, w = img.shape[:2]
        grid_h, grid_w = grid_size

        # Create full-resolution map
        map_x = np.zeros((h, w), dtype=np.float32)
        map_y = np.zeros((h, w), dtype=np.float32)

        # Calculate cell dimensions
        cell_h = h / grid_h
        cell_w = w / grid_w

        for i in range(grid_h):
            for j in range(grid_w):
                # Local homographies at corners of the cell
                h00 = mesh[i, j]
                h01 = mesh[i, j + 1]
                h10 = mesh[i + 1, j]
                h11 = mesh[i + 1, j + 1]

                # Pixel coordinates for this cell
                y_start, y_end = int(i * cell_h), int((i + 1) * cell_h)
                x_start, x_end = int(j * cell_w), int((j + 1) * cell_w)

                if y_start >= h or x_start >= w:
                    continue

                yy, xx = np.mgrid[y_start:y_end, x_start:x_end]
                ones = np.ones_like(xx)
                pts = np.stack([xx, yy, ones], axis=-1).reshape(-1, 3).T

                # Bilinear interpolation of homography coefficients?
                # Faster to just use the cell center homography or interpolate points.
                # Let's interpolate the transformed coordinates for smoothness.

                def transform(H, p):
                    res = H @ p
                    return res[0] / res[2], res[1] / res[2]

                u00, v00 = transform(h00, pts)
                u01, v01 = transform(h01, pts)
                u10, v10 = transform(h10, pts)
                u11, v11 = transform(h11, pts)

                # Bilinear weights
                fy = ((yy - y_start) / (y_end - y_start)).flatten()
                fx = ((xx - x_start) / (x_end - x_start)).flatten()

                u = (
                    (1 - fy) * (1 - fx) * u00
                    + (1 - fy) * fx * u01
                    + fy * (1 - fx) * u10
                    + fy * fx * u11
                )
                v = (
                    (1 - fy) * (1 - fx) * v00
                    + (1 - fy) * fx * v01
                    + fy * (1 - fx) * v10
                    + fy * fx * v11
                )

                map_x[y_start:y_end, x_start:x_end] = u.reshape(
                    y_end - y_start, x_end - x_start
                )
                map_y[y_start:y_end, x_start:x_end] = v.reshape(
                    y_end - y_start, x_end - x_start
                )

        return cv2.remap(img, map_x, map_y, cv2.INTER_LANCZOS4)

    @staticmethod
    def _apply_basic_shading_correction(images: List[np.ndarray]) -> List[np.ndarray]:
        """
        Estimates and applies BaSiC shading correction to a batch of images.
        """
        print("[Stitch] Applying BaSiC Shading Correction...")
        # Deferred import -- see _neural_synthesis_blending's comment above.
        from .manager import ImageMerger

        basic = ImageMerger._get_basic()
        return basic.process_batch(images)

    @staticmethod
    def _global_bundle_adjustment(
        pts_matches: List[Dict], initial_poses: List[np.ndarray], iterations: int = 50
    ) -> List[np.ndarray]:
        """
        Refines tile poses using a global least-squares optimization (Bundle Adjustment).
        pts_matches: List of dicts with {'i': idx1, 'j': idx2, 'pts_i': ..., 'pts_j': ...}
        initial_poses: List of (3, 3) homographies or (2, 3) affine matrices.
        """
        num_tiles = len(initial_poses)
        # We optimize for (dx, dy) for each tile (simplest translation-only BA)
        # In a more complex version, we could optimize homography parameters.
        x0 = np.zeros(num_tiles * 2)
        for i in range(num_tiles):
            # Extract translation from initial pose (assuming affine/translation)
            x0[i * 2] = initial_poses[i][0, 2]
            x0[i * 2 + 1] = initial_poses[i][1, 2]

        def residuals(params):
            res = []
            for m in pts_matches:
                i, j = m["i"], m["j"]
                pts_i, pts_j = m["pts_i"], m["pts_j"]

                # Current translation for tile i and j
                ti = params[i * 2 : i * 2 + 2]
                tj = params[j * 2 : j * 2 + 2]

                # Residual: (pts_i + ti) - (pts_j + tj)
                diff = (pts_i + ti) - (pts_j + tj)
                res.extend(diff.flatten())

            # Regularization: penalize deviation from initial poses to prevent drift/jitter
            # weight proportional to 1/sqrt(num_matches) to balance data and prior
            reg_weight = 0.5
            for i in range(num_tiles):
                res.append(reg_weight * (params[i * 2] - x0[i * 2]))
                res.append(reg_weight * (params[i * 2 + 1] - x0[i * 2 + 1]))

            return np.array(res)

        print(f"[Stitch] Optimizing {num_tiles} tiles with Global Bundle Adjustment...")
        res = least_squares(
            residuals, x0, verbose=0, x_scale="jac", ftol=1e-4, method="trf"
        )

        optimized_poses = []
        for i in range(num_tiles):
            pose = initial_poses[i].copy()
            pose[0, 2] = res.x[i * 2]
            pose[1, 2] = res.x[i * 2 + 1]
            optimized_poses.append(pose)

        return optimized_poses

    @staticmethod
    def _poisson_blend(
        img_target: np.ndarray, img_source: np.ndarray, mask: np.ndarray
    ) -> np.ndarray:
        """
        Seamlessly blends source into target using Poisson image editing.
        """
        # Poisson blending needs a bounding box
        y, x = np.where(mask > 0)
        if len(y) == 0:
            return img_target

        y0, y1 = y.min(), y.max() + 1
        x0, x1 = x.min(), x.max() + 1
        center = ((x0 + x1) // 2, (y0 + y1) // 2)

        try:
            # MIXED_CLONE is often better for panoramas as it preserves target textures
            return cv2.seamlessClone(
                img_source, img_target, mask, center, cv2.MIXED_CLONE
            )
        except Exception:
            # Fallback to simple mask copy if Poisson fails
            res = img_target.copy()
            idx = mask > 0
            res[idx] = img_source[idx]
            return res

    @staticmethod
    def _find_optimal_seam_dp(
        img1: np.ndarray, img2: np.ndarray, horizontal: bool = True
    ) -> np.ndarray:
        """
        Finds the optimal seam between two images using dynamic programming.
        Minimize the energy (difference) between images.
        """
        # Compute energy map: color difference + gradient difference
        diff = cv2.absdiff(img1, img2).astype(np.float32).mean(axis=2)
        # Add gradient energy to prefer seams along natural edges
        grad_x = cv2.Sobel(diff, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(diff, cv2.CV_32F, 0, 1, ksize=3)
        energy = diff + 0.5 * (np.abs(grad_x) + np.abs(grad_y))

        h, w = energy.shape
        if not horizontal:
            energy = energy.T
            h, w = w, h

        # DP: M(i, j) = E(i, j) + min(M(i-1, j-1), M(i-1, j), M(i-1, j+1))
        M = energy.copy()
        for i in range(1, h):
            for j in range(w):
                prev_min = M[i - 1, j]
                if j > 0:
                    prev_min = min(prev_min, M[i - 1, j - 1])
                if j < w - 1:
                    prev_min = min(prev_min, M[i - 1, j + 1])
                M[i, j] += prev_min

        # Backtrack to find the path
        path = np.zeros(h, dtype=np.int32)
        j = np.argmin(M[h - 1, :])
        path[h - 1] = j
        for i in range(h - 2, -1, -1):
            choices = [j]
            if j > 0:
                choices.append(j - 1)
            if j < w - 1:
                choices.append(j + 1)
            j = choices[np.argmin([M[i, c] for c in choices])]
            path[i] = j

        if not horizontal:
            return path  # Path is now vertical seam
        return path

    @staticmethod
    def _calculate_niqe(img: np.ndarray) -> float:
        """
        Simplified no-reference image quality assessment.
        Higher is worse.
        """
        # This is a placeholder for a real NIQE implementation.
        # We can use standard deviation of gradients as a proxy for sharpness.
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
        mag = np.sqrt(gx**2 + gy**2)
        return float(100.0 / (np.mean(mag) + 1e-6))


__all__ = ["_LegacyCompositingMixin"]

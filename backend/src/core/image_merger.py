import cv2
import gc
import os
import numpy as np
import base
import torch

from . import FSETool
from PIL import Image
from typing import List, Tuple, Optional, Dict
from backend.src.utils.definitions import AlignMode
from backend.src.models.siamese_network import SiameseModelLoader
from backend.src.models.gan_wrapper import GanWrapper
from backend.src.models.birefnet_wrapper import BiRefNetWrapper
from backend.src.models.basic_wrapper import BaSiCWrapper
from backend.src.models.loftr_wrapper import LoFTRWrapper
from backend.src.core.anime_stitch_pipeline import AnimeStitchPipeline


# Define the decorator factories needed for the merge methods
MERGE_IMAGES_PREFIX = FSETool.prefix_create_directory(arg_id=2, is_filepath=True)

MERGE_DIR_IMAGES_PREFIX = FSETool.prefix_create_directory(
    arg_id=3, kwarg_name="output_path", is_filepath=True
)


class ImageMerger:
    """
    A comprehensive tool for merging and transforming images,
    supporting horizontal, vertical, grid layouts, panoramic stitching, and GIFs.
    Horizontal/Vertical/Grid methods now use Rust Backend.
    """

    # --- AI Model Caching (Lazy Loaders)
    _gan_inst = None
    _birefnet_inst = None
    _basic_inst = None
    _loftr_inst = None
    _siamese_inst = None

    @classmethod
    def _get_gan(cls):
        if cls._gan_inst is None:
            cls._gan_inst = GanWrapper()
        return cls._gan_inst

    @classmethod
    def _get_birefnet(cls):
        if cls._birefnet_inst is None:
            cls._birefnet_inst = BiRefNetWrapper()
        return cls._birefnet_inst

    @classmethod
    def _get_basic(cls):
        if cls._basic_inst is None:
            cls._basic_inst = BaSiCWrapper()
        return cls._basic_inst

    @classmethod
    def _get_loftr(cls):
        if cls._loftr_inst is None:
            cls._loftr_inst = LoFTRWrapper()
        return cls._loftr_inst

    @classmethod
    def _get_siamese(cls):
        if cls._siamese_inst is None:
            cls._siamese_inst = SiameseModelLoader()
        return cls._siamese_inst

    # --- Core Merging Logic
    @staticmethod
    def _merge_images_panorama(image_paths: List[str], output_path: str) -> Image.Image:
        """
        Stitches images into a panorama using OpenCV's default PANORAMA mode.
        Good for rotating camera shots (perspective transformation).
        """
        # Disable OpenCL to prevent memory corruption/malloc errors during stitching
        cv2.ocl.setUseOpenCL(False)

        cv_images = []
        for path in image_paths:
            img = cv2.imread(path)
            if img is not None:
                cv_images.append(img)
            else:
                print(f"Warning: Could not read image for panorama: {path}")

        if len(cv_images) < 2:
            raise ValueError("Need at least 2 valid images to create a panorama.")

        # Initialize Stitcher in PANORAMA mode (Mode 0)
        try:
            stitcher = cv2.Stitcher_create(mode=0)
        except AttributeError:
            # Fallback for older OpenCV versions
            stitcher = cv2.createStitcher(False)

        # Perform stitching
        status, pano = stitcher.stitch(cv_images)

        # Force cleanup of any internal highgui/Qt resources before we return
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass

        if status != cv2.Stitcher_OK:
            error_map = {
                cv2.Stitcher_ERR_NEED_MORE_IMGS: "Need more images",
                cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "Homography estimation failed",
                cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera params failed",
            }
            err_msg = error_map.get(status, f"Error code {status}")
            raise RuntimeError(f"Panorama stitching failed: {err_msg}")

        # Convert BGR (OpenCV) to RGB (PIL)
        pano_rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
        merged_image = Image.fromarray(pano_rgb)

        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_scan_stitch(
        image_paths: List[str], output_path: str
    ) -> Image.Image:
        """
        Stitches a large number of images with small differences (flat scans).
        Uses OpenCV's SCANS mode which optimizes for affine/flat transformations.
        """
        # Disable OpenCL to prevent memory corruption/malloc errors during stitching
        cv2.ocl.setUseOpenCL(False)

        # 1. Read images
        cv_images = []
        for path in image_paths:
            img = cv2.imread(path)
            if img is not None and img.size > 0:
                cv_images.append(img)
            else:
                print(f"Warning: Could not read image: {path}")

        if len(cv_images) < 2:
            raise ValueError("Need at least 2 valid images to stitch.")

        # 2. Initialize Stitcher in SCANS mode
        # Mode 1 = SCANS (Optimized for flat/affine stitching)
        try:
            stitcher = cv2.Stitcher_create(mode=1)
        except AttributeError:
            # Fallback: older OpenCV versions might not accept mode arg in create
            stitcher = cv2.createStitcher(True)  # True often maps to scans/try_use_gpu

        # 3. Setting Registration Resol (higher value = more keypoints for small diffs)
        # Default is usually 0.6, increasing helps with small overlaps
        stitcher.setRegistrationResol(0.8)

        # 4. Perform Stitching
        status, pano = stitcher.stitch(cv_images)

        # Force cleanup of any internal highgui/Qt resources before we return
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass

        if status != cv2.Stitcher_OK:
            error_map = {
                cv2.Stitcher_ERR_NEED_MORE_IMGS: "Need more images",
                cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "Homography estimation failed",
                cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera params failed",
            }
            err_msg = error_map.get(status, f"Error code {status}")
            raise RuntimeError(f"Scan stitching failed: {err_msg}")

        # 5. Convert & Save
        pano_rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
        merged_image = Image.fromarray(pano_rgb)

        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_sequential(
        image_paths: List[str], output_path: str
    ) -> Image.Image:
        """
        Sequentially stitches images (A->B) vertically using template matching.
        """
        cv_images = []
        for p in image_paths:
            img = cv2.imread(p)
            if img is not None:
                cv_images.append(img)
        if len(cv_images) < 2:
            raise ValueError("Need 2+ images for sequential merge.")

        def smoothstep_alpha(n: int) -> np.ndarray:
            t = np.linspace(0.0, 1.0, n, dtype=np.float64)
            return (1.0 + np.cos(np.pi * t)) / 2.0

        def fix_seam_scanlines(
            arr: np.ndarray, cut_y: int, radius: int = 16
        ) -> np.ndarray:
            """
            Replace rows within ±radius of cut_y that deviate from BOTH
            immediate neighbours by more than 15% of the local brightness.
            Non-cascading (reads frozen copy, writes working copy). 3 passes.
            """
            h = arr.shape[0]
            arr = arr.copy()
            for _ in range(3):
                orig = arr.copy()
                changed = False
                for y in range(max(1, cut_y - radius), min(h - 1, cut_y + radius)):
                    rm = float(arr[y].mean())
                    am = float(orig[y - 1].mean())
                    bm = float(orig[y + 1].mean())
                    nbr = (am + bm) / 2.0
                    # Use relative threshold: 15% of neighbour mean, min 8 units
                    thr = max(nbr * 0.15, 8.0)
                    if abs(rm - am) > thr and abs(rm - bm) > thr:
                        arr[y] = (
                            orig[y - 1].astype(np.float64) * 0.5
                            + orig[y + 1].astype(np.float64) * 0.5
                        )
                        changed = True
                if not changed:
                    break
            return arr

        # 1. Width-normalise
        target_w = cv_images[0].shape[1]
        resized = []
        for img in cv_images:
            h, w = img.shape[:2]
            if w != target_w:
                img = cv2.resize(img, (target_w, int(h * target_w / w)))
            resized.append(img)

        # 2. Accumulate
        canvas = resized[0].astype(np.float64)
        prev_h = resized[0].shape[0]

        for i in range(1, len(resized)):
            next_img = resized[i].astype(np.float64)
            h_canvas = canvas.shape[0]
            h_next = next_img.shape[0]
            slice_h = 64
            max_search = int(min(h_next * 0.90, 5000))
            ovlp_search = min(h_canvas, max_search)
            # Keep at least 30% of canvas — prevents false top-of-image matches
            min_valid_cut = max(h_canvas - prev_h, int(h_canvas * 0.05))

            best_val, best_spy, match_type = 0.0, -1.0, None
            c_u8 = np.clip(canvas, 0, 255).astype(np.uint8)
            n_u8 = np.clip(next_img, 0, 255).astype(np.uint8)

            def spx(res, loc):
                y, x = loc[1], loc[0]
                if 0 < y < res.shape[0] - 1:
                    d = 2 * res[y - 1, x] - 4 * res[y, x] + 2 * res[y + 1, x]
                    if abs(d) > 1e-6:
                        return y + (res[y - 1, x] - res[y + 1, x]) / d
                return float(y)

            # Method A — bottom of canvas in top of next
            if ovlp_search > slice_h:
                tmpl = c_u8[-slice_h:, :]
                if tmpl.std() > 5.0:
                    roi = n_u8[:ovlp_search, :]
                    res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
                    _, v, _, loc = cv2.minMaxLoc(res)
                    spy = spx(res, loc)
                    cut = (h_canvas - slice_h) - int(round(spy))
                    if v > 0.35 and min_valid_cut <= cut < h_canvas and v > best_val:
                        best_val, best_spy, match_type = v, spy, "A"

            # Method B — top of next in bottom of canvas
            if ovlp_search > slice_h:
                tmpl = n_u8[:slice_h, :]
                if tmpl.std() > 5.0:
                    rs = h_canvas - ovlp_search
                    roi = c_u8[rs:, :]
                    res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
                    _, v, _, loc = cv2.minMaxLoc(res)
                    spy = spx(res, loc)
                    cut = rs + int(round(spy))
                    if v > 0.35 and min_valid_cut <= cut < h_canvas and v > best_val:
                        best_val, best_spy, match_type = v, spy, "B"

            if match_type:
                if match_type == "A":
                    final_cut = (h_canvas - slice_h) - int(round(best_spy))
                else:
                    rs = h_canvas - ovlp_search
                    final_cut = rs + int(round(best_spy))

                final_cut = max(min_valid_cut, min(final_cut, h_canvas - 1))
                overlap_h = h_canvas - final_cut
                print(
                    f"[sequential] frame {i}: match={match_type} val={best_val:.3f} "
                    f"cut={final_cut}/{h_canvas} overlap={overlap_h}px"
                )

                # Repair scanline artifacts around the cut point
                canvas = fix_seam_scanlines(canvas, final_cut, radius=16)

                blend_h = max(1, min(overlap_h, 96))
                top_part = canvas[:final_cut]
                img1_strip = canvas[final_cut : final_cut + blend_h].copy()
                img2_strip = next_img[0:blend_h].copy()

                # Brightness correction — only apply if delta is small (< 30/channel).
                # Large delta means a scene change; correcting it corrupts colours.
                skip, win = 4, 48
                ref_a = canvas[
                    max(0, final_cut - win - skip) : max(0, final_cut - skip)
                ]
                ref_b = next_img[skip : skip + win]
                if ref_a.size > 0 and ref_b.size > 0:
                    delta = ref_a.mean(axis=(0, 1)) - ref_b.mean(axis=(0, 1))
                    if np.abs(delta).max() < 30.0:  # same-scene correction only
                        ramp = np.linspace(1.0, 0.0, blend_h, dtype=np.float64).reshape(
                            -1, 1, 1
                        )
                        img2_strip = img2_strip + delta * ramp
                        tail = min(h_next - blend_h, 300)
                        if tail > 0:
                            taper = np.linspace(
                                1.0, 0.0, tail, dtype=np.float64
                            ).reshape(-1, 1, 1)
                            next_img = next_img.copy()
                            next_img[blend_h : blend_h + tail] += delta * taper
                    else:
                        print(
                            f"[sequential] skipping brightness correction "
                            f"(delta too large: {delta.round(1)})"
                        )

                alpha = smoothstep_alpha(blend_h).reshape(-1, 1, 1)
                blended = img1_strip * alpha + np.clip(img2_strip, 0, 255) * (
                    1.0 - alpha
                )

                canvas = np.vstack([top_part, blended, next_img[blend_h:]])
                prev_h = h_next
            else:
                print(f"[sequential] frame {i}: no overlap found, stacking directly")
                canvas = np.vstack([canvas, next_img])
                prev_h = h_next

        result = np.clip(canvas, 0, 255).astype(np.uint8)
        rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        merged = Image.fromarray(rgb)
        merged.save(output_path)
        return merged

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
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
    ) -> np.ndarray:
        """
        Uses AnimeGAN2 to refine the transition zone, ensuring structural and stylistic integrity.
        """
        try:
            # Use cached GAN instance
            gan = ImageMerger._get_gan()

            # Temporary file paths
            import tempfile
            import uuid

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
        from scipy.optimize import least_squares

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

    @staticmethod
    def perfect_stitch(
        image_paths: List[str],
        output_path: str,
        # Legacy parameters kept for call-site compatibility — no longer used
        # internally (the pipeline selects strategies automatically).
        edge_crop: int = 0,
        pyramid_levels: int = 3,
        use_siamese: bool = True,
        use_apap: bool = True,
        use_lsd: bool = True,
        use_gan: bool = True,
        use_birefnet: bool = True,
        # New pipeline control knobs
        use_basic: bool = True,
        use_loftr: bool = True,
        use_ecc: bool = True,
        renderer: str = "median",
        composite_fg: bool = True,
    ) -> Image.Image:
        """
        High-fidelity anime panorama stitching pipeline.

        Delegates to AnimeStitchPipeline which implements the full 13-stage
        research-backed pipeline:

          Stage 1  — Load frames + broadcast dark-border trim
          Stage 2  — Lanczos width normalisation
          Stage 3  — BaSiC photometric correction (broadcast dimming, vignette)
          Stage 4  — BiRefNet/ToonOut foreground masking
          Stage 5-6 — LoFTR dense matching on background only (+ skip-pair edges)
          Stage 7  — Global Levenberg-Marquardt bundle adjustment
          Stage 8  — Pyramid ECC sub-pixel refinement (mask-aware)
          Stage 9  — Global canvas sizing
          Stage 10 — Temporal median render (Overmix-style noise suppression)
          Stage 11 — Foreground character re-composite (nearest-centre Voronoi)
          Stage 12 — Multi-band (Laplacian) seam blend on residual overlaps
          Stage 13 — Largest-inscribed-rectangle boundary crop

        Fallback chain per edge:
          LoFTR + MAGSAC++ → masked template match → high-pass phase correlation
          If zero edges found → OpenCV SCANS mode (same as _merge_images_scan_stitch)

        Parameters
        ----------
        image_paths   : ordered list of frame paths.
        output_path   : destination file (PNG or WEBP).
        use_birefnet  : enable BiRefNet/ToonOut foreground masking.
        use_basic     : enable BaSiC broadcast-dimming correction.
        use_loftr     : enable LoFTR feature matching (falls back to template if False).
        use_ecc       : enable pyramid ECC sub-pixel refinement.
        renderer      : 'median' (Overmix temporal denoising, recommended) |
                        'blend'  (sequential Laplacian seam, closest to SCANS) |
                        'first'  (fast, no blending).
        composite_fg  : re-paste the foreground character on the median background.

        Legacy parameters (edge_crop, pyramid_levels, use_siamese, use_apap,
        use_lsd, use_gan) are accepted but ignored — the new pipeline selects
        strategies adaptively.
        """
        pipeline = AnimeStitchPipeline(
            use_basic=use_basic,
            use_birefnet=use_birefnet,
            use_loftr=use_loftr,
            use_ecc=use_ecc,
            renderer=renderer,
            composite_fg=composite_fg,
        )
        return pipeline.run(image_paths, output_path)

    def _create_gif(
        image_paths: List[str], output_path: str, duration: int = 500
    ) -> Image.Image:
        """
        Creates an animated GIF from the provided images.
        Resizes all images to match the size of the first image to ensure consistency.
        """
        if not image_paths:
            raise ValueError("No images provided for GIF creation.")

        # Open all images
        images = [Image.open(p) for p in image_paths]

        # Use first image as base size
        base_size = images[0].size

        # Normalize all frames to the base size
        frames = []
        for img in images:
            if img.size != base_size:
                # Resize using Lanczos for quality
                frames.append(img.resize(base_size, Image.Resampling.LANCZOS))
            else:
                frames.append(img)

        # Save GIF
        if output_path.lower().endswith(".png"):
            output_path = output_path[:-4] + ".gif"

        frames[0].save(
            output_path,
            format="GIF",
            append_images=frames[1:],
            save_all=True,
            duration=duration,
            loop=0,
            optimize=True,
        )

        return frames[0]

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=MERGE_IMAGES_PREFIX)
    def merge_images(
        self,
        image_paths: List[str],
        output_path: str,
        direction: str,
        grid_size: Optional[Tuple[int, int]] = None,
        spacing: int = 0,
        align_mode: AlignMode = "Default (Top/Center)",
        duration: int = 500,
    ) -> Image.Image:
        """
        Merge images based on direction.
        Options: 'horizontal', 'vertical', 'grid', 'panorama', 'stitch', 'sequential', 'gif'.
        """
        # --- Map AlignMode to simpler Rust strings ---
        # "Default (Top/Center)" -> "top" (horiz), "left" (vert) or "center"?
        # Actually in Rust I implemented simple match.
        # Python:
        #   Horiz: Top/Center is Center for vertical alignment usually?
        #   Let's check Python original:
        #   Horiz: if Center/Default -> y_offset = (canvas_h - current_h)//2. So it is CENTER.
        #   Vert: if Center/Default -> x_offset = (canvas_w - current_w)//2. So it is CENTER.

        # Rust `image_merger.rs` map:
        #   Horiz: "center" -> center, "bottom" -> bottom, default -> 0 (top).
        #   Vert: "center" -> center, "right" -> right, default -> 0 (left).

        # Mapping:
        rust_align = "top"
        if align_mode in ["Center", "Default (Top/Center)"]:
            rust_align = "center"
        elif align_mode == "Align Bottom/Right":
            rust_align = "bottom" if direction == "horizontal" else "right"
        elif align_mode in ["Scaled (Grow Smallest)", "Squish (Shrink Largest)"]:
            rust_align = "stretch"  # I implemented "stretch" in Rust to mean resize.

        if direction == "horizontal":
            base.merge_images_horizontal(image_paths, output_path, spacing, rust_align)
            return Image.open(output_path)
        elif direction == "vertical":
            base.merge_images_vertical(image_paths, output_path, spacing, rust_align)
            return Image.open(output_path)
        elif direction == "grid":
            if grid_size is None:
                raise ValueError("grid_size must be provided for grid merging")
            rows, cols = grid_size
            if len(image_paths) > rows * cols:
                raise ValueError("More images provided than the grid slots can hold.")
            base.merge_images_grid(image_paths, output_path, rows, cols, spacing)
            return Image.open(output_path)
        elif direction == "panorama":
            merged_img = self._merge_images_panorama(image_paths, output_path)
        elif direction == "stitch":
            merged_img = self._merge_images_scan_stitch(image_paths, output_path)
        elif direction == "sequential":
            merged_img = self._merge_images_sequential(image_paths, output_path)
        elif direction == "perfect":
            merged_img = self.perfect_stitch(image_paths, output_path)
        elif direction == "gif":
            merged_img = self._create_gif(image_paths, output_path, duration)
        else:
            raise ValueError(f"ERROR: invalid direction '{direction}'")

        print(
            f"Merged {len(image_paths)} images into '{output_path}' using direction '{direction}'."
        )
        return merged_img

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=MERGE_DIR_IMAGES_PREFIX)
    def merge_directory_images(
        self,
        directory: str,
        input_formats: List[str],
        output_path: str,
        direction: str = "horizontal",
        grid_size: Optional[Tuple[int, int]] = None,
        spacing: int = 0,
        align_mode: AlignMode = "Default (Top/Center)",
        duration: int = 500,
    ) -> Optional[Image.Image]:
        image_paths = []
        for fmt in input_formats:
            image_paths.extend(FSETool.get_files_by_extension(directory, fmt))

        if not image_paths:
            print(
                f"WARNING: No images found in directory '{directory}' with formats {input_formats}."
            )
            return None

        return self.merge_images(
            image_paths,
            output_path,
            direction,
            grid_size,
            spacing,
            align_mode,
            duration,
        )

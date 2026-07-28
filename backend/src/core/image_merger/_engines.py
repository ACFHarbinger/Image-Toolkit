"""External/OpenCV panorama stitching engines for ``ImageMerger``.

Each engine implements one ``merge_images(direction="panorama", engine=...)``
option: OpenCV's built-in Stitcher, the system Hugin CLI toolchain, the
vendored Overmix binary, or the simple sequential template-match stitcher.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import tempfile
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

from backend.src.constants import ROOT_DIR


class _EngineMixin:
    """Panorama-stitching engine implementations for ``ImageMerger``."""

    @staticmethod
    def _merge_images_opencv(
        image_paths: List[str],
        output_path: str,
        stitcher_mode: int = 0,
        registration_resol: float = 0.6,
    ) -> Image.Image:
        """
        Stitches images using OpenCV's Stitcher.

        stitcher_mode : 0 = PANORAMA (rotating-camera/perspective transform),
                         1 = SCANS (affine/flat — small pan shots, near-duplicate
                         frames; this is what a separate "stitch" mode used to
                         mean before it was folded into this one engine).
        registration_resol : keypoint registration resolution; higher values
                         find more keypoints, which helps on small-overlap or
                         near-duplicate frames (SCANS mode used 0.8 by default;
                         now user-facing for both modes).
        """
        # Disable OpenCL to prevent memory corruption/malloc errors during stitching
        cv2.ocl.setUseOpenCL(False)

        cv_images = []
        for path in image_paths:
            img = cv2.imread(path)
            if img is not None and img.size > 0:
                cv_images.append(img)
            else:
                print(f"Warning: Could not read image: {path}")

        if len(cv_images) < 2:
            raise ValueError("Need at least 2 valid images to stitch.")

        try:
            stitcher = cv2.Stitcher_create(mode=stitcher_mode)
        except AttributeError:
            # Fallback for older OpenCV versions
            stitcher = cv2.createStitcher(stitcher_mode == 1)

        stitcher.setRegistrationResol(registration_resol)

        status, pano = stitcher.stitch(cv_images)

        # Force cleanup of any internal highgui/Qt resources before we return
        with contextlib.suppress(cv2.error):
            cv2.destroyAllWindows()

        if status != cv2.Stitcher_OK:
            error_map = {
                cv2.Stitcher_ERR_NEED_MORE_IMGS: "Need more images",
                cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "Homography estimation failed",
                cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera params failed",
            }
            err_msg = error_map.get(status, f"Error code {status}")
            raise RuntimeError(f"OpenCV stitching failed: {err_msg}")

        # Convert BGR (OpenCV) to RGB (PIL)
        pano_rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
        merged_image = Image.fromarray(pano_rgb)

        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _read_pto_canvas_size(pto_path: str) -> Tuple[int, int]:
        """Parse the ``p`` (panorama) line's ``w``/``h`` fields from a .pto file."""
        with open(pto_path, "r") as fh:
            for line in fh:
                if line.startswith("p "):
                    w_match = re.search(r"\bw(\d+)", line)
                    h_match = re.search(r"\bh(\d+)", line)
                    if w_match and h_match:
                        return int(w_match.group(1)), int(h_match.group(1))
        raise RuntimeError(f"could not parse canvas size from {pto_path}")

    @staticmethod
    def _merge_images_hugin(
        image_paths: List[str],
        output_path: str,
        projection: int = 0,
        linear_match: bool = True,
    ) -> Image.Image:
        """
        Stitches images using the system Hugin CLI toolchain (GPL/GPL-adjacent
        external tool via apt hugin-tools/enblend — run as a subprocess chain,
        never linked): pto_gen -> cpfind -> autooptimiser -> pano_modify ->
        nona -> enblend. See roadmap moon/roadmaps/asp.md §0.5 and its field
        notes for why the system packages are used instead of building the
        vendor/Hugin submodule fork (its CMake only wires up align_image_stack).

        projection   : Hugin's own numbering — 0=Rectilinear, 1=Cylindrical,
                       2=Equirectangular.
        linear_match : use cpfind --linearmatch (a scrolling pan/scan
                       sequence) instead of --multirow (rotating-camera
                       panorama, Hugin's own default heuristic).
        """
        tools = ("pto_gen", "cpfind", "autooptimiser", "pano_modify", "nona", "enblend")
        missing = [t for t in tools if shutil.which(t) is None]
        if missing:
            raise RuntimeError(
                f"Hugin toolchain not found: {', '.join(missing)} "
                "(install with: sudo apt-get install hugin-tools enblend enfuse)"
            )
        if len(image_paths) < 2:
            raise ValueError("Need at least 2 images for Hugin stitching.")

        abs_paths = [os.path.abspath(p) for p in image_paths]

        def _run(cmd: List[str], cwd: str) -> None:
            proc = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=300
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"{cmd[0]} failed: {(proc.stderr or proc.stdout).strip()[-500:]}"
                )

        with tempfile.TemporaryDirectory(prefix="hugin_merge_") as tmp:
            _run(["pto_gen", "-o", "project.pto", "-p", str(projection), *abs_paths], tmp)
            cpfind_cmd = ["cpfind", "--linearmatch" if linear_match else "--multirow"]
            cpfind_cmd += ["-o", "project_cp.pto", "project.pto"]
            _run(cpfind_cmd, tmp)
            _run(
                ["autooptimiser", "-a", "-l", "-s", "-o", "project_opt.pto", "project_cp.pto"],
                tmp,
            )
            _run(
                [
                    "pano_modify", "-p", str(projection), "--fov=AUTO", "--canvas=AUTO",
                    "--crop=AUTOOUTSIDE", "--output-cropped-tiff",
                    "-o", "project_mod.pto", "project_opt.pto",
                ],
                tmp,
            )

            # §0.5 field-note finding: rectilinear (and cylindrical) FOV
            # optimization degenerates for long planar-scroll sequences — the
            # implied FOV needed to cover many frames' worth of pure
            # translation approaches Hugin's 180° projection singularity,
            # producing a canvas hundreds of thousands of pixels wide/tall
            # that then hangs or OOMs nona. Fail fast instead.
            canvas_w, canvas_h = _EngineMixin._read_pto_canvas_size(
                os.path.join(tmp, "project_mod.pto")
            )
            _MAX_CANVAS_DIM = 20000
            if canvas_w > _MAX_CANVAS_DIM or canvas_h > _MAX_CANVAS_DIM:
                raise RuntimeError(
                    f"degenerate canvas size {canvas_w}x{canvas_h} — the pan "
                    "sequence is too long for Hugin's rectilinear/cylindrical "
                    "FOV model (approaches the 180° projection singularity)"
                )

            _run(["nona", "-m", "TIFF_m", "-o", "nona_", "project_mod.pto"], tmp)

            layers = sorted(
                p for p in os.listdir(tmp) if p.startswith("nona_") and p.endswith(".tif")
            )
            if len(layers) < 2:
                raise RuntimeError(f"nona produced {len(layers)} layer(s), need >=2")

            # enblend's overlap-check safety guard (designed for photography
            # with partial overlap) always trips on anime pan frames, which
            # overlap almost entirely by design. overlap-check-threshold=0
            # disables that specific check; the blend itself is unaffected
            # (roadmap §0.5 field notes).
            _run(
                [
                    "enblend", "--parameter=overlap-check-threshold=0",
                    "-o", "result.tif", *layers,
                ],
                tmp,
            )

            merged_image = Image.open(os.path.join(tmp, "result.tif")).convert("RGB")
            merged_image.save(output_path)
            return merged_image

    @staticmethod
    def _merge_images_overmix(
        image_paths: List[str],
        output_path: str,
        aligner: str = "Recursive",
        render_stat: str = "average",
    ) -> Image.Image:
        """
        Stitches images using Overmix (GPL-3.0 external tool — run as a
        subprocess, never linked). Requires vendor/Overmix/build/OvermixCli,
        built via desktop/linux/scripts/setup_overmix.sh. See roadmap
        moon/roadmaps/asp.md §0.3 and its field notes.

        aligner     : Overmix's own aligner names — Recursive / Average / Linear.
        render_stat : "average" (Overmix's dedicated average render) or one of
                      the statistics render's methods: avg / median / min /
                      max / difference.
        """
        overmix_bin = ROOT_DIR / "vendor" / "Overmix" / "build" / "OvermixCli"
        if not overmix_bin.exists():
            raise RuntimeError(
                f"OvermixCli not built at {overmix_bin}; run "
                "desktop/linux/scripts/setup_overmix.sh"
            )
        if len(image_paths) < 2:
            raise ValueError("Need at least 2 images for Overmix stitching.")

        render_arg = (
            "average:false:false"
            if render_stat == "average"
            else f"statistics:{render_stat}"
        )
        # Comparator fixed to Gradient (coarse-to-fine pyramid search) —
        # roadmap §0.3 field notes found BruteForce far too slow at full
        # frame resolution to expose as a real option.
        cmd = [
            str(overmix_bin),
            *[os.path.abspath(p) for p in image_paths],
            "--comparator=Gradient:1/false/0:both:0.75:1:6:1638",
            f"--align={aligner}",
            f"--render={render_arg}",
            f"--save=0:{output_path}",
        ]
        env = dict(os.environ)
        env.setdefault("OMP_NUM_THREADS", "4")
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(
                f"Overmix failed: {(proc.stderr or proc.stdout).strip()[-500:]}"
            )
        return Image.open(output_path)

    @staticmethod
    def _merge_images_sequential(  # noqa: C901
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


__all__ = ["_EngineMixin"]

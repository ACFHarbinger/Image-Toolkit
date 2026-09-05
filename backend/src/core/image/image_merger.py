"""``ImageMerger`` — public merge dispatch, composed from per-concern mixins."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import yaml
from loguru import logger
from PIL import Image

from backend.src.constants import BACKEND_DIR, AlignMode
from backend.src.core import telemetry

from .. import FSETool

try:
    import base
except ImportError:
    base = None  # type: ignore[assignment]

from ._engines import _EngineMixin
from ._gif_video import _GifVideoMixin
from ._legacy_compositing import _LegacyCompositingMixin
from ._models import _ModelCacheMixin

# Define the decorator factories needed for the merge methods
MERGE_IMAGES_PREFIX = FSETool.prefix_create_directory(arg_id=2, is_filepath=True)

MERGE_DIR_IMAGES_PREFIX = FSETool.prefix_create_directory(
    arg_id=3, kwarg_name="output_path", is_filepath=True
)


class ImageMerger(
    _ModelCacheMixin, _EngineMixin, _LegacyCompositingMixin, _GifVideoMixin
):
    """
    A comprehensive tool for merging and transforming images,
    supporting horizontal, vertical, grid layouts, panoramic stitching, and GIFs.
    Horizontal/Vertical/Grid methods now use C++ Backend.
    """

    @staticmethod
    def perfect_stitch(
        image_paths: List[str], output_path: str, **kwargs
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
          If zero edges found → OpenCV SCANS mode (same as _merge_images_opencv(stitcher_mode=1))

        Parameters
        ----------
        image_paths   : ordered list of frame paths.
        output_path   : destination file (PNG or WEBP).
        edge_crop     : pixels to crop from left/right sides (prevents vignette artifacts).
        pyramid_levels: number of Laplacian bands (default 8 for 4K smoothness).
        use_birefnet  : enable BiRefNet/ToonOut foreground masking.
        use_basic     : enable BaSiC broadcast-dimming correction.
        use_loftr     : enable LoFTR feature matching (falls back to template if False).
        use_ecc       : enable pyramid ECC sub-pixel refinement.
        renderer      : 'blend'  (sequential Laplacian seam, robust) |
                        'median' (Overmix temporal denoising) |
                        'first'  (fast, no blending).
        composite_fg  : re-paste the foreground character on the background.

        Legacy parameters (edge_crop, pyramid_levels, use_siamese, use_apap,
        use_lsd, use_gan) are accepted but ignored — the new pipeline selects
        strategies adaptively.
        """
        logger.info(f"Starting Perfect Stitch on {len(image_paths)} frames...")

        # Ensure input images are valid 4K
        for path in image_paths:
            with Image.open(path) as img:
                if img.width < 3840 or img.height < 2160:
                    logger.warning(f"Image at {path} is below 4K resolution.")

        # 1. Start with hardcoded system defaults
        params = {
            "use_basic": kwargs.get("use_basic", False),
            "use_loftr": kwargs.get("use_loftr", True),
            "use_ecc": kwargs.get("use_ecc", False),
            "renderer": kwargs.get("renderer", "median"),
            "composite_fg": kwargs.get("composite_fg", True),
            "motion_model": kwargs.get("motion_model", "translation"),
            "edge_crop": kwargs.get("edge_crop", 80),
            "laplacian_bands": kwargs.get("laplacian_bands", 8),
            "mfsr_mode": kwargs.get("mfsr_mode", False),
            "mfsr_n_dct_iter": kwargs.get("mfsr_n_dct_iter", 20),
            "mfsr_use_prior": kwargs.get("mfsr_use_prior", True),
            "mfsr_use_diffusion": kwargs.get("mfsr_use_diffusion", False),
        }

        # 2. Override with stitch.yaml (Project settings)
        config_path = os.path.join(BACKEND_DIR, "config", "core", "stitch.yaml")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    cfg = yaml.safe_load(os.path.expandvars(f.read()))
                    if cfg:
                        params.update(cfg)
            except Exception as e:
                logger.error(f"Error loading stitch config: {e}")
                pass

        # 3. Override with explicit function arguments (Call-site settings)
        params.update(kwargs)

        # 4. Map 'compositor' to 'renderer' if needed
        if "compositor" in params:
            params["renderer"] = params["compositor"]

        # 5. Initialize and run the pipeline with full parameter propagation
        from asp_backend import AnimeStitchPipeline  # §3.15A lazy

        pipeline = AnimeStitchPipeline(**params)

        return pipeline.run(image_paths, output_path)

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=MERGE_IMAGES_PREFIX)
    def merge_images(  # noqa: C901
        self,
        image_paths: List[str],
        output_path: str,
        direction: str,
        grid_size: Optional[Tuple[int, int]] = None,
        spacing: int = 0,
        align_mode: AlignMode = "Default (Top/Center)",
        duration: int = 500,
        engine: str = "opencv",
        engine_kwargs: Optional[Dict] = None,
    ) -> Image.Image:
        """
        Merge images based on direction.
        Options: 'horizontal', 'vertical', 'grid', 'panorama', 'sequential', 'gif'.

        For direction='panorama', `engine` selects the stitching engine:
        'opencv' (default), 'hugin', 'overmix', or 'asp' (Anime Stitch
        Pipeline). `engine_kwargs` carries engine-specific settings — see
        `_merge_images_opencv`/`_merge_images_hugin`/`_merge_images_overmix`/
        `perfect_stitch` for what each accepts.
        """
        # --- Map AlignMode to simpler C++ strings ---
        # "Default (Top/Center)" -> "top" (horiz), "left" (vert) or "center"?
        # Actually in C++ I implemented simple match.
        # Python:
        #   Horiz: Top/Center is Center for vertical alignment usually?
        #   Let's check Python original:
        #   Horiz: if Center/Default -> y_offset = (canvas_h - current_h)//2. So it is CENTER.
        #   Vert: if Center/Default -> x_offset = (canvas_w - current_w)//2. So it is CENTER.

        # C++ `image_merger.rs` map:
        #   Horiz: "center" -> center, "bottom" -> bottom, default -> 0 (top).
        #   Vert: "center" -> center, "right" -> right, default -> 0 (left).

        # Mapping:
        rust_align = "top"
        if align_mode in ["Center", "Default (Top/Center)"]:
            rust_align = "center"
        elif align_mode == "Align Bottom/Right":
            rust_align = "bottom" if direction == "horizontal" else "right"
        elif align_mode in ["Scaled (Grow Smallest)", "Squish (Shrink Largest)"]:
            rust_align = "stretch"  # I implemented "stretch" in C++ to mean resize.

        if direction == "horizontal":
            with telemetry.NATIVE_IMAGE_BATCH_LOCK:
                base.merge_images_horizontal(image_paths, output_path, spacing, rust_align)
            return Image.open(output_path)
        elif direction == "vertical":
            with telemetry.NATIVE_IMAGE_BATCH_LOCK:
                base.merge_images_vertical(image_paths, output_path, spacing, rust_align)
            return Image.open(output_path)
        elif direction == "grid":
            if grid_size is None:
                raise ValueError("grid_size must be provided for grid merging")
            rows, cols = grid_size
            if len(image_paths) > rows * cols:
                raise ValueError("More images provided than the grid slots can hold.")
            with telemetry.NATIVE_IMAGE_BATCH_LOCK:
                base.merge_images_grid(image_paths, output_path, rows, cols, spacing)
            return Image.open(output_path)
        elif direction == "panorama":
            ek = engine_kwargs or {}
            if engine == "hugin":
                merged_img = self._merge_images_hugin(
                    image_paths,
                    output_path,
                    projection=ek.get("projection", 0),
                    linear_match=ek.get("linear_match", True),
                )
            elif engine == "overmix":
                merged_img = self._merge_images_overmix(
                    image_paths,
                    output_path,
                    aligner=ek.get("aligner", "Recursive"),
                    render_stat=ek.get("render_stat", "average"),
                )
            elif engine == "asp":
                merged_img = self.perfect_stitch(image_paths, output_path, **ek)
            else:
                merged_img = self._merge_images_opencv(
                    image_paths,
                    output_path,
                    stitcher_mode=ek.get("stitcher_mode", 0),
                    registration_resol=ek.get("registration_resol", 0.6),
                )
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


__all__ = ["ImageMerger", "MERGE_IMAGES_PREFIX", "MERGE_DIR_IMAGES_PREFIX"]

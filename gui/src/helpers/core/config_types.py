"""
gui/src/helpers/core/config_types.py
=====================================
TypedDict definitions for GUI worker configuration dicts (§5.5A).

These replace bare ``Dict[str, Any]`` annotations on worker ``__init__``
parameters.  Call-sites can construct configs as plain dicts — TypedDicts are
structurally compatible.  Mypy enforces correct key names and types at call
sites when ``--strict`` is enabled per-module.

Usage
-----
::

    from gui.src.helpers.core.config_types import ConversionConfig

    config: ConversionConfig = {
        "output_format": "png",
        "files_to_convert": ["/path/img.webp"],
        "delete_original": False,
    }
    worker = ConversionWorker(config)
"""

from __future__ import annotations

from typing import List, Optional

from typing_extensions import TypedDict


class ConversionConfig(TypedDict, total=False):
    """Configuration dict for :class:`ConversionWorker`."""

    output_format: str
    files_to_convert: List[str]
    input_path: str
    input_formats: List[str]
    output_path: str
    output_filename_prefix: str
    delete_original: bool
    use_multicore: bool
    aspect_ratio: Optional[str]
    aspect_ratio_mode: str
    aspect_ratio_w: Optional[int]
    aspect_ratio_h: Optional[int]


class DeletionConfig(TypedDict, total=False):
    """Configuration dict for :class:`DeletionWorker`."""

    target_path: str
    require_confirm: bool
    target_extensions: List[str]


class MergeConfig(TypedDict, total=False):
    """Configuration dict for :class:`MergeWorker`."""

    output_path: str
    direction: str
    input_path: List[str]
    spacing: int
    align_mode: str
    grid_size: Optional[tuple]
    input_formats: List[str]


class StitchConfig(TypedDict, total=False):
    """Pipeline configuration dict passed to :class:`StitchWorker`.

    Mirrors the ``pipeline_config`` dict consumed by
    :meth:`AnimeStitchPipeline.run`.
    """

    save_intermediate: bool
    use_bg_masks: bool
    use_basic: bool
    use_birefnet: bool
    use_dinov2: bool
    hold_threshold: float
    sp_soft_px: int
    poisson_seam: bool
    tooncrafter_seam: bool
    multiscale_gain: bool
    histogram_match: bool
    mfsr_n_dct_iter: int
    mfsr_use_prior: bool
    mfsr_use_diffusion: bool


__all__ = [
    "ConversionConfig",
    "DeletionConfig",
    "MergeConfig",
    "StitchConfig",
]

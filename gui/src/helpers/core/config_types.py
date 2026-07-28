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


class SamplerConfig(TypedDict, total=False):
    """Configuration dict for :class:`SamplerWorker`."""

    files_to_process: List[str]
    use_multicore: bool
    scale_mode: str
    scale_factor: float
    target_width: Optional[int]
    target_height: Optional[int]
    preserve_aspect_ratio: bool
    algorithm: str
    output_format: Optional[str]
    output_path: Optional[str]
    output_filename_prefix: Optional[str]
    delete_original: bool


class CodecConversionConfig(TypedDict, total=False):
    """Configuration dict for :class:`CodecConversionWorker`."""

    files_to_convert: List[str]
    use_multicore: bool
    video_codec: Optional[str]
    audio_codec: Optional[str]
    crf: int
    speed: int
    output_path: str
    output_filename_prefix: str
    delete_original: bool


class ExtractionConfig(TypedDict, total=False):
    """Configuration dict for a single queued item consumed by
    ``run_extraction_in_process`` / :class:`QueueExecutionWorker`
    (``gui/src/helpers/core/queue_execution_worker.py``)."""

    type: str  # "range" | "single" | "gif" | "video"
    video_path: str
    start_ms: int
    end_ms: int
    output_dir: str
    target_resolution: Optional[tuple]
    cuts_ms: List[tuple]
    frame_interval: int
    smart_extract: bool
    smart_method: str
    fps: float
    mute_audio: bool
    use_ffmpeg: bool
    speed: float


__all__ = [
    "ConversionConfig",
    "DeletionConfig",
    "MergeConfig",
    "StitchConfig",
    "SamplerConfig",
    "CodecConversionConfig",
    "ExtractionConfig",
]

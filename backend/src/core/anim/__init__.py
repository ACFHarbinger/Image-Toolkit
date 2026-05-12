"""
anim — anime panorama stitching package.

Top-level orchestrator :class:`AnimeStitchPipeline` lives in ``pipeline.py`` and
delegates each stage to a sibling module (utils, matching, photometric,
masking, ecc, rendering, compositing, canvas, bundle_adjust).  The ``mfsr``
sub-package adds an optional Multi-Frame Super-Resolution post-processing pass.
"""

from .mfsr import de_seam, pso_register, run_mfsr
from .pipeline import AnimeStitchPipeline

__all__ = ["AnimeStitchPipeline", "run_mfsr", "pso_register", "de_seam"]

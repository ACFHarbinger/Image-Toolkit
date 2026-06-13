"""
anim — anime panorama stitching package.

Top-level orchestrator :class:`AnimeStitchPipeline` lives in ``pipeline.py`` and
delegates each stage to a sibling module (utils, matching, photometric,
masking, ecc, rendering, compositing, canvas, bundle_adjust).  The ``mfsr``
sub-package adds an optional Multi-Frame Super-Resolution post-processing pass.
"""

# §1.8A: auto-load asp_config.toml before any module-level env flags are read.
# Uses os.environ.setdefault → never overrides manually set env vars.
try:
    from .config import load_asp_config as _load_asp_config
    _load_asp_config()
except Exception:
    pass

from .mfsr import de_seam, pso_register, run_mfsr
from .pipeline import AnimeStitchPipeline

__all__ = ["AnimeStitchPipeline", "run_mfsr", "pso_register", "de_seam"]

"""AI model availability probes + lazy singleton loaders for ImageMerger.

Probes are checked at import time without importing the (heavy) libraries
themselves; the actual wrapper classes are only imported on first use via
the ``_get_*`` lazy loaders (§3.15A).
"""

from __future__ import annotations

import importlib.util as _importlib_util_merger

_BIREFNET_OK: bool = _importlib_util_merger.find_spec("transformers") is not None
_LOFTR_OK: bool = _importlib_util_merger.find_spec("kornia") is not None
try:
    from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper

    _BASIC_OK = True
except ImportError:
    _BASIC_OK = False

try:
    from backend.src.models.wrappers.gan_wrapper import GanWrapper as _GanWrapper_probe  # noqa: F401

    _GAN_OK = True
except ImportError:
    _GAN_OK = False

try:
    from backend.src.models.core.siamese_network import SiameseModelLoader as _Siamese_probe  # noqa: F401

    _SIAMESE_OK = True
except ImportError:
    _SIAMESE_OK = False


class _ModelCacheMixin:
    """Lazy-loaded, class-cached AI model wrapper instances."""

    # --- AI Model Caching (Lazy Loaders)
    _gan_inst = None
    _birefnet_inst = None
    _basic_inst = None
    _loftr_inst = None
    _siamese_inst = None

    @classmethod
    def _get_gan(cls):
        if cls._gan_inst is None:
            from backend.src.models.wrappers.gan_wrapper import GanWrapper  # §3.15A lazy

            cls._gan_inst = GanWrapper()
        return cls._gan_inst

    @classmethod
    def _get_birefnet(cls):
        if cls._birefnet_inst is None:
            from backend.src.models.wrappers.birefnet_wrapper import (
                BiRefNetWrapper,
            )  # §3.15A lazy

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
            from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper  # §3.15A lazy

            cls._loftr_inst = LoFTRWrapper()
        return cls._loftr_inst

    @classmethod
    def _get_siamese(cls):
        if cls._siamese_inst is None:
            from backend.src.models.core.siamese_network import (
                SiameseModelLoader,
            )  # §3.15A lazy

            cls._siamese_inst = SiameseModelLoader()
        return cls._siamese_inst


__all__ = [
    "_ModelCacheMixin",
    "_BIREFNET_OK",
    "_LOFTR_OK",
    "_BASIC_OK",
    "_GAN_OK",
    "_SIAMESE_OK",
]

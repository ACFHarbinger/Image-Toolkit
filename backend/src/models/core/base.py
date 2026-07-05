"""
backend/src/models/base.py
==========================
Abstract base class and shared utilities for all model wrappers.

Classes
-------
ModelWrapper
    ABC for every PyTorch model wrapper.  Standardises lifecycle (load /
    unload / is_available / loaded) so the pipeline and GUI can manage
    wrappers uniformly.

ModelRegistry
    Global singleton that tracks every live ModelWrapper via weak references.
    Call ``ModelRegistry.unload_all()`` to bulk-release VRAM between pipeline
    runs or when the user switches tabs.

Functions
---------
lazy_load
    Method decorator: calls ``self.load()`` on first invocation when the
    model is not yet loaded.  Apply to public entry-points (``match``,
    ``get_mask``, ``fit``, …) to make load-on-demand transparent to callers.
"""

from __future__ import annotations

import functools
import gc
import logging
import weakref
from abc import abstractmethod
from typing import Callable, List, Optional, TypeVar

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable)


def lazy_load(method: _F) -> _F:
    """Decorator: transparently calls ``self.load()`` if ``self.loaded`` is False."""
    @functools.wraps(method)
    def _wrapper(self: "ModelWrapper", *args, **kwargs):
        if not self.loaded:
            self.load()
        return method(self, *args, **kwargs)
    return _wrapper  # type: ignore[return-value]


class ModelWrapper:
    """
    Abstract base class for PyTorch model wrappers.

    Parameters
    ----------
    device : str, optional
        ``"cuda"`` or ``"cpu"``.  Auto-detected when omitted.

    Subclass contract
    -----------------
    * **Must** implement ``load()``.
    * Should override ``unload()`` to delete wrapper-specific state, then call
      ``super().unload()`` to handle the CUDA cache and GC.
    * Override ``loaded`` when the model lives in an attribute other than
      ``self._model`` (e.g. ``self.matcher``, class-level dict).
    * Override ``is_available()`` when the wrapper requires an optional
      third-party dependency.
    """

    def __init__(self, device: Optional[str] = None) -> None:
        import torch
        self.device: str = device or ("cuda" if torch.cuda.is_available() else "cpu")
        ModelRegistry.register(self)

    @abstractmethod
    def load(self) -> None:
        """Instantiate the model and move it to ``self.device``."""

    def unload(self) -> None:
        """
        Release VRAM / RAM.

        The default implementation flushes the CUDA cache and triggers GC.
        Subclasses should delete all model-specific state first, then call
        ``super().unload()``.
        """
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    @classmethod
    def is_available(cls) -> bool:
        """Return ``False`` when an optional dependency for this wrapper is missing."""
        return True

    @property
    def loaded(self) -> bool:
        """``True`` when the model is resident in memory.

        The default checks ``self._model``.  Override when the model lives in a
        different attribute (e.g. ``self.matcher``, a class-level dict).
        """
        return getattr(self, "_model", None) is not None


class ModelRegistry:
    """
    Global registry of ModelWrapper instances (weak-reference tracking).

    Wrappers auto-register in ``ModelWrapper.__init__``.  Dead wrappers are
    pruned on the next ``unload_all()`` call.
    """

    _refs: List[weakref.ref] = []

    @classmethod
    def register(cls, wrapper: ModelWrapper) -> None:
        cls._refs.append(weakref.ref(wrapper))

    @classmethod
    def unload_all(cls) -> None:
        """Unload every live wrapper that currently has a model loaded."""
        live: List[weakref.ref] = []
        for ref in cls._refs:
            w = ref()
            if w is not None:
                live.append(ref)
                if w.loaded:
                    w.unload()
        cls._refs = live

    @classmethod
    def loaded_count(cls) -> int:
        """Return the number of wrappers that currently have a model in memory."""
        return sum(
            1 for ref in cls._refs
            if (w := ref()) is not None and w.loaded
        )

    @classmethod
    def clear(cls) -> None:
        """Remove all registry entries (mainly useful in tests)."""
        cls._refs = []

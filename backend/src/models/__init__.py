# §3.14 — wrapper classes are NOT eagerly imported here.
# All callers use the full module path (e.g. from backend.src.models.wrappers.birefnet_wrapper import ...)
# so there is no need to re-export them from this package __init__.  Eager imports
# of aliked_lg_wrapper, birefnet_wrapper, etc. pulled in torchvision + transformers
# at pytest collection time, causing the test-suite freeze.
from .core.base import ModelRegistry, ModelWrapper, lazy_load

__all__ = [
    "ModelWrapper",
    "ModelRegistry",
    "lazy_load",
]

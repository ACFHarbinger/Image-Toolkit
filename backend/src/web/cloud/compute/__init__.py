"""Deprecated alias for :mod:`backend.src.cloud.poc` (moved 2026-10-19, #825).

Kept for one release. Submodules are aliased in ``sys.modules`` (not
re-exported) so ``patch("backend.src.web.cloud.compute.<mod>.<name>")``
still patches the object the code actually uses.
"""

from __future__ import annotations

import importlib
import sys
import warnings

from backend.src.cloud.poc import *  # noqa: F401,F403
from backend.src.cloud.poc import __all__  # noqa: F401

_SUBMODULES = (
    "cloud_job", "dispatcher", "gcd_adapter", "gcs_client",
    "provider_adapter", "usage", "usage_store",
)
for _name in _SUBMODULES:
    sys.modules[f"{__name__}.{_name}"] = importlib.import_module(f"backend.src.cloud.poc.{_name}")

warnings.warn(
    "backend.src.web.cloud.compute moved to backend.src.cloud.poc; the old path is removed next release.",
    DeprecationWarning,
    stacklevel=2,
)

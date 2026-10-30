"""Algorithm registry. Backends register themselves when their module is imported.

Add a file under ``classical/``, ``neural/``, or ``downscale/``. Do not edit this
module to add an algorithm. An empty ``supports_scale`` means any positive scale.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from middleware.src.services.media.gif_upscale.base import (
    AlgorithmError,
    AlgorithmSpec,
    RegisteredAlgorithm,
    UpscaleFn,
)

_ALGORITHMS: dict[str, RegisteredAlgorithm] = {}
_LOADED = False
_PACKAGES = (
    "middleware.src.services.media.gif_upscale.classical",
    "middleware.src.services.media.gif_upscale.neural",
    "middleware.src.services.media.gif_upscale.downscale",
)


def register_algorithm(spec: AlgorithmSpec, upscale: UpscaleFn) -> None:
    if not spec.id or spec.id != spec.id.strip().lower():
        raise ValueError(f"algorithm id must be a lowercase token, got {spec.id!r}")
    existing = _ALGORITHMS.get(spec.id)
    if existing is not None and existing.upscale is not upscale:
        raise ValueError(f"duplicate algorithm id {spec.id}")
    _ALGORITHMS[spec.id] = RegisteredAlgorithm(spec, upscale)


def load_backends() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    for package_name in _PACKAGES:
        package = importlib.import_module(package_name)
        for info in pkgutil.iter_modules(package.__path__):
            if info.name.startswith("_"):
                continue
            importlib.import_module(f"{package_name}.{info.name}")


def get_algorithm(algorithm_id: str) -> RegisteredAlgorithm:
    load_backends()
    key = str(algorithm_id or "").strip().lower()
    found = _ALGORITHMS.get(key)
    if found is None:
        known = ", ".join(sorted(_ALGORITHMS)) or "(none)"
        raise AlgorithmError(f"Unknown resample algorithm {algorithm_id!r}. Known algorithms: {known}.")
    return found


def list_algorithms() -> list[dict[str, Any]]:
    load_backends()
    rows: list[dict[str, Any]] = []
    for registered in _ALGORITHMS.values():
        spec = registered.spec
        try:
            available, reason = spec.available()
        except Exception as exc:  # a broken probe must not hide the row
            available, reason = False, str(exc)
        rows.append(
            {
                "id": spec.id,
                "family": spec.family,
                "content": spec.content,
                "kind": spec.kind,
                "supports_scale": sorted(spec.supports_scale),
                "supports_downscale": spec.supports_downscale,
                "needs_gpu": spec.needs_gpu,
                "vram_mb_estimate": spec.vram_mb_estimate,
                "license": spec.license,
                "weights_sha256": spec.weights_sha256,
                "available": bool(available),
                "reason": "" if available else (reason or f"{spec.id} is unavailable."),
                "containers": list(spec.containers),
            }
        )
    return sorted(rows, key=lambda row: row["id"])

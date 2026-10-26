"""Cel-Shaded-Generator core exports after the flattened source layout.

Public names load on first attribute access so importing this package does
not pull cv2 or numpy (#1036). The export set matches the old eager
``logic/src/__init__.py``.
"""

from __future__ import annotations

import importlib
from typing import Any

# (module, attribute). Imported only when the name is used.
_EXPORTS: dict[str, tuple[str, str]] = {
    "colorize_scribble": (
        "middleware.src.csg.colorization.colorization",
        "colorize_scribble",
    ),
    "graph_cut_temporal_refine": (
        "middleware.src.csg.colorization.graph_cut",
        "graph_cut_temporal_refine",
    ),
    "colorize_reference": (
        "middleware.src.csg.colorization.optimal_transport",
        "colorize_reference",
    ),
    "sinkhorn": ("middleware.src.csg.colorization.optimal_transport", "sinkhorn"),
    "colorize_scribble_screentone": (
        "middleware.src.csg.colorization.screentone",
        "colorize_scribble_screentone",
    ),
    "IsolatedRunner": ("middleware.src.csg.execution", "IsolatedRunner"),
    "JobCancelled": ("middleware.src.csg.execution", "JobCancelled"),
    "JobRequest": ("middleware.src.csg.execution", "JobRequest"),
    "JobTimedOut": ("middleware.src.csg.execution", "JobTimedOut"),
    "Operation": ("middleware.src.csg.execution", "Operation"),
    "PersistentIsolatedRunner": ("middleware.src.csg.execution", "PersistentIsolatedRunner"),
    "WorkerCrashed": ("middleware.src.csg.execution", "WorkerCrashed"),
    "gabor_feature_bank": ("middleware.src.csg.features.gabor", "gabor_feature_bank"),
    "log_preference": ("middleware.src.csg.features.preference_log", "log_preference"),
    "read_preferences": ("middleware.src.csg.features.preference_log", "read_preferences"),
    "arap_deform": ("middleware.src.csg.rigging.arap", "arap_deform"),
    "generate_mesh": ("middleware.src.csg.rigging.arap", "generate_mesh"),
    "build_quadtree": ("middleware.src.csg.temporal.quadtree", "build_quadtree"),
    "colorize_region_incremental": (
        "middleware.src.csg.temporal.quadtree",
        "colorize_region_incremental",
    ),
    "colorize_scribble_sequence": (
        "middleware.src.csg.temporal.temporal",
        "colorize_scribble_sequence",
    ),
}

__all__ = [
    "colorize_scribble",
    "colorize_scribble_screentone",
    "colorize_reference",
    "colorize_scribble_sequence",
    "gabor_feature_bank",
    "sinkhorn",
    "graph_cut_temporal_refine",
    "log_preference",
    "read_preferences",
    "build_quadtree",
    "colorize_region_incremental",
    "generate_mesh",
    "arap_deform",
    "IsolatedRunner",
    "JobCancelled",
    "JobRequest",
    "JobTimedOut",
    "Operation",
    "PersistentIsolatedRunner",
    "WorkerCrashed",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    value = getattr(importlib.import_module(module_name), attr)
    globals()[name] = value
    return value

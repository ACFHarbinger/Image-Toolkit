"""ASP coherence evaluation dashboard — component package.

``backend/controllers/bench_eval_dispatch.py`` is the public entry point /
CLI; everything in this package is an implementation detail it assembles,
split by role:

- ``ui/``    — PySide6 widgets/windows (presentation only).
- ``logic/`` — pixel-data computation (histograms, heatmaps, diff maps, etc).
- ``other/`` — shared data models and dataset discovery, used by both.
"""

from .other.schema import BoundingBox, Edge, EdgePoint, RatingEntry, load_evaluations, save_evaluations
from .ui.main_window import RatingDashboard

__all__ = [
    "RatingDashboard",
    "RatingEntry",
    "BoundingBox",
    "Edge",
    "EdgePoint",
    "load_evaluations",
    "save_evaluations",
]

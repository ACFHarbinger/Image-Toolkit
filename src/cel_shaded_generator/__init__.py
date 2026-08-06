"""cel_shaded_generator — Manga Colorization & Animation: HITL deep learning + mathematical
optimization for scribble-based colorization, temporal propagation, and ARAP
mesh puppeteering.
"""

from .colorization.colorization import colorize_scribble as colorize_scribble
from .colorization.graph_cut import graph_cut_temporal_refine as graph_cut_temporal_refine
from .colorization.optimal_transport import colorize_reference as colorize_reference
from .colorization.optimal_transport import sinkhorn as sinkhorn
from .colorization.screentone import (
    colorize_scribble_screentone as colorize_scribble_screentone,
)
from .features.gabor import gabor_feature_bank as gabor_feature_bank
from .features.preference_log import log_preference as log_preference
from .features.preference_log import read_preferences as read_preferences
from .execution import (
    IsolatedRunner as IsolatedRunner,
    JobCancelled as JobCancelled,
    JobRequest as JobRequest,
    JobTimedOut as JobTimedOut,
    Operation as Operation,
    WorkerCrashed as WorkerCrashed,
)
from .rigging.arap import arap_deform as arap_deform
from .rigging.arap import generate_mesh as generate_mesh
from .temporal.quadtree import build_quadtree as build_quadtree
from .temporal.quadtree import (
    colorize_region_incremental as colorize_region_incremental,
)
from .temporal.temporal import colorize_scribble_sequence as colorize_scribble_sequence

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
    "WorkerCrashed",
]

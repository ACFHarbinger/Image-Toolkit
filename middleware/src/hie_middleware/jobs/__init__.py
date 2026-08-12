"""HIE Middleware Jobs: cancellable optimization job contract + exact/metaheuristic solvers.

See `README.md` in this directory for the package plan, and `base.py` for the
`Job`/`CancelToken`/`JobHandle` contract every solver wrapper here builds on.
"""

from .base import CancelToken, JobCancelled, JobHandle, JobProgress, JobResult, JobStatus, submit_job
from .exact_dp import (
    AlignmentResult,
    ColorHarmonizationResult,
    Correspondence,
    LayerColorStats,
    MotionModel2DTS,
    SeamPixel,
    SeamResult,
    call_hie_alignment_gnc,
    call_hie_exact_solver,
)
from .metaheuristics import call_hie_de, call_hie_pso

__all__ = [
    "AlignmentResult",
    "CancelToken",
    "ColorHarmonizationResult",
    "Correspondence",
    "JobCancelled",
    "JobHandle",
    "JobProgress",
    "JobResult",
    "JobStatus",
    "LayerColorStats",
    "MotionModel2DTS",
    "SeamPixel",
    "SeamResult",
    "call_hie_alignment_gnc",
    "call_hie_exact_solver",
    "call_hie_de",
    "call_hie_pso",
    "submit_job",
]

"""HIE Middleware Jobs: cancellable optimization job contract + exact/metaheuristic solvers.

See `README.md` in this directory for the package plan, and `base.py` for the
`Job`/`CancelToken`/`JobHandle` contract every solver wrapper here builds on.
"""

from .base import CancelToken, JobCancelled, JobHandle, JobProgress, JobResult, JobStatus, submit_job
from .exact_dp import (
    ColorHarmonizationResult,
    LayerColorStats,
    SeamPixel,
    SeamResult,
    call_hie_exact_solver,
)
from .metaheuristics import call_hie_de, call_hie_pso

__all__ = [
    "CancelToken",
    "ColorHarmonizationResult",
    "JobCancelled",
    "JobHandle",
    "JobProgress",
    "JobResult",
    "JobStatus",
    "LayerColorStats",
    "SeamPixel",
    "SeamResult",
    "call_hie_exact_solver",
    "call_hie_de",
    "call_hie_pso",
    "submit_job",
]

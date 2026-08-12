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
from .restoration import RestorationResult, submit_restoration_job
from .restoration_report import generate_restoration_report
from .cpu_restoration import (
    cpu_deblur_preview,
    cpu_deblur_runner,
    cpu_masked_inpainting_runner,
    cpu_sharpen_preview,
    opencv_deblur_runner,
    opencv_masked_inpainting_runner,
    validate_inpainting_mask,
)

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
    "RestorationResult",
    "cpu_deblur_preview",
    "cpu_deblur_runner",
    "cpu_masked_inpainting_runner",
    "cpu_sharpen_preview",
    "opencv_deblur_runner",
    "opencv_masked_inpainting_runner",
    "validate_inpainting_mask",
    "generate_restoration_report",
    "call_hie_alignment_gnc",
    "call_hie_exact_solver",
    "call_hie_de",
    "call_hie_pso",
    "submit_restoration_job",
    "submit_job",
]

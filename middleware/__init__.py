"""HIE Middleware: Python Orchestration & Middleware Layer for HIE.

Subpackages:
- hie_middleware.models / middleware.models: ML & DL Neural Nets (BiRefNet, Real-ESRGAN, Inpainting)
- hie_middleware.policies / middleware.policies: RL Policies (Brush assistant, tone retouching, crop optimizer)
- hie_middleware.jobs / middleware.jobs: Optimization methods (Exact DP, PSO, Differential Evolution)
- hie_middleware.pipeline / middleware.pipeline: Processing pipeline orchestrator
- hie_middleware.logic_bridge / middleware.logic_bridge: C++ pybind11 wrappers
"""

from .contracts import EditRequest, OperationResult

__all__ = ["EditRequest", "OperationResult"]

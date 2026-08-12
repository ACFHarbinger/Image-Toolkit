# HIE Middleware Pipeline (`middleware/pipeline/`)

The `pipeline` package provides the central execution pipeline orchestrating deep learning models (`models/`), reinforcement learning policies (`policies/`), numerical optimization jobs (`jobs/`), and the C++ DAG render graph (`logic_bridge/`).

## Responsibilities

- **Pipeline Orchestration (`pipeline/orchestrator.py`):** Schedules multi-stage execution graphs combining raw image pre-processing, neural matting, optimization parameter tuning, and composite rendering.
- **Frame Sequence Processing (`pipeline/sequence.py`):** Handles multi-frame video sequence evaluation, temporal keyframe propagation, and batch processing.
- **Resource & Memory Management:** Manages GPU/VRAM allocations between PyTorch/ONNX inference and C++ render graph memory buffers.
- **Progress & State Tracking:** Emits granular progress telemetry and supports operation cancellation for frontends (`gui/` and `frontend/`).

## Current boundary

`ProposalPipeline` in `orchestrator.py` registers model adapters and RL
policies, exposes capabilities, and returns serializable preview proposals.
It intentionally does not mutate documents. A future acceptance/history
service will apply an explicitly accepted proposal and connect long-running
optimization jobs through the same frontend contract.

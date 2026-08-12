# HIE Middleware Layer (`submodules/HIE/middleware/`)

The **middleware layer** serves as the Python orchestration boundary connecting the high-performance C++ logic core (`logic/`) to state-of-the-art Machine Learning (ML/DL) models, Reinforcement Learning (RL) policies, mathematical optimization solvers, and dual frontends (**PySide6** `gui/` & **Tauri** `frontend/`).

## Architecture & Submodules Layout

The middleware is structured into five core submodules:

- **`middleware/models/` — Machine Learning & Deep Learning Neural Nets:**
  - **BiRefNet & FastSAM:** Neural sub-pixel alpha matting and trimap extraction.
  - **Real-ESRGAN:** AI super-resolution and spatial upscaling nodes.
  - **Generative Inpainting:** Stroke-guided and prompt-driven generative fill & boundary outpainting.

- **`middleware/policies/` — Reinforcement Learning Policies:**
  - **Interactive Brush Assistant (`policies/brush_assistant.py`):** RL agent trained via Gymnasium to assist with localized dodging, burning, and tone adjustment.
  - **Global Tone Agent (`policies/tone_agent.py`):** RL policy for dynamic range balancing and automated color grading.
  - **Crop & Composition Agent (`policies/crop_agent.py`):** Reinforcement learning policy for auto-cropping and visual weight maximization.

- **`middleware/jobs/` — Mathematical & Swarm Optimization Methods:**
  - **Exact DP Solvers (`jobs/exact_dp.py`):** Seam routing with character exclusion barriers, GNC-TLS alignment, and convex color harmonization.
  - **Metaheuristic Solvers (`jobs/metaheuristics.py`):** Particle Swarm Optimization (PSO) for multi-parameter filter tuning and Differential Evolution (DE) for composition layout optimization.

- **`middleware/pipeline/` — Processing Pipeline Orchestrator:**
  - **Pipeline Execution (`pipeline/orchestrator.py`):** Orchestrates multi-stage processing graphs combining models, RL policies, optimization jobs, and C++ DAG render graph evaluations.
  - **Sequence Processing (`pipeline/sequence.py`):** Multi-frame video clip sequence evaluation and temporal keyframe propagation.

- **`middleware/logic_bridge/` — C++ pybind11 & C-ABI Wrappers:**
  - Zero-copy tensor/array memory sharing between Python (NumPy / PyTorch) and native C++ DAG evaluators/solvers in `logic/`.

## Shared Contracts

- `middleware/src/hie_middleware/contracts.py`: Defines serializable edit requests (`EditRequest`) and execution results (`OperationResult`).
- `middleware/src/hie_middleware/ipc.py`: Defines versioned frontend/host envelopes (`IpcRequest`, `IpcResponse`) for `open_media`, `export_document`, and `notify`.
- `middleware/src/hie_middleware/ipc_service.py`: Provides a deterministic in-memory implementation of those initial methods for hosts and integration tests, including still and multi-frame media sequences.
- `middleware/src/hie_middleware/pipeline/session.py`: Combines an active `DocumentHistory`, default capabilities, proposal preview, and explicit acceptance for one editor session.
- `middleware/src/hie_middleware/jobs/restoration.py`: Runs injected deblur/inpainting backends through cancellable `JobHandle`s without bundling model runtimes.
- `middleware/src/hie_middleware/jobs/cpu_restoration.py`: Optional Pillow CPU baselines for local previews while neural/OpenCV runtimes are unavailable.

Install the OpenCV backend with:

```bash
python3 -m pip install -e '.[restoration-opencv]'
```

Use `opencv_masked_inpainting_runner` through `submit_restoration_job` after
the required mask and permission confirmation have been supplied.

## CLI

Install the middleware with UV and run the local baselines directly:

```bash
uv sync --extra restoration-opencv
uv run hie-restore deblur input.png --output restored.png
uv run hie-restore inpaint owned.png --mask logo-mask.png \
  --permission-confirmed --output cleaned.png
```

`inpaint` defaults to OpenCV when installed and otherwise uses the Pillow
baseline. The original file is never overwritten unless an explicit output
path points to it.

## Weight & Dependency Management

Model weights, checkpoints, and heavy dataset dependencies remain outside Git tracking. Document retrieval scripts, checksums, and remote URLs under `docs/`.

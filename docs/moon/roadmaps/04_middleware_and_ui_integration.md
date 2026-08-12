# Roadmap 04: Middleware & Dual UI Integration

## Executive Summary
This roadmap specifies the middleware bridge (`middleware/`) connecting the C++ logic core (`logic/`) to Python models, policies, optimization jobs, and pipelines, as well as the dual frontends (`gui/` and `frontend/`).

---

## Technical Specifications

### 1. Middleware Boundaries (`middleware/`)
- **Models:** Versioned neural-network/model adapters under `middleware/models/`.
- **Policies:** Inspectable RL policies under `middleware/policies/`.
- **Jobs:** Cancellable exact and heuristic optimization work under `middleware/jobs/`.
- **Pipeline:** End-to-end orchestration under `middleware/pipeline/`.
- **Binding:** Integration with Image-Toolkit's central `base` pybind11 module, following ASP conventions.

### 2. PySide6 Desktop GUI (`gui/`) — Primary Phase 1 Target
- **Integration Mode:** Embedded as a dedicated tab (`gui/hie_tab.py`) inside Image-Toolkit's desktop application (`python backend/main.py`), and executable standalone via `python -m hie.gui.main`.
- **Canvas Viewport:** `QGraphicsView` / `QOpenGLWidget` viewport with real-time hardware acceleration, zoom/pan navigation, and brush stroke overlay.
- **Threaded Worker Architecture:** `QThread` workers communicating off the Qt event loop via Signals & Slots to trigger C++ optimization solvers and PyTorch inference.

### 3. Tauri Web UI (`frontend/`)
- **Integration Mode:** Embedded as a tab in Image-Toolkit's React/Tauri web app, and executable standalone (`npm run tauri dev`).
- **Middleware API Bridge:** Consumes the exact same Python middleware bridge via HTTP/REST or IPC socket.

---

## Delivery Phases & Deliverables

| Phase | Milestone | Priority | Output Deliverables |
|---|---|:---:|---|
| **Phase 4.1** | Central `base` pybind11 HIE Logic Bridge | High | `middleware/logic_bridge/` and Image-Toolkit `base` integration |
| **Phase 4.2** | Models, Policies, Jobs, and Pipeline Service Contract | High | `middleware/{models,policies,jobs,pipeline}/` |
| **Phase 4.3** | PySide6 HIE Tab Component (`gui/hie_tab.py`) | High | `gui/src/hie_tab.py` integrated into `Image-Toolkit/gui/`. Includes an "Open Image…" toolbar action (`HieTab.open_image`/`load_image_path`) that loads a file into `HieViewport` and starts a fresh document history, plus a grouped toolbar/status/sidebar layout (2026-08-12). |
| **Phase 4.4** | PySide6 Standalone Runner | High | `gui/main.py` entry point |
| **Phase 4.5** | Tauri Frontend Integration | Med | `frontend/src/main.ts`, `frontend/src/style.css` |
| **Phase 4.6** | Host Pipeline IPC Contract | High | Versioned `list_capabilities`, `preview_policy`, `accept_proposal`, and `submit_restoration` methods backed by `PipelineSession` |
| **Phase 4.7** | Submodule UI Ownership | High | HIE-owned PySide6 and React/Tauri editor tabs with thin Image-Toolkit re-exports |
| **Phase 4.8** | Flat Source Layout | Med | Stable `middleware/src/*` and `gui/src/*` package paths, updated entry points, imports, tests, and packaging metadata |

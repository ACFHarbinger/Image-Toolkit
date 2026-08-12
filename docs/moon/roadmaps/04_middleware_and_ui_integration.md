# Roadmap 04: Middleware & Dual UI Integration

> **Status:** Foundation ✅ · Host ownership / pipeline IPC 🔄 (2026-08-12)  
> **GitHub:** [HIE #8](https://github.com/ACFHarbinger/Hybrid-Image-Editor/issues/8) · parent [Image-Toolkit #363](https://github.com/ACFHarbinger/Image-Toolkit/issues/363) (Track 04 foundation closed; follow-ups on #8)

## Executive Summary

This roadmap specifies the middleware bridge (`middleware/`) connecting the C++ logic core (`logic/`) to Python models, policies, optimization jobs, and pipelines, as well as the dual frontends (`gui/` and `frontend/`). Image-Toolkit embeds HIE UIs by **re-exporting** submodule packages; editor features land here first.

---

## Technical Specifications

### 1. Middleware Boundaries (`middleware/`)

- **Models:** Versioned neural-network/model adapters under `middleware/models/` (flat `middleware/src/*` layout).
- **Policies:** Inspectable RL policies under `middleware/policies/`.
- **Jobs:** Cancellable exact and heuristic optimization work under `middleware/jobs/`.
- **Pipeline:** End-to-end orchestration under `middleware/pipeline/` (`ProposalPipeline`, `PipelineSession`, `RestorationPipeline`).
- **IPC:** Versioned envelopes in `ipc.py` / `ipc_service.py` shared by PySide6 and Tauri hosts.
- **Binding:** Integration with Image-Toolkit's central `base` pybind11 module, following ASP conventions.

### 2. PySide6 Desktop GUI (`gui/`) — Primary Phase 1 Target

- **Source of truth:** HIE `gui/` (`HieTab`, `HieEditorTab`, `HieViewport`).
- **Integration Mode:** Image-Toolkit `gui/src/tabs/editor/` **re-exports** `HieEditorTab`; standalone via `hie-gui` / `python -m hie_gui.main` (or flat `main` after package flatten).
- **Session:** Desktop tab owns a `PipelineSession` (proposals + restoration capability list + queue action).
- **Canvas Viewport:** `QGraphicsView` viewport with pan/zoom and image load.
- **Threading:** Long-running jobs use middleware `JobHandle` cancellation; UI must not block the Qt event loop.

### 3. Tauri / React Web UI (`frontend/`)

- **Source of truth:** HIE `frontend/` standalone shell + `frontend/src/embed/react/HieEditorTab.tsx` for Image-Toolkit.
- **Integration Mode:** Image-Toolkit depends on `hie-frontend` (`file:../submodules/HIE/frontend`) and re-exports the React tab.
- **Host seam:** `HieHost` (`openMedia`, `exportDocument`, `notify`, optional capability/proposal methods).

---

## Delivery Phases & Deliverables

| Phase | Milestone | Priority | Status | Output Deliverables |
|---|---|:---:|:---:|---|
| **Phase 4.1** | Central `base` pybind11 HIE Logic Bridge | High | ✅ | `middleware/logic_bridge/` and Image-Toolkit `base` integration |
| **Phase 4.2** | Models, Policies, Jobs, and Pipeline Service Contract | High | ✅ | `middleware/{models,policies,jobs,pipeline}/` + `PipelineSession` |
| **Phase 4.3** | PySide6 HIE Tab Component | High | ✅ | Embeddable `HieTab` / `HieEditorTab`; Open Image; toolbar/status/sidebar; parent re-export |
| **Phase 4.4** | PySide6 Standalone Runner | High | ✅ | `hie-gui` / standalone `main` entry; optional `--image PATH` |
| **Phase 4.5** | Tauri / React Frontend Integration | Med | ✅ shell · ✅ embed package | Standalone Vite/Tauri shell; React embed under `frontend/src/embed/react/`; Image-Toolkit re-export via `hie-frontend` |
| **Phase 4.6** | Host pipeline IPC expansion | High | 🔄 | IPC: `list_capabilities`, `preview_policy`, `accept_proposal`, `submit_restoration`; desktop `PipelineSession` wiring ✅; Tauri Rust commands for new methods pending |
| **Phase 4.7** | Submodule UI ownership | High | ✅ | HIE-owned PySide6 + React editor tabs; thin Image-Toolkit re-exports only |
| **Phase 4.8** | Flat source layout | Med | 🔄 Claude | Stable `middleware/src/*` and `gui/src/*` package paths, entry points, imports, tests, packaging metadata |
| **Phase 4.9** | Accessibility & host hardening | Med | ⬜ | Keyboard/a11y pass; job progress streaming to UIs |

### 2026-08-12 host-ownership slice (Grok)

- UI implementations consolidated into HIE; parent thin re-exports only (Image-Toolkit S377).
- `HieTab` uses `PipelineSession` + restoration capability discovery / queue.
- IPC service methods above implemented and unit-tested (flat middleware imports).
- Commits: HIE `ae052e8`, Image-Toolkit `a672ba46`.
- Tests: middleware 103 passed / 23 skipped; gui 5 passed.

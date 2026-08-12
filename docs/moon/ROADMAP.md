# Hybrid Image Editor (HIE) — Master Delivery Roadmap

> **Status:** ACTIVE DEVELOPMENT — Tracks 01–04 foundation complete; host pipeline/IPC & ownership hardening advanced (2026-08-12)  
> **Last Updated:** 2026-08-12 (Grok host-ownership session; parent S377; Claude package flatten concurrent)  
> **Repository:** `submodules/HIE` · GitHub: [Hybrid-Image-Editor](https://github.com/ACFHarbinger/Hybrid-Image-Editor)  
> **Lead Agents:** Gemini, Chat, Claude, Grok  
> **Tracking:** HIE issues [#5](https://github.com/ACFHarbinger/Hybrid-Image-Editor/issues/5)–[#8](https://github.com/ACFHarbinger/Hybrid-Image-Editor/issues/8); parent Image-Toolkit [#360](https://github.com/ACFHarbinger/Image-Toolkit/issues/360)–[#363](https://github.com/ACFHarbinger/Image-Toolkit/issues/363)

---

## 1. Project Overview & Mission

The **Hybrid Image Editor (HIE)** is a next-generation hybrid editing module that bridges **High-Performance C++ Mathematical Optimization** (Exact DP solvers, PSO, Differential Evolution) with **State-of-the-Art Machine Learning** (BiRefNet Alpha Matting, Real-ESRGAN, Inpainting) and **Reinforcement Learning Assistance** (Interactive Brush Assistant RL Policies).

Architected from Day 1 for multi-modal inputs (single images and multi-frame video clips), HIE supports dual frontends: a **PySide6 Desktop GUI (`gui/`)** (Primary Phase 1 target) and a **Tauri Web UI (`frontend/`)**. Image-Toolkit embeds both surfaces by **re-exporting** HIE packages rather than forking UI code.

---

## 2. Priority Matrix & Roadmap Tracks

| Track ID | Track Name | Roadmap Reference | Priority | Status |
|---|---|---|:---:|:---:|
| **TRACK 01** | Core Architecture & Multi-Modal Document Model | [`docs/moon/roadmaps/01_architecture_and_data_model.md`](roadmaps/01_architecture_and_data_model.md) | High | ✅ Completed |
| **TRACK 02** | Mathematical Optimization Core (`logic/` + `middleware/jobs/`) | [`docs/moon/roadmaps/02_mathematical_optimization_core.md`](roadmaps/02_mathematical_optimization_core.md) | High | ✅ Completed |
| **TRACK 03** | Deep Learning & RL Subsystem (`middleware/models/`, `middleware/policies/`, `middleware/jobs/`, `middleware/pipeline/`) | [`docs/moon/roadmaps/03_deep_learning_and_rl_subsystem.md`](roadmaps/03_deep_learning_and_rl_subsystem.md) | High | ✅ Foundation delivered; restoration/RL hardening continues |
| **TRACK 04** | Middleware Bridge & Dual UI Integration (`gui/` + `frontend/`) | [`docs/moon/roadmaps/04_middleware_and_ui_integration.md`](roadmaps/04_middleware_and_ui_integration.md) | High | ✅ Core delivered · 🔄 host IPC / ownership / flat layout ([HIE #8](https://github.com/ACFHarbinger/Hybrid-Image-Editor/issues/8)) |

---

## 3. Phased Sequence Summary

- **Phase 1 (Foundation):** Multi-modal frame sequence document model, C++ logic core refactoring, pybind11 root `base` binding integration, PySide6 `HieTab` viewport.
- **Phase 2 (Optimization & Matting):** Exact C++ DP seam routing & convex color harmonization, PSO filter autotuner, BiRefNet alpha matting, and optional deblur/inpainting restoration foundations.
- **Phase 3 (RL Co-Pilot & Advanced Features):** Interactive Brush RL Retouching Agent, Differential Evolution composition solver, Real-ESRGAN super-resolution, Tauri web UI integration.
- **Phase 4 (Host pipeline integration — active):** Image-Toolkit re-export ownership, `PipelineSession` in desktop UI, versioned IPC for capabilities/proposals/restoration; residual Tauri command wiring for new IPC methods, a11y pass, package-layout flatten (Claude).
- **Phase 5 (Video Editing Extension):** Temporal keyframe sequence propagation, SAM-2 tracking, video clip export. *(Earlier drafts labeled this “Phase 4 video.”)*

---

## 4. Active Integration Notes (2026-08-12)

### 4.1 UI ownership (Grok — parent S377 / HIE `ae052e8`)

| Surface | Source of truth | Image-Toolkit |
|---|---|---|
| PySide6 Hybrid Editor | HIE `gui/` (`HieTab`, `HieEditorTab`, `HieViewport`) | `gui/src/tabs/editor/` re-exports only |
| React Hybrid Editor | `frontend/src/embed/react/HieEditorTab.tsx` | `hie-frontend` file dep + `frontend/src/tabs/editor/` re-export |
| Standalone Vite/Tauri shell | `frontend/src/main.ts`, `host.ts` | N/A (submodule app) |

- **Do not** re-implement Hybrid Editor UI in the parent repo.
- Claude owns flattening redundant package dirs (`hie_middleware` → `middleware/src/*`, `hie_gui` → `gui/src/*`). Other agents must not reverse that work.

### 4.2 Pipeline / IPC contract (hosts)

Hosts integrate through:

1. **`PipelineSession`** — document history + proposal pipeline + restoration pipeline.
2. **Versioned IPC methods:** `open_media`, `export_document`, `notify`, `list_capabilities`, `preview_policy`, `accept_proposal`, `submit_restoration`.

Remaining under [HIE #8](https://github.com/ACFHarbinger/Hybrid-Image-Editor/issues/8): end-to-end Tauri Rust commands for the new IPC methods; accessibility/keyboard pass; optional native job progress streaming.

### 4.3 Verification snapshot (host-ownership land)

- Middleware: **103 passed, 23 skipped**
- GUI: **5 passed**
- Parent Image-Toolkit pointer: `a672ba46` → HIE `ae052e8`

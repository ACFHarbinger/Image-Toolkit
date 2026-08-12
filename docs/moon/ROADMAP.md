# Hybrid Image Editor (HIE) — Master Delivery Roadmap

> **Status:** ACTIVE DEVELOPMENT  
> **Last Updated:** 2026-08-12  
> **Repository:** `submodules/HIE`  
> **Lead Agents:** Gemini & Chat (Collaborating with Claude & Grok)

---

## 1. Project Overview & Mission

The **Hybrid Image Editor (HIE)** is a next-generation hybrid editing module that bridges **High-Performance C++ Mathematical Optimization** (Exact DP solvers, PSO, Differential Evolution) with **State-of-the-Art Machine Learning** (BiRefNet Alpha Matting, Real-ESRGAN, Inpainting) and **Reinforcement Learning Assistance** (Interactive Brush Assistant RL Policies).

Architected from Day 1 for multi-modal inputs (single images and multi-frame video clips), HIE supports dual frontends: a **PySide6 Desktop GUI (`gui/`)** (Primary Phase 1 target) and a **Tauri Web UI (`frontend/`)**.

---

## 2. Priority Matrix & Roadmap Tracks

| Track ID | Track Name | Roadmap Reference | Priority | Status |
|---|---|---|:---:|:---:|
| **TRACK 01** | Core Architecture & Multi-Modal Document Model | [`docs/moon/roadmaps/01_architecture_and_data_model.md`](roadmaps/01_architecture_and_data_model.md) | High | ✅ Completed |
| **TRACK 02** | Mathematical Optimization Core (`logic/` + `middleware/jobs/`) | [`docs/moon/roadmaps/02_mathematical_optimization_core.md`](roadmaps/02_mathematical_optimization_core.md) | High | ✅ Completed |
| **TRACK 03** | Deep Learning & RL Subsystem (`middleware/models/`, `middleware/policies/`, `middleware/jobs/`, `middleware/pipeline/`) | [`docs/moon/roadmaps/03_deep_learning_and_rl_subsystem.md`](roadmaps/03_deep_learning_and_rl_subsystem.md) | High | ✅ Completed |
| **TRACK 04** | Middleware Bridge & Dual UI Integration (`gui/` + `frontend/`) | [`docs/moon/roadmaps/04_middleware_and_ui_integration.md`](roadmaps/04_middleware_and_ui_integration.md) | High | ✅ Completed |

---

## 3. Phased Sequence Summary

- **Phase 1 (Foundation):** Multi-modal frame sequence document model, C++ logic core refactoring, pybind11 root `base` binding integration, PySide6 `gui/hie_tab.py` viewport.
- **Phase 2 (Optimization & Matting):** Exact C++ DP seam routing & convex color harmonization, PSO filter autotuner, BiRefNet alpha matting, and optional deblur/inpainting restoration foundations.
- **Phase 3 (RL Co-Pilot & Advanced Features):** Interactive Brush RL Retouching Agent, Differential Evolution composition solver, Real-ESRGAN super-resolution, Tauri web UI integration.
- **Phase 4 (Video Editing Extension):** Temporal keyframe sequence propagation, SAM-2 tracking, video clip export.

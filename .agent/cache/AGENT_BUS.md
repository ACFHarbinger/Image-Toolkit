# AGENT_BUS.md — Hybrid Image Editor (HIE) Multi-Agent Communication Bus

Welcome to the **Hybrid Image Editor (HIE)** agentic coordination hub. All agents (Gemini, Chat, Claude, Grok) working on `submodules/HIE` post updates, architectural proposals, roadmaps, and status reports here.

---

## Agent Directory & Workspace Structure
- **Global Coordination:** `submodules/HIE/.agent/cache/AGENT_BUS.md`
- **Gemini Cache:** `submodules/HIE/.agent/cache/gemini/`
- **Chat Cache:** `submodules/HIE/.agent/cache/chat/`
- **Claude Cache:** `submodules/HIE/.agent/cache/claude/`
- **Grok Cache:** `submodules/HIE/.agent/cache/grok/`

---

## Finalized Architectural Decisions (Confirmed by Harbinger)

1. **Canvas Architecture:** **Hybrid Stack** (combining layer-stack controls with non-destructive node modifiers).
2. **C++ Logic Binding Boundary:** **Root `base` Pybind11 Module** (compiled into Image-Toolkit's central `base` module like ASP to maintain repository standards and allow zero-copy memory sharing).
3. **Reinforcement Learning Sequence:** **Localized Retouching (Interactive Brush Assistant) $\rightarrow$ Global Color/Exposure Retouching $\rightarrow$ Crop & Composition Optimizer**.
4. **Optimization Solvers Focus:** **Parallel Execution** (Exact DP/Convex solvers + Swarm Intelligence [PSO] & Differential Evolution [DE]).
5. **Document Data Model:** **Multi-Modal Frame Sequence Model from Day 1** (`Sequence[Frame]`, image = 1-frame clip).
6. **UI Priority Target:** **PySide6 Desktop GUI (`gui/`) as Primary Phase 1 Target** (zero-IPC latency for PyTorch/C++ rendering) with clean middleware APIs for Tauri (`frontend/`).

---

## Finalized Roadmaps Directory Structure (`submodules/HIE/docs/moon/`)
- [`ROADMAP.md`](../../docs/moon/ROADMAP.md) — Master HIE Delivery Plan & Priority Matrix
- [`01_architecture_and_data_model.md`](../../docs/moon/roadmaps/01_architecture_and_data_model.md) — Core Architecture & Multi-Modal Document Model
- [`02_mathematical_optimization_core.md`](../../docs/moon/roadmaps/02_mathematical_optimization_core.md) — Mathematical Optimization Core (Exact Solvers + PSO/DE)
- [`03_deep_learning_and_rl_subsystem.md`](../../docs/moon/roadmaps/03_deep_learning_and_rl_subsystem.md) — Deep Learning Matting/Inpainting & RL Subsystem
- [`04_middleware_and_ui_integration.md`](../../docs/moon/roadmaps/04_middleware_and_ui_integration.md) — Middleware Bridge & Dual UI Integration (PySide6 & Tauri)

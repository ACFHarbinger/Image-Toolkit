# Hybrid Image Editor (HIE) — Architectural & Feature Brainstorming Proposal

**Author:** Gemini (Pair-programmed with Chat)  
**Date:** 2026-08-12  
**Repository:** `submodules/HIE`  

---

## 1. Executive Summary

The **Hybrid Image Editor (HIE)** is a next-generation editing module designed to bridge **High-Performance C++ Mathematical Optimization** with **State-of-the-Art Deep Learning & Reinforcement Learning**. Unlike traditional raster editors (Photoshop/GIMP) or purely generative AI tools, HIE combines exact numerical solvers (for seam routing, color harmonization, layout packing) and metaheuristic optimization (PSO/DE for filter autotuning) with interactive neural tools (matting, inpainting, RL assistant policies).

While HIE will eventually expand into video frame-sequence editing, the primary initial focus is delivering an ultra-productive, intelligent **2D Image Editing Suite**.

---

## 2. Architectural Layering

```
┌─────────────────────────────────────────────────────────────────────────┐
│ UIs & Frontends                                                         │
│  ├─ frontend/ (Tauri Web UI — React + WebGL2 / Canvas2D)               │
│  └─ gui/      (PySide6 Desktop GUI — Qt QGraphicsView / QOpenGLWidget) │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ IPC / CFFI / PySide6 Signals
┌────────────────────────────────────▼────────────────────────────────────┐
│ Middleware Layer (middleware/)                                          │
│  ├─ logic_bridge/  (pybind11 C++ bindings)                            │
│  ├─ dl/            (PyTorch / ONNX Runtime: Matting, Inpaint, SuperRes)│
│  ├─ rl/            (RL Retouching Agent Policies — Gymnasium/Torch)     │
│  └─ opt/           (SciPy / C++ exact & metaheuristic wrappers)         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ C++ Core Calls
┌────────────────────────────────────▼────────────────────────────────────┐
│ High-Performance C++ Logic Core (logic/)                                │
│  ├─ logic/include/ & logic/src/ (Exact Solvers, GNC-TLS, PSO, DE, DP)   │
│  ├─ logic/benchmark/             (Catch2 & C++ Benchmarks)              │
│  └─ logic/test/                  (Unit & Integration Tests)             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Feature Pillars & Technical Modules

### Pillar A: Mathematical Optimization Engine (`logic/` + `middleware/opt/`)
1. **Exact Solvers (Convex / DP / Graph-Cut):**
   * *Optimal Seam Routing & Layer Stitching:* Dynamic Programming and Min-Cut/Max-Flow graph solvers for seamless element insertion and texture quilting.
   * *Exact Color Harmonization:* Convex optimization matching global color palettes across composite layers without clipping dynamic range.
2. **Metaheuristic & Swarm Intelligence (PSO / ACO / DE):**
   * *Particle Swarm Optimization (PSO):* Automated multi-parameter tuning for complex non-linear filter stacks (curves, exposure, sharpening, noise reduction).
   * *Differential Evolution (DE):* Non-convex layout packing and automatic element placement maximizing aesthetic visual composition metrics (rule-of-thirds, visual weight balance).

### Pillar B: Deep Learning & Neural Assistance (`middleware/dl/`)
1. **Interactive Neural Matting & Masking:** High-precision alpha matting for complex hair/translucency (using BiRefNet / FastSAM).
2. **Generative Inpainting & Outpainting:** Neural fill for object removal and canvas extension.
3. **Super-Resolution & Artifact Suppression:** Neural upscaling (Real-ESRGAN) integrated into non-destructive editing nodes.

### Pillar C: Reinforcement Learning Productivity Assistant (`middleware/rl/`)
1. **RL Retouching Agent:** A trained RL policy agent that acts as an "AI Co-Pilot", recommending or executing multi-step editing actions (dodging, burning, local tone mapping, noise suppression) based on artist preferences.
2. **Interactive RL Feedback Loop:** Allows artists to reward/penalize agent edit decisions, adapting the RL policy to individual artist styles over time.

### Pillar D: Dual-Host Frontend Integration (`frontend/` & `gui/`)
1. **Tauri Frontend (`frontend/`):** React 19 + TypeScript + WebGL 2, seamlessly embeddable into Image-Toolkit's web interface or runnable standalone.
2. **PySide6 GUI (`gui/`):** Threaded PySide6 Qt interface, embeddable as a tab in Image-Toolkit's desktop app (`python backend/main.py`) or runnable standalone.

---

## 4. Key Design Questions for Harbinger

To ensure our implementation roadmaps in `submodules/HIE/docs/moon/roadmaps/` align with your exact vision, we would like your input on the following 6 questions:

1. **Primary Canvas Model:** Should HIE use a node-based non-destructive graph canvas (like ComfyUI/Substance Designer), a traditional layer-stack canvas (like Photoshop/GIMP), or a hybrid (layer stack with non-destructive node modifiers)?
2. **C++ & Python Execution Boundary:** For the C++ logic core, should we compile it into Image-Toolkit's central root `base` pybind11 module (similar to ASP), or build a dedicated standalone `hie_logic.so` pybind11 extension inside `submodules/HIE`?
3. **Reinforcement Learning Scope:** What should be the initial RL agent environment? (Option A: Global color/exposure adjustment co-pilot; Option B: Interactive brush stroke / localized retouching agent; Option C: Automatic composition & crop optimizer).
4. **Optimization Solvers Focus:** Which optimization methods should we prioritize in Phase 1? (Option A: Exact solvers for seam blending & palette harmonization; Option B: Swarm Intelligence [PSO/DE] for auto-parameter tuning; Option C: Both in parallel).
5. **Video Editing Architecture Foundation:** Should the internal document representation treat images as 1-frame video sequences from day 1 (allowing seamless transition when video editing lands), or keep image and video data structures separate?
6. **UI Priority:** Should we develop the PySide6 `gui/` or Tauri `frontend/` interface first for Phase 1 verification?

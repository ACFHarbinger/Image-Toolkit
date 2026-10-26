# Roadmap 01: Core Architecture & Multi-Modal Document Model

## Executive Summary
This roadmap defines the core document architecture and canvas model for the **Hybrid Image Editor (HIE)** submodule. Designed from Day 1 for multi-modal inputs (single images and multi-frame video clips), HIE adopts a **Hybrid Canvas Architecture** combining traditional layer-stack controls with non-destructive node modifiers.

---

## Technical Specifications

### 1. Hybrid Canvas Architecture
- **Layer-Stack Foundation:** Top-down composite order with opacity, blending modes (multiply, screen, overlay), and group masks familiar to digital artists.
- **Non-Destructive Node Modifiers:** Each layer can attach arbitrary processing nodes (mathematical optimization filters, neural matting, style transfer, curve autotuning) that process non-destructively without baking pixels into the base raster.
- **Render Graph Evaluator:** C++ DAG engine in `logic/` for topological evaluation, caching dirty layer regions and skipping un-modified node evaluations.

### 2. Multi-Modal Document Data Model
- **Frame Sequence Paradigm:** Every image document is internally represented as a frame sequence array `Sequence[Frame]`, where a single static image is a `1-frame` sequence (`length=1`).
- **Video Editing Readiness:** Expanding from single image editing to video clip editing requires 0 data model refactoring—video files load as `N-frame` sequences with temporal keyframe interpolation for node modifiers.
- **Metadata & Seam Storage:** Stores exact seam routing paths, GNC weights, and character exclusion masks per frame.

### 3. Primary UI Target Selection
- **Primary Phase 1 UI:** **PySide6 Desktop GUI (`gui/`)**. Chosen for zero-IPC Python/C++ memory sharing, low latency for interactive PyTorch/OpenCV rendering, and direct integration into Image-Toolkit's desktop application (`gui/hie_tab.py`).
- **Secondary UI Target:** **Tauri Web GUI (`frontend/`)**. Shared middleware API ensures Tauri can consume the exact same Python/C++ middleware bridge.

---

## Delivery Phases & Deliverables

| Phase | Milestone | Priority | Output Deliverables |
|---|---|:---:|---|
| **Phase 1.1** | Frame Sequence Document Schema | High | `middleware/src/document.py` & C++ `logic/include/document.hpp` |
| **Phase 1.2** | Hybrid Layer-Node DAG Engine | High | C++ topological render graph evaluator in `logic/src/render_graph.cpp` |
| **Phase 1.3** | PySide6 Canvas Viewport | High | PySide6 `QGraphicsView` / `QOpenGLWidget` viewport in `gui/src/viewport.py` |

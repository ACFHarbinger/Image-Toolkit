# HIE Product Decisions — Q&A Synthesis

Date: 2026-08-12

## Confirmed decisions

- **Editor model:** Hybrid stack: familiar layer-based editing with optional non-destructive node graphs/modifiers.
- **Binding boundary:** Follow ASP and expose HIE through Image-Toolkit’s central/root pybind11 module (`base`), keeping C++/Python standards consistent.
- **RL sequence:** Localized retouching assistant first, then global tone/exposure, then composition/crop optimization.
- **Optimization scope:** Exact methods and swarm/evolutionary methods both belong in Phase 1, but should be isolated behind common solver/evaluation interfaces.
- **Media model:** Use a multi-modal representation from day one so still images are a degenerate one-frame sequence without forcing video features into the first UI.
- **UI sequencing:** PySide6 first for Phase 1 verification because it matches existing Image-Toolkit prototypes; retain a shared middleware contract and renderer-independent document model so Tauri can reach parity later.

## UI recommendation

Build PySide6 first. It minimizes integration risk with the existing Image-Toolkit desktop workflow, gives direct access to Qt threading/signals for ML and optimization jobs, and makes rapid validation of the hybrid layer/node interaction easier. Tauri should remain a first-class second host: it is attractive for a polished cross-platform UI and browser tooling, but adds a web/native IPC boundary and is less advantageous while the editing model and middleware contract are still changing.

The decision is about sequencing, not capability. The middleware should expose the same request, progress, cancellation, preview, and commit operations to both hosts.

## Architecture consequences

1. The document model needs explicit `MediaAsset`, `FrameSequence`, `Layer`, `ModifierGraph`, `Selection/Mask`, and `Timeline` concepts, even if the first UI hides timeline controls.
2. The central binding should expose coarse-grained, versioned operations rather than raw pixel buffers wherever possible; large data should use shared memory or mapped handles.
3. RL agents must emit inspectable action proposals and reward metadata, never silently mutate a document.
4. Exact and heuristic optimization must share objective/constraint/evaluation contracts so both can be benchmarked against the same editing task.

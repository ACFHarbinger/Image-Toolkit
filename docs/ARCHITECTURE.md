# Architecture

## Current system

Cel-Shaded-Generator is an offline Python computational-art engine plus a
PySide6 demonstration client. The current UI exercises experimental manga
colorization, temporal propagation, and mesh-deformation algorithms. It is not
yet the planned Krita learning alpha or a production drawing application.

| Package | Location | Responsibility |
| --- | --- | --- |
| `cel_shaded_generator` | `src/cel_shaded_generator/` | UI-independent algorithms and runtime coordination |
| `cel_shaded_generator_gui` | `gui/src/cel_shaded_generator_gui/` | Standalone Qt demonstration client |
| Tests | `test/`, `gui/test/` | Algorithm invariants, UI behavior, and package boundaries |

Both distributions form a `uv` workspace. The GUI declares the core
distribution as a workspace dependency and imports it through its installed
package name. Neither package imports Image-Toolkit internals.

## Integration boundary

Image-Toolkit adds the two source roots to its import path and imports the same
public package names. This is an adapter owned by Image-Toolkit, not a runtime
service consumed by Cel-Shaded-Generator.

Heavy numerical calls are temporarily serialized by
`cel_shaded_generator.runtime.NATIVE_COMPUTE_LOCK` because the existing native
library mix has shown intermittent in-process instability. This is containment,
not the target architecture. Cancellable process-isolated jobs are the planned
next boundary for heavy or unstable work.

## Target system

The Krita plugin will consume versioned lesson, exercise, rubric, review,
redline, progress, job, and model contracts. Python remains the first engine
and research environment. Proven and profiled document, geometry, optimization,
media, and inference services migrate incrementally to C++ without exposing C++
ownership details to clients.

See the [Engine Architecture Roadmap](moon/roadmaps/engine_architecture.md) and
[Krita Learning Alpha](moon/roadmaps/krita_learning_alpha.md).

## Decisions to record next

- Versioned lesson/review/progress schemas and artwork-retention policy.
- Krita plugin-to-engine transport: in-process for lightweight deterministic
  operations versus local IPC for heavyweight jobs.
- Image buffers, color spaces, coordinates, and layer ownership.
- C++ ABI and model-package manifest once the Python contracts stabilize.

# Architecture

## Current system

Cel-Shaded-Generator is an offline Python computational-art engine plus a
PySide6 demonstration client. The current UI exercises experimental manga
colorization, temporal propagation, and mesh-deformation algorithms. It is not
yet the planned Krita learning alpha or a production drawing application.

| Package | Location | Responsibility |
| --- | --- | --- |
| `colorization`, `features`, `learning`, `project`, `rigging`, `temporal` | `logic/src/` | UI-independent domain packages |
| `execution`, `runtime` | `logic/src/` | Isolated-job boundary and native-compute coordination |
| `cel_shaded_generator_gui` | `gui/src/cel_shaded_generator_gui/` | Standalone Qt demonstration client |
| Tests | `logic/test/`, `gui/test/` | Algorithm invariants, UI behavior, and package boundaries |

Both distributions form a `uv` workspace. The GUI declares the core
distribution as a workspace dependency and imports its top-level domain
packages. Neither distribution imports Image-Toolkit internals.

## Integration boundary

Image-Toolkit adds the two source roots to its import path and imports the same
public module names. This is an adapter owned by Image-Toolkit, not a runtime
service consumed by Cel-Shaded-Generator.

Built-in heavy numerical calls cross a serializable `JobRequest`/`Operation`
boundary. Batch colorization and animation use fresh spawned processes;
latency-sensitive ARAP dragging uses a restartable persistent process. The
process-local `NATIVE_COMPUTE_LOCK` remains defense in depth inside workers.
Cancellation, adaptive timeouts, forced termination, and metadata-only local
diagnostics prevent a native failure from taking down the Qt/Krita host.

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

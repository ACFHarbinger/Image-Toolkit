# Standalone Engine Architecture Roadmap

## Objective

Create a standalone, offline engine that can serve the Krita plugin first,
Blender and future desktop clients later, and Image-Toolkit only through an
adapter. C++ is the long-term engine language; Python remains the research and
model-development environment.

## Near-term boundary

The initial Python engine exposes typed jobs and results for analysis,
redlining, colorization, and later animation. UI packages do not import private
engine modules, and engine packages do not import Krita, Qt, or Image-Toolkit.

Heavy or unstable native work should run in cancellable worker processes. This
contains CUDA/BLAS/native-extension failures, enables resource scheduling, and
avoids making one global process lock the permanent concurrency model.

## Stable contracts before C++

- Versioned document, layer, stroke, lesson, rubric, review, redline, model,
  job, progress, and provenance schemas.
- Explicit image layout, color space, alpha, coordinate, and ownership rules.
- Deterministic serialization and migrations.
- Cancellation, progress, diagnostics, and structured errors.
- Capability discovery for optional CUDA/models/plugins.
- Golden inputs and outputs for every ported algorithm.

## C++ migration candidates

Port by measured value, not language preference:

1. Tiled image access, compositing, masks, and color conversion.
2. Stroke/curve geometry and deterministic analyzers.
3. Sparse optimization, region segmentation, correspondence, and deformation.
4. Video frame transport and motion-aware processing.
5. GPU scheduling and ONNX Runtime/TensorRT inference adapters.
6. Import/export validation for Blender, Unity, and Unreal workflows.

Use Python bindings for in-process research and a versioned local IPC service
for application isolation. Keep the C ABI narrow enough that alternative
language clients are possible without exposing C++ object ownership.

## Deployment profile

- First platform: Kubuntu/KDE on x86-64.
- Default inference target: consumer NVIDIA GPU with 12 GB VRAM.
- Higher-memory 24 GB development hardware may enable optional models but may
  not become an accidental baseline.
- CPU fallbacks are desirable for deterministic tools and diagnostics, but
  heavyweight ML need not meet interactive targets on CPU in the first alpha.
- No mandatory account, network service, or silent download.

## Model packages

Each package declares identifier/version, compatible engine ABI, files and
hashes, expected VRAM, license/provenance when known, execution provider, and
capabilities. Built-in validated, community-described, and unverified local
packages remain visibly distinct. Users retain the ability to install arbitrary
models.

## Architecture gates

1. **Standalone Python:** installable core and Krita client with no parent
   imports or alias bootstrap.
2. **Isolated jobs:** cancellable worker protocol and crash recovery.
3. **Measured native pilot:** port one proven bottleneck and demonstrate a
   representative improvement without changing output contracts.
4. **C++ engine foundation:** own stable document/compute services; Python
   becomes a plugin/research worker.
5. **Standalone editor decision:** proceed only when Krita limitations are
   demonstrated by validated workflows.

### Gate 5 exception (2026-08-07)

Gate 5's precondition has **not** been met — no Krita limitation has been
demonstrated by a validated workflow. The owner made an explicit, informed
decision to build a standalone full raster editor now anyway, ahead of that
gate, rather than in response to a discovered limitation. This is recorded
here so the history is honest: this is a scope decision, not evidence Krita
has proven insufficient. The reference-coloring Krita Dockers (Character
Colors, Line Art Segmentation, Chapter Queue, Learning Tutor) remain the
primary, actively-developed host; the standalone editor is a second,
independent host built on the same portable `project`/`colorization` core,
not a replacement in progress.

**Toolkit:** PySide6, matching the existing `cel_shaded_generator_gui`
workspace member (`gui/`) — the standalone editor is being built as new
tabs/elements inside that same package rather than a third Qt-binding
dependency.

**First slice (issue #25, In review pending a manual desktop-app check):**
a canvas + layer-stack foundation — `src/editor/`'s
`LayerStack` (pure numpy, no Qt, mirrors the "portable contract first"
pattern every other milestone in this project uses) plus a
`ReferenceColoringTab` in `gui/` wiring a zoomable/pannable `LayerCanvas`
to an add/remove/reorder/show-hide `LayerListPanel`. No paint tools, masks,
segmentation, or palette preview yet — those are later slices built on this
same foundation, the same way every Krita Docker was built on Krita's own
layer model.

**Second slice (issue #26, In review pending a manual desktop-app check):
brush paint tool.** `src/editor/brush.py` adds `stamp_dot`/`stamp_line` —
pure numpy, no Qt, a hard-edged circular brush composited with straight
alpha "over", deliberately not anti-aliased so it stays simple and
pixel-exact-testable; a softer brush is a later slice on the same contract.
`LayerCanvas` gained an explicit Pan/Brush tool switch (`set_tool`) rather
than overloading left-click, since `QGraphicsView.DragMode.ScrollHandDrag`
already claims left-click-drag for panning; painting targets whichever
layer `LayerListPanel` reports as selected (`layer_selected` signal, new).
`ReferenceColoringTab` adds Pan/Brush radio buttons, a color-swatch button
(`QColorDialog`), and a brush-size spin box. Still no masks, segmentation,
or palette-preview UI — those remain later slices on this same foundation.

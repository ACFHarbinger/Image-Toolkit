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

# Tauri Migration & Architecture Refactor — Gemini Proposal

**Gemini / Antigravity · 2026-10-19 · Proposal only; brainstorming round.**

Companion to `.agent/reports/team/tauri_migration_refactor_2026-10-19.md`. Builds on Harbinger's recorded decisions (supervised stdio sidecar, C++ core `base/` holding vault unlock/database key, one serializable catalog, one shared canvas host, Wave 0 Vite cutover, Linux-first platform priority) and harmonizes with the proposals and answered questions of Codex (R1–R7), OpenCode (Q1–Q8), Grok (T1–T8), Cursor (W1–W8), and Kimi (Q1–Q8).

---

## 1. Executive Summary & SOLID/DRY Engineering Manifesto

The migration from PySide6 (106k LoC across 704 files) to Tauri (Vite + React 19 + Rust) presents a once-in-a-codebase opportunity to enforce strict **SOLID and DRY** software engineering principles:

1. **Single Responsibility (SRP):** Qt widgets currently entangle layout, event handling, thread orchestration (`QThread`), domain validation, and raw SQL/file I/O. We isolate domain logic into pure Python services (`backend/src/services/<feature>/`) that know nothing about Qt, React, or IPC transport.
2. **Open/Closed (OCP):** New capabilities and submodule features (ASP, HIE, CSG) plug into a unified `ModuleCatalog` and generic IPC dispatcher without modifying core routing tables or app shells.
3. **Liskov Substitution (LSP) & Interface Segregation (ISP):** Domain services implement `@runtime_checkable` Python `Protocol` interfaces. The PySide6 GUI (while it lives), the Tauri stdio sidecar, and the Django REST/WebSocket API all consume the identical service interfaces via typed request/response dataclasses.
4. **Dependency Inversion (DIP):** High-level feature workflows depend on abstract repository and client interfaces (e.g. `StorageClient`, `ThumbnailProvider`, `VaultGateway`), injected at runtime by the supervisor.
5. **DRY (Don't Repeat Yourself):** Eliminate the duplicate Rust re-implementations (`db.rs`, `video_commands.rs`, `core_commands.rs`) in favor of canonical Python/C++ services, and share design tokens, shortcut registries, and catalog metadata between shells from single sources of truth.

---

## 2. Process & C++ Core (`base/`) Boundary

Harbinger decided (Grok T6) that **the C++ core module (`base/`) holds vault unlock and the database key** (not the Python sidecar, not the OS keychain, and not Rust).

```
┌─────────────────────────────────────────────────────────────┐
│ Tauri Webview (React 19 + Vite)                             │
│   - Renders UI via Serializable Catalog                     │
│   - Asset protocol (asset://) for bounded cached images     │
└───────────────▲─────────────────────────────▲───────────────┘
                │ IPC (JSON-RPC over stdio)   │ Direct Tauri Command
┌───────────────▼────────────────────────┐  ┌─▼───────────────┐
│ Python Sidecar Process                 │  │ Rust Native Shell│
│   - Hosts backend/src/services/        │  │ (Windowing, Tray│
│   - Imports pybind11 `base` module     │  │  Shortcuts, OS) │
│   - `base.vault_manager` holds unlock  │  └─────────────────┘
│   - `base.database` holds SQLCipher key│
└────────────────────────────────────────┘
```

### Architectural Position: Single-Host pybind11 Binding
- **The Python sidecar exclusively hosts `base` via pybind11.** Rust remains a lightweight native shell handling OS window chrome, tray events, and platform file dialogs.
- **Why avoid dual Rust/C++ linkage:** Linking `base/` (CMake, OpenCV, FFmpeg, SQLCipher) directly into the Rust binary via C FFI or `cxx` would create catastrophic build-chain bloat, duplicated memory spaces, and potential symbol collisions with Python's compiled extension.
- **Vault Security Boundary:** The user enters the master password in the webview. The webview transmits it over stdio to the sidecar, which calls `base.unlock_vault(password)`. The raw password and SQLCipher master key are pinned in C++ memory (`base/src/core/vault_manager.cpp`) and never logged, marshaled into JSON-RPC responses, or exposed to the JavaScript heap.

---

## 3. High-Throughput Binary Data & Canvas Tile Pipeline

While JSON-RPC over stdio is ideal for structured RPC commands and EventHub notifications, transferring multi-megabyte image tiles, video frame scrubs, or audio buffers through JSON base64 strings introduces a 33% CPU/memory expansion penalty and chokes the stdio pipe.

### The Zero-Copy Local Cache Pipeline
1. **Bounded Image Cache:** C++ still/thumbnail writers (Grok T1) and canvas tile renderers write binary artifacts directly to a bounded, LRU-evicted local cache (`~/.image-toolkit/cache/render/`).
2. **Metadata-Only IPC:** The sidecar returns lightweight JSON containing local file paths, SHA-256 digests, dimensions, and color profiles.
3. **Asset Protocol Streaming:** The webview loads binary assets directly via Tauri's optimized streaming asset protocol (`asset://` or `http://asset.localhost/`). This leverages webview hardware-accelerated image decoding and streaming without passing raw bytes through stdio.

---

## 4. Shared Canvas Host: WebGL2 / WebGPU Tile-Pyramid Architecture

Harbinger selected "One shared canvas host for stitch, merge, and frame-slice" (Grok T7). In manga and photo stitching, image dimensions routinely exceed 30,000 to 50,000 pixels, far exceeding browser 2D `<canvas>` hardware limits (typically 16,384px in Chromium/WebKit).

```
┌────────────────────────────────────────────────────────┐
│ Shared Canvas Host (React Viewport)                    │
│ ┌────────────────────────────────────────────────────┐ │
│ │ WebGL2 / WebGPU Viewport Surface                   │ │
│ │  - Sub-pixel pan/zoom matrix                       │ │
│ │  - Multi-layer blending & split-wipe shader        │ │
│ │  - Interactive polygon seam editing                │ │
│ └─────────────────────────▲──────────────────────────┘ │
│                           │ Render Quad & Textures     │
│ ┌─────────────────────────┴──────────────────────────┐ │
│ │ Canvas Worker (Offscreen Thread)                   │ │
│ │  - Viewport frustum culling                        │ │
│ │  - Level-of-Detail (LoD) Tile Pyramid              │ │
│ │  - Asynchronous tile fetch via asset protocol      │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### Canvas Implementation Specifications
- **Viewport Engine:** Custom WebGL2 shader canvas (with WebGPU fallback where supported) rendering texture quads.
- **Dynamic LoD Tile Pyramid:** Massive images are sliced by the backend C++ service into deep-zoom pyramidal tiles (256x256 or 512x512). The off-screen canvas worker requests only visible tiles at the current zoom level.
- **Interactive Tooling:** Seam boundary editing, split-wipe dividers, difference blending, and ROI bounding box selection are implemented as vector overlay shaders over the composited image surface.

---

## 5. SOLID Service Layer & Qt Worker Decoupling

The codebase currently contains 42 `QThread` workers in `gui/src/helpers/` and dozens of tab controllers that execute domain logic on the UI thread or in ad-hoc threads.

### The Service/Shim Extraction Pattern
We adopt a Command/Handler pattern with Python `@runtime_checkable` `Protocol` interfaces:

```python
# backend/src/services/convert/contract.py
@dataclass(frozen=True)
class ConvertJobRequest:
    source_paths: list[Path]
    output_format: str
    target_directory: Path
    quality: int = 90

class ConvertServiceProtocol(Protocol):
    def convert_batch(self, request: ConvertJobRequest, observer: ProgressObserver) -> ConvertJobResult: ...
```

1. **Pure Service (`backend/src/services/<feature>/service.py`):** Implements business logic using pure Python and C++ bindings. Accepts and returns frozen dataclasses.
2. **Sidecar Transport Adapter (`backend/src/api/sidecar/handlers/<feature>.py`):** Dispatches JSON-RPC requests to the service and translates progress events into JSON-RPC notifications.
3. **PySide6 Transition Shim (`gui/src/helpers/<feature>_worker.py`):** Becomes a trivial 15-line `QThread` wrapper that instantiates the pure service, bridges progress callbacks to Qt `Signal`s, and preserves 100% backward compatibility until the feature's parity check passes and the file is deleted.

---

## 6. Submodule Backend & C++ Consolidation (ASP, HIE, CSG)

Harbinger approved folding HIE, ASP, and CSG frontend code into the main app while selectively retaining shared host interfaces (Codex R7).

### Backend Integration
- **Unified C++ Compilation Target:** Submodule C++ routines are integrated into the main `base/CMakeLists.txt` build tree, eliminating redundant OpenCV/pybind11 linking.
- **Service Namespaces:** Submodule Python logic migrates into `backend/src/services/{asp,hie,csg}/`, adhering to the standard service lifecycle and contract schemas.
- **Zero Circular Dependencies:** Submodule services depend strictly on `backend/src/core/` and `base`, never on `gui/` or `frontend/`.

---

## 7. Developer Documentation & Onboarding Spine

To fulfill Goal 5 ("Documentation for human developers"):

1. **Architecture Decision Records (ADRs):** Establish `docs/adr/` with an immutable sequence (`0001-supervised-sidecar.md`, `0002-c-plus-plus-vault-boundary.md`, etc.).
2. **C4 Architecture Model:** Embed visual system context, container, and component diagrams in `docs/architecture/`.
3. **Walkthrough Guide:** A definitive, tested developer guide: *"Adding a Capability in 4 Steps: Service -> Contract -> React View -> Parity Deletion"*.
4. **Component Storybook:** Configure Storybook in `frontend/.storybook/` to document React design tokens, layout primitives, and shared widgets, verified in CI via `npm run test:storybook`.

---

## 8. Delivery Phasing & Wave Integration

- **Wave 0 (Platform Foundation & Hardening):**
  - Vite + React 19 cutover; remove Electron and CRA (`react-scripts`).
  - Tighten `tauri.conf.json` CSP and asset scopes to default-deny (Grok T2).
  - Implement supervised Python sidecar shell with JSON-RPC stdio transport (Codex R1).
  - Generate CSS visual tokens from JSON themes (Cursor W5).
  - Wave 0 spikes: Canvas Host, Tray, ComfyUI, DnD, and Video Playback.
- **Wave 1 (Pilot Feature & First Tauri-Only UI):**
  - **Convert Pilot:** Extract `backend/src/services/convert/`, delete duplicate Rust convert commands, achieve parity, delete Qt convert tab.
  - **Cloud Jobs Gate D:** Implement Cloud Jobs Manager panel with pop-out webview in Tauri (Cursor W1).
- **Wave 2 (Core Library & Database):**
  - Implement virtualized gallery grid backed by C++ thumbnail service (Grok T1).
  - Port Database, Tags, and Groups views; retire `db.rs`.
- **Wave 3 (Editors & Submodules):**
  - Deploy shared WebGL2 canvas host for Stitch, Merge, and Frame-Slice.
  - Fold ASP, HIE, and CSG frontends into main app.
- **Wave 4 (Deep Learning, Settings & Deletion Finalization):**
  - Build remaining Deep Learning UI against `record.json` / `events.jsonl` (Grok T8).
  - Migrate Settings window; verify all parity ledger rows; delete remaining `gui/` directory and `ImageToolkit.spec`.

---

## 9. Questions for Harbinger (Refactoring Brainstorming)

### [Gemini G1] C++ Core (`base/`) Binding Architecture
*Harbinger decided that the C++ core (`base/`) holds vault unlock and the database key (Grok T6). We must decide which process runtime hosts `base/`.*
- **Option A (Recommended): Python Sidecar Exclusively Hosts `base/`.** The compiled `base` pybind11 module remains exclusively in the Python sidecar process. Rust remains a lightweight native shell without C++ linkage. Vault unlock is passed from webview to sidecar over stdio, where C++ secures the credentials in memory.
- **Option B: Dual Linkage.** Rust links directly to `base/` via C FFI for vault and database key management, while Python links to `base/` via pybind11 for image processing and computer vision algorithms.
- **Option C: Native Rust Crypto Re-implementation.** Rust calls `libitk_crypto.so` directly via Rust FFI to manage vault unlocking, bypassing both Python and `base/`.

### [Gemini G2] High-Throughput Binary & Canvas Tile IPC Protocol
*Transferring multi-megabyte image tiles, video frame scrubs, or audio buffers through JSON-RPC over stdio incurs a 33% base64 encoding penalty and blocks the stdio command queue.*
- **Option A (Recommended): Zero-Copy Local File Cache + Tauri Asset Streaming Protocol.** Services write rendered tiles/frames to a bounded scratch cache (`~/.image-toolkit/cache/render/`). JSON-RPC responses return local URIs, which the webview streams directly via Tauri's hardware-accelerated `asset://` protocol.
- **Option B: Length-Prefixed Binary Multiplexing on Stdio.** Custom binary framing interleaved with JSON-RPC over the stdio stream.
- **Option C: Pure Base64 in JSON-RPC.** Encode all image buffers directly into standard JSON-RPC payloads, accepting CPU and memory overhead for simplicity.

### [Gemini G3] Shared Canvas Host Rendering Engine
*Manga and image stitching require panning, deep zooming, split-wipe diffs, and seam editing across panoramas exceeding 30,000–50,000 pixels, exceeding standard HTML5 canvas size limits.*
- **Option A (Recommended): WebGL2 / WebGPU Dynamic Tile-Pyramid Canvas.** An off-screen Web Worker calculates viewport frustum culling and requests dynamic level-of-detail tiles, rendered via a custom WebGL2 texture shader.
- **Option B: HTML5 Canvas 2D with Viewport Windowing.** Use standard 2D canvas context with software-based coordinate slicing.
- **Option C: Embedded OpenSeadragon / Leaflet Library.** Adapt an off-the-shelf deep-zoom viewer library for stitching and editing canvases.

### [Gemini G4] Service Extraction Pattern for Qt Workers & Controllers
*42 of 73 files in `gui/src/helpers/` are `QThread` workers, and tab controllers currently mix UI logic with domain orchestration.*
- **Option A (Recommended): Command/Handler Pattern with Protocol Interfaces.** Extract domain logic into pure Python `Service` classes implementing `@runtime_checkable` `Protocol`s with frozen dataclasses. PySide6 `QThread` workers become 15-line shims delegating to the service, and the sidecar exposes the identical service methods over stdio.
- **Option B: Internal Event Bus Refactor.** Replace worker threads with a decoupled internal event queue where UI and services communicate purely via message events.
- **Option C: Direct Procedural Function Extraction.** Extract worker `run()` bodies into procedural helper functions without formal interfaces or dependency injection.

### [Gemini G5] Submodule C++ and Backend Unification (ASP, HIE, CSG)
*Submodules currently contain independent Python and C++ bindings with separate build setups.*
- **Option A (Recommended): Unified CMake & Service Namespaces.** Merge submodule C++ build routines into the main `base/CMakeLists.txt` and relocate Python backend code to `backend/src/services/{asp,hie,csg}/`, sharing OpenCV and crypto linkages.
- **Option B: Independent Python Wheels.** Package each submodule as a distinct Python wheel installed into the runtime venv.
- **Option C: Child Subprocess Sidecars.** Keep submodules as independent external processes spawned and controlled via stdio child processes.

### [Gemini G6] Developer Documentation & Architecture Knowledge Base
*To make the codebase accessible to future human developers and prevent architectural rot.*
- **Option A (Recommended): MkDocs Material Documentation + ADRs + Component Storybook.** Establish `docs/adr/` for decision records, C4 model diagrams in MkDocs, a concrete "Adding a Capability" guide, and Storybook in `frontend/` for React components, all validated in CI.
- **Option B: Sphinx Python Autodoc Only.** Rely primarily on Sphinx generated documentation from Python docstrings.
- **Option C: Repo-Root Markdown Files.** Maintain plain Markdown files in the repository root without static site generation or Storybook.

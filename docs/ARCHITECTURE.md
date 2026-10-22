# Image-Toolkit Architecture Reference

**Image-Toolkit** is a modular, multi-language desktop and cloud media engineering platform. Its architecture separates the presentation shell (**React 19 + Tauri 2**) from the domain service layer (**Python `middleware/`**) and the performance/cryptography core (**C++17 `backend/`** via `pybind11`).

> For the 13-stage Anime Stitch Pipeline (ASP) algorithmic reference and stage flowcharts, see [ASP_ARCHITECTURE.md](ASP_ARCHITECTURE.md).
> For the locked architectural decisions and rationale, see [Architecture Decision Records (ADRs)](adr/index.md).

---

## 1. C4 Level 1 — System Context

At the system context level, Image-Toolkit runs locally on the user's workstation while orchestrating optional remote compute providers, external media boards, and cloud storage remotes.

```mermaid
flowchart TD
    User["User / Media Engineer\n(Desktop, Web, or Mobile)"]

    subgraph Workstation["Local Workstation"]
        ITK["Image-Toolkit Platform\n(Tauri 2 Desktop, Supervisor,\nPython Sidecar, C++ Core)"]
        LocalFS[("Local Image & Video Library\n+ ~/.image-toolkit/*.db\n(SQLCipher AES-256)")]
    end

    subgraph External["External Systems"]
        CloudCompute["Cloud Compute Providers\n(AWS, GCP, Azure, RunPod,\nHyperstack, Thunder, Oracle, Cloudflare)"]
        Watchdog["Cloud Watchdog & Relay\n(User-owned GCP Function / Cloudflare Worker)"]
        CloudStorage["Cloud Sync Remotes\n(Google Drive, Dropbox, OneDrive)"]
        MediaBoards["External Booru & Search Boards\n(Danbooru, Gelbooru, Sankaku, SauceNAO)"]
    end

    User -->|"Interacts via UI / CLI / Extension"| ITK
    ITK -->|"Reads/writes encrypted stores\nand rendered thumbnails"| LocalFS
    ITK -->|"Dispatches sharded CPU/GPU jobs\nand polls telemetry"| CloudCompute
    ITK -->|"Registers heartbeats & pulls\nremote commands"| Watchdog
    Watchdog -->|"Enforces deadline teardown"| CloudCompute
    ITK -->|"Syncs collections & stages inputs"| CloudStorage
    ITK -->|"Crawls & reverse-searches"| MediaBoards
```

---

## 2. C4 Level 2 — Containers & Process Topology

A lightweight **Supervisor** (`middleware/src/supervisor/`) runs outside the webview and manages the **Python Sidecar**, **Cloud Jobs Daemon**, and **Slideshow Daemon** as sibling OS processes. Closing every GUI window does not interrupt durable background work, and a sidecar restart does not drop daemon credential leases.

```mermaid
flowchart TD
    subgraph UI_Process["Desktop UI Process (frontend/)"]
        Webview["React 19 + Vite Webview\n(Catalog Shell, EventHub, WebGL2/WebGPU Canvas)"]
        TauriShell["Tauri 2 Rust Shell (src-tauri/)\n(WindowManager, Native Tray, OS Dialogs,\nDefault-Deny Capabilities, asset:// Protocol)"]
        HostClient["HostClient\n(Transport Adapters: Sidecar, Django, Rust)"]
        Webview --> HostClient
        HostClient --> TauriShell
    end

    subgraph Supervisor_Group["Supervised Process Group (middleware/src/supervisor/)"]
        Supervisor["Process Supervisor\n(Single-Instance Gate, Restart Backoff,\nbridge.down / bridge.ready Lifecycle)"]
        Sidecar["Python Sidecar\n(Versioned JSON-RPC 2.0 over stdio)"]
        CloudDaemon["Cloud Jobs Daemon\n(Single-Instance, Authenticated IPC, JSONL WAL)"]
        SlideshowDaemon["Slideshow Daemon\n(Per-Monitor Wallpaper Rotation)"]
        Supervisor -->|"Spawns & monitors"| Sidecar
        Supervisor -->|"Spawns & monitors"| CloudDaemon
        Supervisor -->|"Spawns & monitors"| SlideshowDaemon
    end

    subgraph Remote_API["Optional Remote Server (api/ & tasks/)"]
        Django["Django REST API + Celery\n(Remote Mobile / Web Bridge)"]
    end

    subgraph Core_Stores["Encrypted Data & Cache Layer (~/.image-toolkit/)"]
        LibraryDB[("library.db\n(SQLCipher Unified Store +\nEmbeddings + Settings)")]
        CloudDB[("cloud_jobs.db\n(SQLCipher Jobs, Shards,\nEvents & Spend Ledger)")]
        RenderCache[("cache/render/\n(Bounded Middle-Frame JPEGs\nfor asset:// Streaming)")]
    end

    TauriShell <-->|"Framed JSON-RPC / stdio"| Sidecar
    TauriShell -.->|"Zero-copy asset:// stream"| RenderCache
    Sidecar --> LibraryDB
    Sidecar --> RenderCache
    CloudDaemon --> CloudDB
    Django --> LibraryDB
```

### Process Invariants

| Invariant | Enforcement Mechanism |
|---|---|
| **No business logic in Tauri Rust** | `frontend/src-tauri/` handles only windowing, tray, native dialogs, drag-and-drop, and `asset://` streaming. Domain logic lives in `middleware/src/services/` and `backend/`. |
| **Stdout is protocol-only** | Sidecar `stdout` carries exclusively framed JSON-RPC messages; `stderr` carries redacted diagnostics. |
| **Vault keys stay in C++** | `backend::vault` holds master keys and database keys in `mlock`-pinned memory (`LockedSecret`). The webview receives only an opaque session handle; daemons receive **sealed per-store leases** (`backend::vault::unseal_lease`). |
| **Zero-copy media transport** | Large images are never base64-encoded over stdio. The C++ thumbnail service writes bounded middle-frame stills to `~/.image-toolkit/cache/render/`, and the webview streams them via `asset://` under a strict capability scope. |
| **Single encrypted database engine** | Both `library.db` and `cloud_jobs.db` use SQLCipher via `backend.database.Database`. PostgreSQL/pgvector is retired. |

---

## 3. C4 Level 3 — Service & Core Components

Every feature vertical follows a strict layered architecture with automated boundary enforcement in both Python (`import-linter`) and TypeScript (`eslint-plugin-boundaries`).

```mermaid
flowchart LR
    subgraph Frontend_Components["Frontend Webview (frontend/src/)"]
        Shell["Catalog Shell\n(frontend/src/shell/)\nRail · Ribbon · Inspector · Status"]
        FeatureView["Feature Views\n(frontend/src/features/<feature>/)"]
        EventHub["Generated EventHub\n(Snapshot + Bounded Tail + Seq Gap Resnapshot)"]
        AppStore["appStore.ts\n(Ephemeral UI State Only)"]
        Shell --> FeatureView
        FeatureView --> EventHub
        FeatureView --> AppStore
    end

    subgraph Contracts_Layer["Contract Spine (contracts/)"]
        Schemas["JSON Schemas + methods.toml\n(contracts/schemas/ · CONTRACTS.sha256)"]
    end

    subgraph Middleware_Components["Python Middleware (middleware/src/)"]
        ServiceAPI["Public Service Surface\n(middleware/src/services/<feature>/api.py)"]
        Commands["Frozen Command / Result Dataclasses\n(commands.py)"]
        Handlers["@runtime_checkable Protocol Handlers\n(handlers.py · service.py)"]
        Submodules["Absorbed Feature Services\n(services/{asp,hie,csg,cre}/)"]
        CloudEngine["Cloud Jobs Engine\n(middleware/src/cloud/)\nJobSpec · Pure Reconciler · Preflight · Cost"]
        ServiceAPI --> Commands
        ServiceAPI --> Handlers
        Handlers --> Submodules
    end

    subgraph Cpp_Backend["C++17 Native Core (backend/)"]
        Bindings["pybind11 Module (import backend)\n(backend/src/bindings.cpp)"]
        CppCore["Core & Media Ops\n(convert, merger, finder, similarity,\nimage_batch, video_batch, wallpaper)"]
        CppVault["Vault & SQLCipher Engine\n(vault.cpp, locked_secret.cpp,\ndatabase.cpp, itk_crypto.c)"]
        CppSolvers["ASP & HIE Native Solvers\n(matching, bundle_adjust, seam,\ncompositing, exact_solvers, metaheuristics)"]
        Bindings --> CppCore
        Bindings --> CppVault
        Bindings --> CppSolvers
    end

    FeatureView -->|"Typed RPC"| Schemas
    Schemas -->|"Dispatches to"| ServiceAPI
    Handlers -->|"Calls via pybind11"| Bindings
    CloudEngine -->|"Sealed lease & DB"| CppVault
```

---

## 4. Repository Module Map & Boundary Rules

| Directory | Package / Target | Role | Boundary Contract |
|---|---|---|---|
| `contracts/` | `contracts/generate.py` | Single source of truth for RPC schemas (`contracts/schemas/`), routing (`methods.toml`), generated TS/Py/Rust bindings, and `CONTRACTS.sha256`. | `python contracts/generate.py --check` fails CI on drift. |
| `backend/` | `import backend` (`.so`) | Unified CMake + pybind11 C++17 extension (including absorbed ASP and HIE C++ solvers, SQLCipher DB engine, and `libitk_crypto.so`). | Built via `just build::build-base`; tested via `just test-base-cpp`. |
| `middleware/` | `middleware.src.*` | Python orchestrator, `services/<feature>/` Command/Handler layer, `supervisor/`, `cloud/`, and ML pipelines. | Must never import `gui.*` or `PySide6` (except `middleware/src/app.py` launch shim). Sibling services under `middleware/src/services/*` are independent (`lint-imports`). |
| `frontend/` | `image-toolkit` | React 19 + TypeScript + Vite webview and `src-tauri/` Rust host. | `eslint-plugin-boundaries` forbids cross-feature and cross-tab-domain imports; `check_tauri_security.py` enforces real CSP and default-deny `asset://` scopes. |
| `gui/` | `gui.src.*` | Legacy PySide6 desktop interface (coexisting during Tauri migration). | **Frozen to reviewed bugfixes only** (`W0-20`). New UI lands exclusively in `frontend/`. |
| `migration/` | `migration/features.toml` | Capability migration ledger, route maps, parity scenarios, and bounded freeze/schema exceptions. | Validated in CI; generates `docs/migration/parity.md`. |
| `api/` & `tasks/` | Django + Celery | Remote HTTP/WebSocket bridge exposing `middleware/src/services/` to mobile and web clients. | Tasks must remain idempotent and contain zero domain logic. |
| `app/` & `extension/` | Android, iOS, WebExt | Kotlin/Compose Android app, SwiftUI iOS app, and Manifest V3 browser extension. | Consume contracts via `api/`. |

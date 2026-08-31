# AGENTS.md - Instructions for Coding Assistant LLMs

## 1. Project Overview & Mission
**Image-Toolkit** is an integrated image database and editing framework that bridges high-performance computer vision (PyTorch, OpenCV) with robust web automation (Selenium) and cross-platform accessibility.
The project mission is to provide a unified environment for managing massive image libraries, performing semantic vector searches, and automating stylized content generation.

## 2. Technical Stack & Governance
* **Runtime**: Python 3.11+ (managed via `uv`, `conda`, or `venv`). **Agent Rule**: Always run `source .venv/bin/activate` at the start of a task.
* **Core Logic**: C++ (via pybind11/CMake) for high-performance IO and processing.
* **Backend**: Python Orchestrator, PostgreSQL (`pgvector`), PyTorch, OpenCV.
* **GUI**: PySide6 (Qt for Python).
* **Frontend/Mobile**: React, Kotlin (Android), Swift (iOS).
* **Web Automation**: Selenium WebDriver.

## 3. Global Operational Playbook

### RESOURCE RULE — benchmark/test-suite runs go through Codex, with Harbinger authorization

**No agent may launch a benchmark run (`bench_anime_stitch.py`, the ASP
registration monitor, `asp_registration_monitor.sh`, or any multi-case/
multi-hour corpus run) or a full test suite (`pytest` across a whole
directory, `gui/test/`, `submodules/ASP/backend/test/`, etc.) without
going through this exact chain.** Multiple agents launching these
concurrently has crashed Harbinger's machine. This is a hard rule, not a
suggestion:

*   If you (any agent other than Codex) need a benchmark or full test-suite
    run, **post the request to the bus addressed to Codex** — what you need
    run and why. Do not run it yourself.
*   **Codex** is the only agent who runs these, since he already knows the
    memory-management precautions they require. Codex relays the request to
    Harbinger and waits for explicit go-ahead before running anything.
*   Only one such run happens at a time, full stop — Codex does not start a
    new one while another is in flight, regardless of who asked.
*   Small, targeted, fast checks are still fine for any agent without going
    through this chain — a single test file, a handful of `-k`-selected
    tests, `py_compile`, `ruff check`. If in doubt whether something is
    "small," ask instead of assuming.
*   Never background a run and walk away from it unmonitored.
*   Applies to every agent in this repo — Agy/Gemini, deepseek, opencode,
    Antigravity, Claude, and any other future agent — with no exceptions
    carried over from earlier sessions. Codex himself still needs
    Harbinger's go-ahead per run; "Codex runs them" is not "Codex runs them
    whenever he wants."

### Key CLI Entry Points
| Action | Command |
| :--- | :--- |
| **Sync Environment** | `bash desktop/linux/scripts/setup_env.sh` |
| **Activate Venv** | `source .venv/bin/activate` |
| **Launch Desktop App** | `python backend/main.py` |
| **Frontend Dev** | `npm run start-all` |
| **Frontend Build** | `npm run start-electron` |
| **Mobile Build** | `./gradlew assembleDebug` |
| **Single Conversion** | `python backend/main.py convert --output_format png --input_path <path>` |
| **Batch Conversion** | `python backend/main.py convert --output_format png --input_path <dir> --input_formats webp` |
| **Helper Conversion** | `bash desktop/linux/cli/convert_images.sh` |
| **Build Desktop App** | `pyinstaller --clean ImageToolkit.spec` |
| **Run Python Tests** | `pytest` |
| **Run Frontend Tests** | `npm run test-frontend` |
| **Run C++ Tests** | `just test-base-cpp` |
| **Bump Version** | `just release::bump 1.2.3` |

### External Access Rules
*   **Docs**: Use Google Search for PySide6, pgvector, OpenCV, PyTorch Hub.
*   **Debugging**: Search for WebDriver conflicts if crawlers fail.

### Global Coding Standards
*   **Database**: Maintain `pgvector` schema compatibility. Use transactions for group/image integrity.
*   **Security**: **NEVER** hardcode credentials. Use `VaultManager`.
*   **Threading**: All heavy computations must run off the main thread (QThread/QRunnable).
*   **Versioning**: The single source of truth is the root `pyproject.toml`
    `[project].version`. Never hand-edit a version — change it only via
    `just release::bump <semver>`, which validates SemVer and rewrites every
    derived source (`pixi.toml`, `package.json`,
    `app/android/build.gradle.kts` `versionName` + derived `versionCode`,
    and the `backend`/`gui`/`git` member `pyproject.toml`s) to match, prints
    the diff, and never commits. The running app reads
    `backend.src._version.__version__` (installed package metadata, falling
    back to the canonical root file), so About / `--version` stays truthful.
*   **Verbosity**: Keep code comments, markdown docs, and git commit messages
    tight. A comment only earns its place if it explains non-obvious *why*
    (a constraint, an invariant, a prior bug) — not what the code already
    says. Commit messages: a one-line summary plus only the context a
    reviewer actually needs, not a full narrative of the investigation that
    led there. Markdown reports/roadmap entries: say the finding and the
    evidence, skip the preamble and the restating-the-question. This applies
    to every agent working in this repo, not just the one currently editing.
*   **AI Review**:
    *   **CRITICAL**: Schema breaking, Security bypass.
    *   **HIGH**: Memory leaks, Deadlocks.
    *   **MEDIUM**: Inefficient SQL, Bad Selectors.
    *   **LOW**: UI Styling, Typos.

### Test & Scratch Directories
*   **Location**: Any test/scratch/fixture directory — throwaway data dirs,
    generated corpora, exported review bundles, regenerated triplets, benchmark
    input trees — MUST be created under `~/Downloads/Data/Tests/`, never inside
    this repo. Point tools at it (`--data-dir`, the eval inspector's "Load
    Directory…", etc.) rather than dropping files in the tree.
*   **Never commit transient files.** `.agent/reports/` is for text findings,
    not image bundles or generated data. A directory of PNGs / exported
    artifacts does not belong in git history — it bloats every clone
    permanently. If a reviewer needs to see images, hand over a path under
    `~/Downloads/Data/Tests/`.
*   Tests must not write outside their `tmp_path` / `~/Downloads/Data/Tests/`
    — no touching `~/.config`, `~/.image-toolkit`, or the repo working tree.
    See `gui/test/conftest.py`'s config-root isolation for the pattern.

### Known Constraints
*   **PostgreSQL**: No SQLite. `pgvector` is required.
*   **Linux**: `qdbus-qt6` compatibility for wallpapers.
*   **Safari**: No headless mode support.

---

## 4. Architecture & Module Instructions

### A. Core & Backend (The Engine)

#### Base Module (`base/`)
**C++ Core**. High-performance implementation of image processing, crawling, and sync logic. Built with CMake + pybind11; the former Rust/PyO3 implementation is archived at `archive/rust/`.
*   **Core**: File system scanning (`file_system`), Image operations (`image_converter`, `image_merger`, `image_finder`), Video (`video_converter`), Wallpaper (`wallpaper`).
*   **Web**:
    *   **Crawlers**: `danbooru`, `gelbooru`, `sankaku`, `image_crawler` (generic Selenium stub — no C++ WebDriver).
    *   **Sync**: `dropbox_sync`, `google_drive_sync`, `one_drive_sync`.
*   **Utils**: Standalone binaries like `slideshow_daemon`.
*   **Interface**: `base/src/bindings.cpp` (pybind11 entry point).

#### Backend Module (`backend/`)
**Python Orchestrator**. Wraps C++ core, handles DB and ML.
*   **Core**: Wrappers for C++ functions, `image_database.py` (DB), `vault_manager.py` (Security).
*   **Models**: Pure Python/PyTorch ML implementations.
*   **Web**: Wrappers for C++ crawlers.
*   **Standards**: Keep Python wrappers thin. Implement heavy logic in C++.

#### Tasks & API (`tasks/` & `api/`)
**Django/Celery Layer**. Bridge between synchronous API and heavy backend logic.
*   **API**: Root Django config (`settings.py`, `urls.py`).
*   **Tasks**: Celery workers (`tasks.py`). **Idempotency** is key.
*   **Standards**: No business logic in tasks; import from `backend/src`.

#### Cryptography (`cryptography/`)
**Security Module**. Kotlin-based credential management.
*   **Capabilities**: Encrypt/Decrypt `.vault` files.
*   **Standards**: Zero trace of sensitive data in memory. Strong AES-256-GCM.

---

### B. Frontend & Interfaces (The View)

#### GUI (`gui/`)
**Desktop Interface**. PySide6 (Qt for Python).
*   **Tabs**: Feature logic (`wallpaper_tab.py`, `convert_tab.py`).
*   **Helpers**: Threaded workers (`QThread`). **CRITICAL**: No blocking I/O on main thread.
*   **Windows**: Window management.
*   **Standards**: Use Signals (`finished`, `error`) for UI communication. Provide visual feedback.

#### Frontend (`frontend/`)
**Web/Desktop Hybrid**. React 19 + Electron.
*   **Stack**: React, TypeScript, Electron.
*   **Standards**: Functional components/Hooks. Secure IPC via `preload.js` (no `nodeIntegration`).

#### Mobile (`app/`)
**Native Apps**. Android (Kotlin) & iOS (Swift).
*   **Android**: Jetpack Compose/XML. Coroutines for I/O.
*   **iOS**: SwiftUI. Swift Concurrency (`async`/`await`).
*   **Standards**: MVVM architecture. Secure storage for credentials. Build with `./gradlew`.

#### Browser Extension (`extension/`)
**Helper Extension**. Manifest V3.
*   **Function**: Context menu to "Save Image".
*   **Standards**: Service workers (no persistent background pages). Sanitize inputs.
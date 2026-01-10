# AGENTS.md - Instructions for Coding Assistant LLMs

## 1. Project Overview & Mission
**Image-Toolkit** is an integrated image database and editing framework that bridges high-performance computer vision (PyTorch, OpenCV) with robust web automation (Selenium) and cross-platform accessibility.
The project mission is to provide a unified environment for managing massive image libraries, performing semantic vector searches, and automating stylized content generation.

## 2. Technical Stack & Governance
* **Runtime**: Python 3.11+ (managed via `uv`, `conda`, or `venv`). **Agent Rule**: Always run `source .venv/bin/activate` at the start of a task.
* **Core Logic**: Rust (via PyO3/Maturin) for high-performance IO and processing.
* **Backend**: Python Orchestrator, PostgreSQL (`pgvector`), PyTorch, OpenCV.
* **GUI**: PySide6 (Qt for Python).
* **Frontend/Mobile**: React, Kotlin (Android), Swift (iOS).
* **Web Automation**: Selenium WebDriver.

## 3. Global Operational Playbook

### Key CLI Entry Points
| Action | Command |
| :--- | :--- |
| **Sync Environment** | `bash scripts/setup_env.sh` |
| **Activate Venv** | `source .venv/bin/activate` |
| **Launch Desktop App** | `python main.py` |
| **Frontend Dev** | `npm run start-all` |
| **Frontend Build** | `npm run start-electron` |
| **Mobile Build** | `./gradlew assembleDebug` |
| **Single Conversion** | `python main.py convert --output_format png --input_path <path>` |
| **Batch Conversion** | `python main.py convert --output_format png --input_path <dir> --input_formats webp` |
| **Helper Conversion** | `bash scripts/convert_images.sh` |
| **Build Desktop App** | `pyinstaller --clean ImageToolkit.spec` |
| **Run Python Tests** | `pytest` |
| **Run Frontend Tests** | `npm run test-frontend` |
| **Run Rust Tests** | `cd base && cargo test` |

### External Access Rules
*   **Docs**: Use Google Search for PySide6, pgvector, OpenCV, PyTorch Hub.
*   **Debugging**: Search for WebDriver conflicts if crawlers fail.

### Global Coding Standards
*   **Database**: Maintain `pgvector` schema compatibility. Use transactions for group/image integrity.
*   **Security**: **NEVER** hardcode credentials. Use `VaultManager`.
*   **Threading**: All heavy computations must run off the main thread (QThread/QRunnable).
*   **AI Review**:
    *   **CRITICAL**: Schema breaking, Security bypass.
    *   **HIGH**: Memory leaks, Deadlocks.
    *   **MEDIUM**: Inefficient SQL, Bad Selectors.
    *   **LOW**: UI Styling, Typos.

### Known Constraints
*   **PostgreSQL**: No SQLite. `pgvector` is required.
*   **Linux**: `qdbus-qt6` compatibility for wallpapers.
*   **Safari**: No headless mode support.

---

## 4. Architecture & Module Instructions

### A. Core & Backend (The Engine)

#### Base Module (`base/`)
**Rust Core**. High-performance implementation of image processing, crawling, and sync logic.
*   **Core**: File system scanning (`file_system`), Image operations (`image_converter`, `image_merger`, `image_finder`), Video (`video_converter`), Wallpaper (`wallpaper`).
*   **Web**:
    *   **Crawlers**: `danbooru`, `gelbooru`, `sankaku`, `image_crawler` (generic Selenium).
    *   **Sync**: `dropbox_sync`, `google_drive_sync`, `one_drive_sync`.
*   **Utils**: Standalone binaries like `slideshow_daemon`.
*   **Interface**: `lib.rs` (PyO3 entry point).

#### Backend Module (`backend/`)
**Python Orchestrator**. Wraps Rust core, handles DB and ML.
*   **Core**: Wrappers for Rust functions, `image_database.py` (DB), `vault_manager.py` (Security).
*   **Models**: Pure Python/PyTorch ML implementations.
*   **Web**: Wrappers for Rust crawlers.
*   **Standards**: Keep Python wrappers thin. Implement heavy logic in Rust.

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
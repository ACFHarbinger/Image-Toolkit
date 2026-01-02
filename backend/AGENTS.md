# Backend Module Instructions (`backend/`)

## Overview
The Backend is the core engine, structured as a hybrid Python/Rust system. It handles database operations, machine learning inference, and acts as the high-level orchestrator for the performance-critical logic implemented in the `base` Rust crate.

## Structure
* **`core/`**:
    *   **Wrappers**: `image_converter.py`, `image_finder.py`, `image_merger.py`, `file_system_entries.py`, and `wallpaper.py` are now lightweight wrappers around the `base` Rust extension.
    *   `image_database.py`: **CRITICAL**. Handles PostgreSQL `pgvector` interactions (Pure Python).
    *   `vault_manager.py`: Handles credential security (Pure Python).
*   **`models/`**:
    *   Contains PyTorch/OpenCV implementations (GANs, LoRA, etc.) which remain in Python for ecosystem compatibility.
*   **`web/`**:
    *   **Wrappers**: All crawlers (`danbooru`, `google_drive_sync`, etc.) and `web_requests` now wrap specific Rust implementations in `base::web`.
*   **`utils/`**:
    *   `slideshow_daemon.py`: A wrapper that launches the standalone `slideshow_daemon` Rust binary.

## Coding Standards
1.  **Rust Integration**:
    *   Prefer implementing heavy logic in `base` and exposing it via `pyo3`.
    *   Keep Python files in `core` and `web` as thin interfaces where possible.
2.  **Database**:
    *   Strict adherence to the `pgvector` schema.
    *   Use transactions for multi-step operations.
3.  **Security**:
    *   **NEVER** hardcode credentials. Always use `VaultManager`.
4.  **ML Performance**:
    *   Ensure model inference is optimized (batching where appropriate).
    *   Manage GPU memory explicitly if necessary.

## Testing
*   `pytest` is the standard for Python-side logic and integration tests.
*   Rust logic is tested via `cargo test` in the `base` directory.

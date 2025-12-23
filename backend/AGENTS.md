# Backend Module Instructions (`backend/`)

## Overview
The Backend is the core engine, handling database operations, machine learning inference, file management, and external automated web interactions.

## Structure
* **`core/`**:
    *   `image_database.py`: **CRITICAL**. Handles PostgreSQL `pgvector` interactions.
    *   `vault_manager.py`: Handles credential security.
* **`models/`**:
    *   Contains PyTorch/OpenCV implementations (GANs, LoRA, etc.).
* **`web/`**:
    *   Selenium crawlers and API clients.

## Coding Standards
1.  **Database**:
    *   Strict adherence to the `pgvector` schema.
    *   Use transactions for multi-step operations.
2.  **Security**:
    *   **NEVER** hardcode credentials. Always use `VaultManager`.
3.  **ML Performance**:
    *   Ensure model inference is optimized (batching where appropriate).
    *   Manage GPU memory explicitly if necessary.
4.  **Web Automation**:
    *   Handle browser driver compatibility gracefully.
    *   Respect `robots.txt` and rate limits where applicable.

## Testing
*   `pytest` is the standard.
*   Mock external dependencies (DB, Web) for unit tests.

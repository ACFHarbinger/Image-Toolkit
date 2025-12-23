# Tasks Module Instructions (`tasks/`)

## Overview
This module houses the **Celery Async Workers** and the **REST API** endpoints that trigger them. It acts as the bridge between the synchronous Django/API layer and the heavy backend logic.

## Structure
* **`tasks.py`**: Defines `@shared_task` functions. **Crucial**: These wrappers import core logic from `backend/src/` and run it asynchronously.
* **`views.py`**: Django Rest Framework (DRF) views that dispatch tasks or query DB status.
* **`serializers.py`**: DRF serializers for API request/response validation.
* **`urls.py`**: API route definitions for task triggering.

## Coding Standards
1.  **Task Idempotency**:
    *   Tasks should be safe to retry if possible.
    *   Use `bind=True` to access task ID and update state (`self.update_state`).
2.  **Code Reuse**:
    *   **Do not write business logic here.** Import it from `backend/src/`.
    *   This layer is strictly for *orchestration* and *dispatch*.
3.  **Error Handling**:
    *   Catch exceptions in tasks and return a standard `{"status": "error", "message": "..."}` dict to the caller.
4.  **API Design**:
    *   Use readable, resource-oriented URLs (e.g., `/api/convert/`, `/api/crawl/`).

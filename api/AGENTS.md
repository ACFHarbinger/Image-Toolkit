# API Module Instructions (`api/`)

## Overview
The `api/` directory serves as the **root Django project configuration** and the entry point for the HTTP/ASGI server. It orchestrates the routing, settings, and WSGI/ASGI application lifecycle.

## Structure
* **`settings.py`**: Global Django configuration (DB, installed apps, middleware, Celery broker).
* **`urls.py`**: Root URL routing configuration.
* **`celery.py`**: App-wide Celery configuration and module discovery.
* **`asgi.py` / `wsgi.py`**: Entry points for deployment servers (daphne/gunicorn).

## Coding Standards
1.  **Settings**:
    *   Do not hardcode secrets. Use `os.getenv` or `python-decouple`.
    *   Keep `DEBUG` false in production.
2.  **Routing**:
    *   Delegate logic to app-specific `urls.py` (e.g., `tasks/urls.py`). Do not clutter root routing.
3.  **Async**:
    *   Use `asgi.py` for WebSockets or async endpoints if necessary.
4.  **Celery**:
    *   Ensure `app.autodiscover_tasks()` is enabled to find tasks in other modules.

# Docker

Containerized **backend** stack for Image-Toolkit: the Django/Gunicorn web server, a Celery worker,
PostgreSQL (with pgvector), and Redis. The PySide6 desktop GUI and the Tauri frontend are desktop
apps and are **not** containerized here.

## Files

| File | Purpose |
| :--- | :--- |
| `Dockerfile` | Multi-stage build: system toolchain → Python deps (uv) → C++ `base/` pybind11 extension → slim runtime |
| `entrypoint.sh` | Waits for Postgres, applies Django migrations (web only), execs the command |
| `docker-compose.yml` | `db` (pgvector) + `redis` + `backend` (gunicorn) + `worker` (celery) |
| `postgres/init-pgvector.sql` | `CREATE EXTENSION vector` on first DB init |
| `../.dockerignore` | Keeps the (large) repo's build context small |

## Usage

From the repository root:

```bash
docker compose -f docker/docker-compose.yml up --build
```

- Web API: http://localhost:8000
- PostgreSQL: `localhost:5432` (db `image_toolkit`, user `toolkit_user`)
- Redis: `localhost:6379`

Override credentials via a repo-root `.env` (or the shell environment):

```env
DB_NAME=image_toolkit
DB_USER=toolkit_user
DB_PASSWORD=change_me_123
```

## Notes

- The build context is the **repository root** (`context: ..`) so the image can compile the C++
  `base/` extension (mirrors `pixi run build-base`) and copy the backend packages.
- The image installs `gunicorn` and serves `api.wsgi:application`; for an ASGI deployment swap the
  command for `uvicorn api.asgi:application --host 0.0.0.0 --port 8000`.
- This is a heavy image (PyTorch + OpenCV + the ML stack are core dependencies). A production build
  should prune optional generation/ComfyUI dependencies as needed.

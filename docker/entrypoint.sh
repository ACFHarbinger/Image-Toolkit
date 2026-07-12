#!/usr/bin/env bash
# Container entrypoint for the Image-Toolkit backend.
#
# Waits for PostgreSQL, optionally applies Django migrations (web service only),
# then execs the container command (gunicorn web server or celery worker).
set -euo pipefail

# --- Wait for PostgreSQL -----------------------------------------------------
if [[ -n "${DB_HOST:-}" ]]; then
    echo "entrypoint: waiting for postgres at ${DB_HOST}:${DB_PORT:-5432}..."
    for _ in $(seq 1 30); do
        if python -c "import socket,sys; s=socket.socket(); s.settimeout(1); \
            s.connect(('${DB_HOST}', int('${DB_PORT:-5432}'))); s.close()" 2>/dev/null; then
            echo "entrypoint: postgres is up."
            break
        fi
        sleep 1
    done
fi

# --- Django migrations (only where RUN_MIGRATIONS=1) -------------------------
if [[ "${RUN_MIGRATIONS:-0}" == "1" ]]; then
    echo "entrypoint: applying Django migrations..."
    python manage.py migrate --noinput || echo "entrypoint: migrate failed (continuing)"
fi

exec "$@"

"""PostgreSQL + pgvector prerequisite check and diagnostics (issue #477).

Image-Toolkit uses SQLCipher local storage (library.db) as its primary store.
External PostgreSQL (with pgvector >= 0.5.0) is an optional prerequisite for
vector similarity search, anime training pipelines, and legacy migration.

This module provides non-blocking reachability tests and clean user-facing
dialogs pointing to INSTALL.md rather than raw stack traces.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, NamedTuple, Optional

from backend.src.constants import ROOT_DIR
from PySide6.QtWidgets import QMessageBox, QWidget

ENV_FILE = Path(ROOT_DIR) / "env" / "vars.env"


class PostgresStatus(NamedTuple):
    reachable: bool
    has_pgvector: bool
    version_str: str
    message: str


def load_postgres_config() -> Dict[str, str]:
    """Load connection parameters from environment or env/vars.env."""
    env: Dict[str, str] = {}
    if ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    k = key.strip()
                    v = value.strip().strip("'\"")
                    if k.startswith("DB_") or k.startswith("POSTGRES_") or k == "DATABASE_URL":
                        env[k] = v
        except OSError:
            pass

    # Environment variables override the file.
    if os.environ.get("POSTGRES_DB"):
        env["DB_NAME"] = os.environ["POSTGRES_DB"]
    if os.environ.get("POSTGRES_USER"):
        env["DB_USER"] = os.environ["POSTGRES_USER"]
    if os.environ.get("POSTGRES_PASSWORD"):
        env["DB_PASSWORD"] = os.environ["POSTGRES_PASSWORD"]
    if os.environ.get("POSTGRES_HOST"):
        env["DB_HOST"] = os.environ["POSTGRES_HOST"]
    if os.environ.get("POSTGRES_PORT"):
        env["DB_PORT"] = os.environ["POSTGRES_PORT"]

    for key in ("DATABASE_URL", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"):
        if os.environ.get(key):
            env[key] = os.environ[key]

    return env


def check_postgres_reachability(timeout: int = 2) -> PostgresStatus:
    """Test connection to external PostgreSQL and verify pgvector extension.

    Runs quickly with a short timeout. Never raises exceptions.
    """
    try:
        import psycopg2
    except ImportError:
        try:
            import psycopg as psycopg2
        except ImportError:
            return PostgresStatus(
                reachable=False,
                has_pgvector=False,
                version_str="",
                message="PostgreSQL client driver (psycopg2/psycopg) is not installed.",
            )

    pg = load_postgres_config()
    db_url = pg.get("DATABASE_URL")

    try:
        if db_url:
            conn = psycopg2.connect(dsn=db_url, connect_timeout=timeout)
        else:
            conn = psycopg2.connect(
                dbname=pg.get("DB_NAME", "image_toolkit"),
                user=pg.get("DB_USER", "toolkit_user"),
                password=pg.get("DB_PASSWORD", "change_me_123"),
                host=pg.get("DB_HOST", "localhost"),
                port=int(pg.get("DB_PORT", 5432)),
                connect_timeout=timeout,
            )
    except Exception as exc:
        return PostgresStatus(
            reachable=False,
            has_pgvector=False,
            version_str="",
            message=f"Could not connect to PostgreSQL server: {exc}",
        )

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            row = cur.fetchone()
            pg_ver = row[0] if row else "Unknown"

            cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
            vrow = cur.fetchone()
            has_vector = vrow is not None
            vec_ver = vrow[0] if vrow else "Not installed"

        conn.close()
        return PostgresStatus(
            reachable=True,
            has_pgvector=has_vector,
            version_str=f"{pg_ver} (pgvector: {vec_ver})",
            message="PostgreSQL connection successful." if has_vector else "PostgreSQL reachable, but pgvector extension is not installed.",
        )
    except Exception as exc:
        conn.close()
        return PostgresStatus(
            reachable=True,
            has_pgvector=False,
            version_str="",
            message=f"Connected but query failed: {exc}",
        )


def show_postgres_status_dialog(parent: Optional[QWidget] = None, silent_if_ok: bool = False) -> PostgresStatus:
    """Check PostgreSQL reachability and present user-friendly guidance dialog."""
    status = check_postgres_reachability()

    if status.reachable and status.has_pgvector:
        if not silent_if_ok:
            QMessageBox.information(
                parent,
                "PostgreSQL Status: Ready",
                f"External PostgreSQL + pgvector is connected and ready.\n\n"
                f"Version: {status.version_str}",
            )
    elif status.reachable and not status.has_pgvector:
        QMessageBox.warning(
            parent,
            "pgvector Extension Missing",
            "Connected to PostgreSQL, but the 'vector' extension is not enabled on this database.\n\n"
            "To enable pgvector, run:\n"
            "    just db-setup\n"
            "or execute in psql:\n"
            "    CREATE EXTENSION IF NOT EXISTS vector;\n\n"
            "See docs/INSTALL.md for setup instructions.\n"
            "The app will continue using local SQLCipher storage.",
        )
    else:
        QMessageBox.information(
            parent,
            "PostgreSQL Offline (Operating on Local Storage)",
            "External PostgreSQL is currently unreachable or unconfigured.\n\n"
            "• The application is running normally using local SQLCipher encrypted storage (~/.image-toolkit/library.db).\n"
            "• Vector similarity search and training pipelines require PostgreSQL + pgvector.\n\n"
            "To set up PostgreSQL:\n"
            "    just db-setup\n"
            "or refer to docs/INSTALL.md for configuration options.",
        )

    return status


__all__ = [
    "PostgresStatus",
    "check_postgres_reachability",
    "load_postgres_config",
    "show_postgres_status_dialog",
]

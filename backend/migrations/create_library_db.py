"""001 — Create ~/.image-toolkit/library.db with schema v1 (Phase DB, DB.4).

Opens the unified store with the same password/salt pair the vault uses,
applies the DDL from backend/src/database/unified/schema.sql (+ FTS5 layer
when available) and stamps schema_version. Idempotent: the DDL is
IF NOT EXISTS throughout.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from backend.src.database.unified import session


def run(
    password: str,
    salt: str,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Create/upgrade the library DB. Returns a small report dict."""
    import base

    path = str(db_path if db_path is not None else session.DEFAULT_DB_PATH)
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    db = base.database.Database(path, password, salt)
    try:
        session.ensure_schema(db)
        report = {
            "step": "001_create_library_db",
            "db_path": path,
            "schema_version": db.schema_version(),
            "fts_enabled": session.fts_enabled(db),
            "integrity_ok": db.integrity_check(),
        }
    finally:
        db.close()
    return report


def main() -> int:
    import getpass

    password = getpass.getpass("Vault password: ")
    salt = input("Account name (salt): ").strip()
    report = run(password, salt)
    print(report)
    return 0 if report["integrity_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

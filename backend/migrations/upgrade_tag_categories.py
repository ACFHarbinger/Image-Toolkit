"""Upgrade an existing library.db's tags table to the categorized model.

As of this session, ``session.ensure_schema()`` (called on every login)
already self-heals a pre-DB.11 ``tags`` table automatically via
``tag_categories.migrate_legacy_type_column()`` -- no manual step is
required for the app to keep working. This script remains as an explicit,
backup-first way to run that same migration standalone (e.g. before a
scripted/offline maintenance pass), sharing the exact same migration
function so the two paths can never drift apart.

Usage:
    python backend/migrations/upgrade_tag_categories.py \\
        --account-name <vault_account> [--password ...]
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.migrations._backup_utils import backup_database  # noqa: E402
from backend.src.constants import IMAGE_TOOLKIT_DIR  # noqa: E402
from backend.src.database.unified import session, tag_categories  # noqa: E402

DEFAULT_BACKUP_DIR = IMAGE_TOOLKIT_DIR / "backups"


def run(
    password: str,
    salt: str,
    db_path: Optional[str] = None,
    backup_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Migrate tags.type -> tags.category_id. Returns a report dict."""
    import base

    path = str(db_path if db_path is not None else session.DEFAULT_DB_PATH)
    db = base.database.Database(path, password, salt)
    try:
        needs_migration = tag_categories.has_column(db, "tags", "type")
        if not needs_migration:
            return {
                "step": "upgrade_tag_categories",
                "db_path": path,
                "already_upgraded": True,
            }

        backup_path = backup_database(
            Path(path),
            backup_dir if backup_dir is not None else DEFAULT_BACKUP_DIR,
            script="upgrade_tag_categories.py",
        )

        # Same ordering session.ensure_schema() uses: the column must exist
        # before schema.sql's DDL (its CREATE INDEX references category_id),
        # then DDL + seed populate tag_categories, then backfill from the
        # legacy type column and drop it.
        session.ensure_schema(db)

        return {
            "step": "upgrade_tag_categories",
            "db_path": path,
            "already_upgraded": False,
            "backup_path": str(backup_path),
        }
    finally:
        db.close()


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate tags.type to the tag_categories/category_id model."
    )
    parser.add_argument("--account-name", required=True)
    parser.add_argument("--password", help="Vault password. Prompted securely when omitted.")
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    password = args.password or getpass.getpass("Vault password: ")
    if not password:
        print("Error: password is required.", file=sys.stderr)
        return 2

    report = run(
        password=password,
        salt=args.account_name,
        db_path=str(args.db_path) if args.db_path else None,
        backup_dir=args.backup_dir,
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

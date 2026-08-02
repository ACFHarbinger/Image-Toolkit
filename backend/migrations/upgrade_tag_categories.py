"""Upgrade an existing library.db's tags table to the categorized model.

Fresh installs get the new schema (``tag_categories``/``entity_tags``, and
``tags.category_id`` instead of ``tags.type``) automatically via
``schema.sql`` + ``tag_categories.seed()`` (wired into
``session.ensure_schema``). This migration retrofits a DB created before the
Danbooru-style tag overhaul: it applies the current DDL (creates
``tag_categories``/``entity_tags`` if missing, seeds the default categories),
then migrates each tag's legacy ``type`` string onto ``category_id`` (mapping
the old image-tag type ``"Series"`` onto the renamed ``"Copyright"``
category) and drops the now-unused ``type`` column.

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


def _has_column(db, table: str, column: str) -> bool:
    return any(row[1] == column for row in db.query(f"PRAGMA table_info({table})", ()))


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
        # Bring tag_categories/entity_tags (and any other new DDL) up to
        # date first -- ensure_schema is idempotent (IF NOT EXISTS).
        session.ensure_schema(db)

        if not _has_column(db, "tags", "type"):
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

        if not _has_column(db, "tags", "category_id"):
            db.execute(
                "ALTER TABLE tags ADD COLUMN category_id INTEGER "
                "REFERENCES tag_categories(id)"
            )

        rows = db.query(
            "SELECT id, type FROM tags WHERE type IS NOT NULL AND type != ''", ()
        )
        migrated = 0
        for tag_id, old_type in rows:
            category_name = tag_categories.LEGACY_CATEGORY_ALIASES.get(old_type, old_type)
            cat_rows = db.query(
                "SELECT id FROM tag_categories WHERE name = ?", (category_name,)
            )
            category_id = cat_rows[0][0] if cat_rows else None
            db.execute(
                "UPDATE tags SET category_id = ? WHERE id = ?", (category_id, tag_id)
            )
            migrated += 1

        dropped_type_column = False
        try:
            db.execute("ALTER TABLE tags DROP COLUMN type")
            dropped_type_column = True
        except Exception:
            # Older SQLite builds (<3.35) lack DROP COLUMN support; the
            # leftover unused column is harmless (nothing reads it anymore).
            pass

        return {
            "step": "upgrade_tag_categories",
            "db_path": path,
            "already_upgraded": False,
            "backup_path": str(backup_path),
            "tags_migrated": migrated,
            "dropped_type_column": dropped_type_column,
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

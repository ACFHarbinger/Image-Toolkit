"""Clean orphaned benchmark rows out of the live library.db.

The archived ``archive/python/database/bench_database.py`` benchmark (a
legacy pgvector-era script) was, at some point before being archived, run
directly against the real ``~/.image-toolkit/library.db``. Its own cleanup
called ``delete_group()`` on the ``benchmark_images``/``benchmark_search``
groups, but ``delete_group`` only removes the ``groups`` row — ``images.
group_id`` is ``ON DELETE SET NULL``, not cascaded — so the ``/tmp/
bench_img_*.jpg`` and ``/tmp/search_img_*.jpg`` image rows it inserted
survived, orphaned from any group.

This migration finds and removes those orphaned rows directly by
``file_path`` pattern (not by group, since the group rows are already gone),
and additionally removes the two group rows if they still exist. It always
takes a backup first via ``_backup_utils.backup_database``.

Usage:
    python backend/migrations/clean_benchmark_data.py \\
        --account-name <vault_account> [--password ...] [--dry-run]
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
from backend.src.database.unified import session  # noqa: E402

DEFAULT_BACKUP_DIR = IMAGE_TOOLKIT_DIR / "backups"

_PATH_PATTERNS = ("/tmp/bench_img_%", "/tmp/search_img_%")
_GROUP_NAMES = ("benchmark_images", "benchmark_search")


def find_matching_images(db) -> List[Dict[str, Any]]:
    """Return {id, file_path} rows whose file_path matches a benchmark pattern."""
    matches: List[Dict[str, Any]] = []
    seen_ids = set()
    for pattern in _PATH_PATTERNS:
        rows = db.query(
            "SELECT id, file_path FROM images WHERE file_path LIKE ?", (pattern,)
        )
        for image_id, file_path in rows:
            if image_id not in seen_ids:
                seen_ids.add(image_id)
                matches.append({"id": image_id, "file_path": file_path})
    return matches


def find_matching_groups(db) -> List[str]:
    rows = db.query(
        f"SELECT name FROM groups WHERE name IN "
        f"({','.join('?' for _ in _GROUP_NAMES)})",
        _GROUP_NAMES,
    )
    return [name for (name,) in rows]


def run(
    password: str,
    salt: str,
    db_path: Optional[str] = None,
    backup_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Delete benchmark rows from the live DB. Returns a report dict."""
    import base

    path = str(db_path if db_path is not None else session.DEFAULT_DB_PATH)
    db = base.database.Database(path, password, salt)
    try:
        images = find_matching_images(db)
        groups = find_matching_groups(db)

        report: Dict[str, Any] = {
            "step": "clean_benchmark_data",
            "db_path": path,
            "images_found": len(images),
            "groups_found": groups,
            "dry_run": dry_run,
            "backup_path": None,
        }

        if dry_run or (not images and not groups):
            return report

        backup_path = backup_database(
            Path(path),
            backup_dir if backup_dir is not None else DEFAULT_BACKUP_DIR,
            script="clean_benchmark_data.py",
        )
        report["backup_path"] = str(backup_path)

        for image in images:
            db.execute("DELETE FROM images WHERE id = ?", (image["id"],))
        for name in groups:
            db.execute("DELETE FROM groups WHERE name = ?", (name,))

        report["images_deleted"] = len(images)
        report["groups_deleted"] = groups
        return report
    finally:
        db.close()


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove orphaned /tmp/bench_img_*/search_img_* image rows and the "
            "benchmark_images/benchmark_search groups from library.db."
        )
    )
    parser.add_argument(
        "--account-name", required=True,
        help="Vault account name used as the SQLCipher salt.",
    )
    parser.add_argument("--password", help="Vault password. Prompted securely when omitted.")
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be deleted without creating a backup or writing changes.",
    )
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
        dry_run=args.dry_run,
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

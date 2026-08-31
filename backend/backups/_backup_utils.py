"""Shared backup/restore helper for one-off migration scripts.

Extracted from ``sync_listing_associations.py`` so every migration that needs
a lightweight "copy the DB file, write a manifest, allow rollback" safety net
uses the same implementation instead of a copy-pasted one. For the heavier
SHA-256-manifest gate used by the 000-004 runner sequence, see
``backup_all.py`` — that one is a distinct, more involved mechanism and is
not affected by this module.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def backup_database(db_path: Path, backup_dir: Path, script: str) -> Path:
    """Copy *db_path* into *backup_dir* with a timestamped name + manifest.

    Returns the backup file path. *script* is recorded in the manifest so a
    later reader knows which migration produced the backup.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"{db_path.stem}-{stamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)

    manifest = {
        "created_at": stamp,
        "source_db": str(db_path),
        "backup_db": str(backup_path),
        "script": script,
    }
    manifest_path = backup_path.with_suffix(backup_path.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return backup_path


def restore_database(backup_path: Path, db_path: Path) -> None:
    """Replace *db_path* with *backup_path*."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, db_path)

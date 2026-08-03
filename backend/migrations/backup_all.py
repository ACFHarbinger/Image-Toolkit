"""000 — Backup gate for the unified-database migration (Phase DB, DB.4/DB.10).

Creates a timestamped, checksummed backup of every store BEFORE any
migration step may run. The runner refuses to execute 001+ unless a backup
manifest produced by this step exists and its artifacts still verify.

Artifacts (under ``assets/migrations/pre_unified/<UTC timestamp>/``):

* ``library.db.bak``              — byte copy of the unified SQLCipher
                                    library database (Phase DB, DB.10 —
                                    replaces the retired PostgreSQL dump
                                    below now that DB.6 has ported the image
                                    tabs off Postgres entirely)
* ``listings_secure.db.bak``      — byte copy of the (pre-unification)
                                    SQLCipher listings store, kept only for
                                    restoring backups made before DB.5/DB.6
                                    migrated listings onto ``library.db``
* ``listings.json.enc`` / ``entities.json.enc``
                                  — copies of the encrypted JSON exports
                                    (refresh them from the app's "Update
                                    Backup" buttons first; staleness is
                                    recorded, not fatal)
* ``manifest.json``               — SHA-256 of every artifact + skip notes

DB.10 retired this gate's PostgreSQL ``pg_dump`` artifact: DB.6 fully ported
the image tabs off Postgres onto the unified store, so a Postgres dump would
back up a database the app no longer reads from or writes to.

The module is importable (``run_backup()``) for the runner and executable
directly: ``python -m backend.migrations.backup_all``.

File is named without the ``000_`` prefix so it stays importable; the runner
maps step ``000`` to this module.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from backend.src.constants import IMAGE_TOOLKIT_DIR, ROOT_DIR
from backend.src.database.unified.session import DEFAULT_DB_PATH

PRE_UNIFIED_DIR = Path(ROOT_DIR) / "assets" / "migrations" / "pre_unified"
LIBRARY_DB = Path(DEFAULT_DB_PATH)
LISTINGS_DB = Path(IMAGE_TOOLKIT_DIR) / "listings_secure.db"
SECRETS_DIR = Path(ROOT_DIR) / "assets" / "secrets"
ENC_FILES = ("listings.json.enc", "entities.json.enc")

MANIFEST_NAME = "manifest.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_backup(dest_root: Optional[Path] = None) -> Dict[str, Any]:
    """Create the pre-migration backup. Returns the manifest dict.

    Raises ``RuntimeError`` only when NOTHING could be backed up (no library
    DB, no legacy listings DB, no .enc files) — an empty backup would defeat
    the gate. Individual missing sources are recorded as warnings instead.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = Path(dest_root) if dest_root is not None else PRE_UNIFIED_DIR / stamp
    dest.mkdir(parents=True, exist_ok=True)

    artifacts: Dict[str, Dict[str, Any]] = {}
    warnings: list = []

    # (a) Unified SQLCipher library database — byte copy (encrypted at rest
    # already). This is the app's sole data store post-DB.6; back it up
    # first since every other artifact here is legacy/pre-unification.
    if LIBRARY_DB.exists():
        bak = dest / "library.db.bak"
        shutil.copy2(LIBRARY_DB, bak)
        artifacts["library.db.bak"] = {
            "source": str(LIBRARY_DB),
            "bytes": bak.stat().st_size,
            "sha256": _sha256(bak),
        }
    else:
        warnings.append(f"Library DB not found at {LIBRARY_DB} — skipped.")

    # (b) Legacy (pre-unification) SQLCipher listings store — byte copy, kept
    # only for restoring backups made before DB.5/DB.6.
    if LISTINGS_DB.exists():
        bak = dest / "listings_secure.db.bak"
        shutil.copy2(LISTINGS_DB, bak)
        artifacts["listings_secure.db.bak"] = {
            "source": str(LISTINGS_DB),
            "bytes": bak.stat().st_size,
            "sha256": _sha256(bak),
        }
    else:
        warnings.append(f"Listings DB not found at {LISTINGS_DB} — skipped.")

    # (c) Encrypted JSON exports (may be stale; refresh via the app first).
    for name in ENC_FILES:
        src = SECRETS_DIR / name
        if src.exists():
            copy = dest / name
            shutil.copy2(src, copy)
            age_days = (
                datetime.now(timezone.utc)
                - datetime.fromtimestamp(src.stat().st_mtime, tz=timezone.utc)
            ).days
            artifacts[name] = {
                "source": str(src),
                "bytes": copy.stat().st_size,
                "sha256": _sha256(copy),
                "age_days": age_days,
            }
            if age_days > 7:
                warnings.append(
                    f"{name} is {age_days} days old — consider refreshing it "
                    "via the Listings tab 'Update Backup' button before "
                    "migrating."
                )
        else:
            warnings.append(f"{src} not found — skipped.")

    if not artifacts:
        shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError(
            "Backup gate produced no artifacts: no library DB, no legacy "
            "listings DB, and no .enc exports. Refusing to write an empty "
            "backup manifest."
        )

    manifest: Dict[str, Any] = {
        "step": "000_backup_all",
        "created_utc": stamp,
        "backup_dir": str(dest),
        "artifacts": artifacts,
        "warnings": warnings,
    }
    (dest / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )
    return manifest


def find_latest_manifest(root: Optional[Path] = None) -> Optional[Path]:
    """Return the newest manifest.json under pre_unified/, or None."""
    base = Path(root) if root is not None else PRE_UNIFIED_DIR
    if not base.exists():
        return None
    candidates = sorted(base.glob(f"*/{MANIFEST_NAME}"), reverse=True)
    return candidates[0] if candidates else None


def verify_manifest(manifest_path: Path) -> list:
    """Re-hash every artifact in a manifest. Returns a list of problems."""
    problems: list = []
    try:
        manifest = json.loads(Path(manifest_path).read_text())
    except Exception as e:  # noqa: BLE001 — any parse failure is a problem
        return [f"manifest unreadable: {e}"]
    backup_dir = Path(manifest.get("backup_dir", Path(manifest_path).parent))
    for name, info in manifest.get("artifacts", {}).items():
        path = backup_dir / name
        if not path.exists():
            problems.append(f"missing artifact: {path}")
            continue
        if _sha256(path) != info.get("sha256"):
            problems.append(f"checksum mismatch: {path}")
    return problems


def main() -> int:
    print("=== 000_backup_all — pre-migration backup gate ===")
    try:
        manifest = run_backup()
    except RuntimeError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1
    print(f"Backup written to: {manifest['backup_dir']}")
    for name, info in manifest["artifacts"].items():
        print(f"  ✔ {name}  ({info['bytes']} bytes, sha256={info['sha256'][:12]}…)")
    for warning in manifest["warnings"]:
        print(f"  ⚠ {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Migration runner — orchestrates steps 000→004 (Phase DB, DB.4).

Idempotent and resumable: completed steps are recorded in
``~/.image-toolkit/.phase_db_migration_state.json`` and skipped on re-run
(``--force`` restarts from scratch). The backup gate is hard: 001+ refuse to
run unless a backup manifest exists AND still verifies. On verification
failure the runner exits non-zero and points at the backups.

CLI::

    python -m backend.migrations.runner            # prompts for credentials
    python -m backend.migrations.runner --skip-postgres
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from backend.migrations import backup_all, create_library_db, migrate_listings
from backend.migrations import migrate_pgvector, verify_migration
from backend.src.constants import IMAGE_TOOLKIT_DIR

STATE_FILE = Path(IMAGE_TOOLKIT_DIR) / ".phase_db_migration_state.json"

STEPS = ("000_backup_all", "001_create_library_db", "002_migrate_listings",
         "003_migrate_pgvector", "004_verify_migration")


def _load_state(state_file: Path) -> Dict[str, Any]:
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except (ValueError, OSError):
            pass
    return {"completed": {}, "backup_manifest": None}


def _save_state(state_file: Path, state: Dict[str, Any]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _mark(state: Dict[str, Any], step: str, report: Dict[str, Any]) -> None:
    state["completed"][step] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "report": report,
    }


def _require_verified_backup(state: Dict[str, Any]) -> None:
    """The hard gate: a manifest must exist and every artifact must re-hash."""
    manifest = state.get("backup_manifest")
    manifest_path = Path(manifest) if manifest else backup_all.find_latest_manifest()
    if manifest_path is None or not manifest_path.exists():
        raise RuntimeError(
            "backup gate: no backup manifest found — step 000 must run first "
            "(it cannot be skipped)."
        )
    problems = backup_all.verify_manifest(manifest_path)
    if problems:
        raise RuntimeError(
            f"backup gate: backup at {manifest_path.parent} does not verify: "
            f"{problems}. Re-run step 000."
        )
    state["backup_manifest"] = str(manifest_path)


def run_all(
    password: str,
    salt: str,
    db_path: Optional[str] = None,
    legacy_db_path: Optional[str] = None,
    skip_postgres: bool = False,
    force: bool = False,
    state_file: Optional[Path] = None,
    log=print,
) -> Dict[str, Any]:
    """Run 000→004. Returns the state dict; raises on gate/verify failure."""
    state_path = Path(state_file) if state_file is not None else STATE_FILE
    state = {"completed": {}, "backup_manifest": None} if force \
        else _load_state(state_path)
    done = state["completed"]

    # --- 000: backup gate (re-verified on EVERY run, even when resumed) ---
    if "000_backup_all" not in done:
        log("[000] creating pre-migration backup…")
        report = backup_all.run_backup()
        state["backup_manifest"] = str(
            Path(report["backup_dir"]) / backup_all.MANIFEST_NAME
        )
        _mark(state, "000_backup_all", {
            k: v for k, v in report.items() if k != "artifacts"
        })
        _save_state(state_path, state)
        for warning in report.get("warnings", []):
            log(f"      ⚠ {warning}")
    _require_verified_backup(state)
    log(f"[000] backup verified: {state['backup_manifest']}")

    # --- 001: schema ---
    if "001_create_library_db" not in done:
        log("[001] creating library.db schema…")
        report = create_library_db.run(password, salt, db_path=db_path)
        _mark(state, "001_create_library_db", report)
        _save_state(state_path, state)
        log(f"      schema v{report['schema_version']}, "
            f"fts={'on' if report['fts_enabled'] else 'off'}")
    else:
        log("[001] already done — skipping")

    # --- 002: listings ---
    if "002_migrate_listings" not in done:
        log("[002] migrating listings_secure.db…")
        report = migrate_listings.run(
            password, salt, db_path=db_path, legacy_db_path=legacy_db_path
        )
        _mark(state, "002_migrate_listings", report)
        _save_state(state_path, state)
        if report.get("skipped"):
            log(f"      skipped: {report['reason']}")
        else:
            log(f"      {report['media_migrated']} media, "
                f"{report['entities_migrated']} entities"
                + (f", {len(report['dangling_references'])} rows with "
                   f"dangling refs (parked in extra)"
                   if report["dangling_references"] else ""))
    else:
        log("[002] already done — skipping")

    # --- 003: pgvector (skippable) ---
    if skip_postgres:
        log("[003] skipped by --skip-postgres (re-run later without the flag)")
    elif "003_migrate_pgvector" not in done:
        log("[003] migrating PostgreSQL image index…")
        report = migrate_pgvector.run(password, salt, db_path=db_path)
        if report.get("skipped"):
            # Not marked completed: re-runnable once the server is back.
            log(f"      ⚠ SKIPPED: {report['reason']}")
            log("      ⚠ re-run the runner when PostgreSQL is reachable.")
        else:
            _mark(state, "003_migrate_pgvector", report)
            _save_state(state_path, state)
            log(f"      migrated: {report['migrated']}")
    else:
        log("[003] already done — skipping")

    # --- 004: verify (always runs — it is the cutover gate) ---
    log("[004] verifying migration…")
    report = verify_migration.run(
        password, salt, db_path=db_path, legacy_db_path=legacy_db_path
    )
    _mark(state, "004_verify_migration", report)
    _save_state(state_path, state)
    if not report["ok"]:
        for problem in report["problems"]:
            log(f"      ✘ {problem}")
        raise RuntimeError(
            f"verification FAILED ({len(report['problems'])} problems). "
            f"Your data is intact in the backups at "
            f"{Path(state['backup_manifest']).parent} and the legacy stores "
            "were not modified. Fix the issues and re-run."
        )
    log("[004] verification passed ✔")
    return state


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase DB migration runner (000→004)."
    )
    parser.add_argument("--db-path", default=None,
                        help="target library.db path (default: ~/.image-toolkit/library.db)")
    parser.add_argument("--legacy-db", default=None,
                        help="legacy listings_secure.db path")
    parser.add_argument("--skip-postgres", action="store_true",
                        help="don't attempt the PostgreSQL migration this run")
    parser.add_argument("--force", action="store_true",
                        help="ignore recorded state and re-run every step")
    args = parser.parse_args()

    import getpass

    password = getpass.getpass("Vault password: ")
    salt = input("Account name (salt): ").strip()

    try:
        run_all(
            password, salt,
            db_path=args.db_path,
            legacy_db_path=args.legacy_db,
            skip_postgres=args.skip_postgres,
            force=args.force,
        )
    except RuntimeError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1
    print("Migration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""004 — Verify the migration (Phase DB, DB.4).

Compares source stores against library.db and checks internal integrity:

* listings: per-category row counts and a full id↔title equality sweep
  against the legacy store (it is small — thousands of rows);
* pgvector: table counts + sampled file_path checks (skipped when the
  server is unreachable, mirroring 003);
* internal: PRAGMA integrity_check + PRAGMA foreign_key_check + a report of
  dangling references parked by 002.

Returns a report with ``ok: False`` and a problem list on any mismatch —
the runner exits non-zero and points at the backups.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.migrations.migrate_listings import LEGACY_DB, _parse_legacy_rows


def _verify_listings(db, password: str, salt: str,
                     legacy_db_path: Optional[str],
                     problems: List[str]) -> Dict[str, Any]:
    import base

    legacy = str(legacy_db_path if legacy_db_path is not None else LEGACY_DB)
    if not Path(legacy).exists():
        return {"skipped": True, "reason": f"legacy DB not found: {legacy}"}

    rows = base.secret.fetch_all_listings_secure(legacy, password, salt)
    media_entries, entity_entries = _parse_legacy_rows(rows)

    media_count = db.query("SELECT count(*) FROM media_items", ())[0][0]
    entity_count = db.query("SELECT count(*) FROM entities", ())[0][0]
    if media_count < len(media_entries):
        problems.append(
            f"media_items count {media_count} < legacy content rows "
            f"{len(media_entries)}"
        )
    if entity_count < len(entity_entries):
        problems.append(
            f"entities count {entity_count} < legacy entity rows "
            f"{len(entity_entries)}"
        )

    # Full id/title sweep (cheap at listings scale).
    target_media = dict(db.query("SELECT id, title FROM media_items", ()))
    for entry in media_entries:
        if entry["id"] not in target_media:
            problems.append(f"legacy content row missing: {entry['id']}")
        elif target_media[entry["id"]] != entry.get("title", ""):
            problems.append(
                f"title mismatch for {entry['id']}: "
                f"{target_media[entry['id']]!r} != {entry.get('title', '')!r}"
            )
    target_entities = dict(db.query("SELECT id, name FROM entities", ()))
    for entity in entity_entries:
        if entity["id"] not in target_entities:
            problems.append(f"legacy entity row missing: {entity['id']}")
        elif target_entities[entity["id"]] != entity.get("name", ""):
            problems.append(
                f"name mismatch for {entity['id']}: "
                f"{target_entities[entity['id']]!r} != "
                f"{entity.get('name', '')!r}"
            )

    return {
        "skipped": False,
        "legacy_media": len(media_entries),
        "legacy_entities": len(entity_entries),
        "target_media": media_count,
        "target_entities": entity_count,
    }


def _verify_pgvector(db, problems: List[str],
                     provider=None) -> Dict[str, Any]:
    from backend.migrations.migrate_pgvector import _postgres_provider

    try:
        data = (provider or _postgres_provider)()
    except Exception as e:  # noqa: BLE001 — mirrors 003's skip semantics
        return {"skipped": True, "reason": f"PostgreSQL unreachable: {e}"}

    checks = {
        "images": "SELECT count(*) FROM images",
        "groups": "SELECT count(*) FROM groups",
        "subgroups": "SELECT count(*) FROM subgroups",
        "tags": "SELECT count(*) FROM tags",
    }
    report: Dict[str, Any] = {"skipped": False}
    for key, sql in checks.items():
        source_count = len(list(data.get(key, ())))
        target_count = db.query(sql, ())[0][0]
        report[key] = {"source": source_count, "target": target_count}
        if target_count < source_count:
            problems.append(
                f"{key} count {target_count} < legacy pgvector {source_count}"
            )

    target_paths = {r[0] for r in db.query("SELECT file_path FROM images", ())}
    for row in list(data.get("images", ()))[:1000]:
        if str(row[0]) not in target_paths:
            problems.append(f"legacy image missing from target: {row[0]}")
    return report


def _verify_internal(db, problems: List[str]) -> Dict[str, Any]:
    if not db.integrity_check():
        problems.append("PRAGMA integrity_check failed")
    fk_violations = db.query("PRAGMA foreign_key_check", ())
    if fk_violations:
        problems.append(f"foreign_key_check: {len(fk_violations)} violations")

    dangling: Dict[str, Any] = {}
    for table in ("media_items", "entities"):
        for row_id, extra_raw in db.query(
            f"SELECT id, extra FROM {table} WHERE extra LIKE '%_dangling_%'", ()
        ):
            try:
                extra = json.loads(extra_raw or "{}")
            except (TypeError, ValueError):
                continue
            parked = {k: v for k, v in extra.items() if k.startswith("_dangling_")}
            if parked:
                dangling[f"{table}:{row_id}"] = parked
    return {
        "integrity_ok": not problems,
        "fk_violations": len(fk_violations),
        "dangling_parked": dangling,
    }


def run(
    password: str,
    salt: str,
    db_path: Optional[str] = None,
    legacy_db_path: Optional[str] = None,
    pg_provider=None,
) -> Dict[str, Any]:
    import base

    from backend.src.database.unified import session

    path = str(db_path if db_path is not None else session.DEFAULT_DB_PATH)
    problems: List[str] = []
    db = base.database.Database(path, password, salt)
    try:
        listings = _verify_listings(db, password, salt, legacy_db_path, problems)
        pgvector = _verify_pgvector(db, problems, provider=pg_provider)
        internal = _verify_internal(db, problems)
    finally:
        db.close()

    return {
        "step": "004_verify_migration",
        "ok": not problems,
        "problems": problems,
        "listings": listings,
        "pgvector": pgvector,
        "internal": internal,
    }


def main() -> int:
    import getpass

    password = getpass.getpass("Vault password: ")
    salt = input("Account name (salt): ").strip()
    report = run(password, salt)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

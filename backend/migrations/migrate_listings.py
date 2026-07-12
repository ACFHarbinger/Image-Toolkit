"""002 — Migrate listings_secure.db into library.db (Phase DB, DB.4).

Reads the legacy document store through ``base.secret.fetch_all_listings_secure``
(deliberately the last consumer of that API), explodes each JSON blob into
the normalized tables via the DAL's legacy-dict repos, then links
associations in a second pass so ordering can't drop them. Dangling
association ids (legacy data contains them) are logged AND parked in the
row's ``extra`` under ``_dangling_*`` keys — nothing is silently dropped.

Idempotent: repos upsert by preserved legacy id.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.src.constants import IMAGE_TOOLKIT_DIR
from backend.src.database.unified.entity_repo import EntityRepo
from backend.src.database.unified.media_repo import MediaRepo

LEGACY_DB = str(Path(IMAGE_TOOLKIT_DIR) / "listings_secure.db")


def _parse_legacy_rows(rows) -> Tuple[List[Dict], List[Dict]]:
    """Split raw (id, category, title, metadata_json, date_added) rows into
    media entry dicts and entity dicts, mirroring the subtabs' loaders."""
    media: List[Dict] = []
    entities: List[Dict] = []
    for row in rows:
        id_, category, title, metadata_json, date_added = row
        try:
            item = json.loads(metadata_json)
            if not isinstance(item, dict):
                item = {}
        except (TypeError, ValueError):
            item = {}
        item["id"] = id_
        item["date_added"] = date_added
        if category == "Entity":
            item["name"] = title
            entities.append(item)
        else:
            item["type"] = category
            item["title"] = title
            media.append(item)
    return media, entities


def run(
    password: str,
    salt: str,
    db_path: Optional[str] = None,
    legacy_db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Migrate. Returns a report dict (counts + dangling references)."""
    import base

    from backend.src.database.unified import session

    legacy = str(legacy_db_path if legacy_db_path is not None else LEGACY_DB)
    if not Path(legacy).exists():
        return {
            "step": "002_migrate_listings",
            "skipped": True,
            "reason": f"legacy listings DB not found: {legacy}",
        }

    rows = base.secret.fetch_all_listings_secure(legacy, password, salt)
    media_entries, entity_entries = _parse_legacy_rows(rows)

    path = str(db_path if db_path is not None else session.DEFAULT_DB_PATH)
    db = base.database.Database(path, password, salt)
    dangling: Dict[str, List[str]] = {}
    try:
        session.ensure_schema(db)
        media_repo = MediaRepo(db)
        entity_repo = EntityRepo(db)

        # Pass 1 — rows without associations (so link targets all exist
        # before any link is written).
        for entry in media_entries:
            stripped = {k: v for k, v in entry.items() if k != "associated_entities"}
            media_repo.save_media(stripped)
        for entity in entity_entries:
            stripped = {
                k: v for k, v in entity.items()
                if k not in ("associated_content", "associated_entities")
            }
            entity_repo.save_entity(stripped)

        # Pass 2 — associations. Repos skip dangling targets; detect and
        # park them so nothing is silently lost.
        known_media = {e["id"] for e in media_entries}
        known_entities = {e["id"] for e in entity_entries}

        for entry in media_entries:
            wanted = [str(x) for x in entry.get("associated_entities") or []]
            media_repo.set_entity_links(entry["id"], wanted)
            missing = [x for x in wanted if x not in known_entities]
            if missing:
                dangling[f"media:{entry['id']}"] = missing
                _park_dangling(db, "media_items", entry["id"],
                               "_dangling_associated_entities", missing)

        for entity in entity_entries:
            wanted_content = [str(x) for x in entity.get("associated_content") or []]
            entity_repo.set_media_links(entity["id"], wanted_content)
            missing = [x for x in wanted_content if x not in known_media]

            wanted_peers = [str(x) for x in entity.get("associated_entities") or []]
            entity_repo.set_peer_links(entity["id"], wanted_peers)
            missing_peers = [
                x for x in wanted_peers
                if x not in known_entities or x == entity["id"]
            ]
            if missing or missing_peers:
                dangling[f"entity:{entity['id']}"] = missing + missing_peers
                if missing:
                    _park_dangling(db, "entities", entity["id"],
                                   "_dangling_associated_content", missing)
                if missing_peers:
                    _park_dangling(db, "entities", entity["id"],
                                   "_dangling_associated_entities", missing_peers)

        report = {
            "step": "002_migrate_listings",
            "skipped": False,
            "source_rows": len(rows),
            "media_migrated": len(media_entries),
            "entities_migrated": len(entity_entries),
            "media_in_target": media_repo.count(),
            "entities_in_target": entity_repo.count(),
            "dangling_references": dangling,
        }
    finally:
        db.close()
    return report


def _park_dangling(db, table: str, row_id: str, key: str, ids: List[str]) -> None:
    rows = db.query(f"SELECT extra FROM {table} WHERE id = ?", (row_id,))
    if not rows:
        return
    try:
        extra = json.loads(rows[0][0] or "{}")
    except (TypeError, ValueError):
        extra = {}
    extra[key] = ids
    db.execute(
        f"UPDATE {table} SET extra = ? WHERE id = ?",
        (json.dumps(extra, ensure_ascii=False), row_id),
    )


def main() -> int:
    import getpass

    password = getpass.getpass("Vault password: ")
    salt = input("Account name (salt): ").strip()
    report = run(password, salt)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

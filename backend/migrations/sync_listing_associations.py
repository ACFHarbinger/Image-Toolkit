#!/usr/bin/env python3
"""Backfill two-way associations between content and entity listings.

Before the secure-database migration, associations made on only one side of the
pair (content → entity, entity → content, or entity → entity) were not mirrored
automatically. This script:

1. Creates a timestamped backup of ``listings_secure.db``.
2. Scans every content entry's ``associated_entities`` and every entity entry's
   ``associated_content`` and ``associated_entities``.
3. Adds any missing reverse links so both sides agree.
4. Writes only rows that actually changed.

Rollback restores the database file from a backup created by this script.

Usage:
    python backend/migrations/sync_listing_associations.py \\
        --account-name <vault_account> \\
        [--db-path ~/.image-toolkit/listings_secure.db] \\
        [--dry-run]

    python backend/migrations/sync_listing_associations.py \\
        --rollback ~/.image-toolkit/backups/listings_secure-20260710T120000.db
"""

from __future__ import annotations

import argparse
import getpass
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import base  # noqa: E402
from backend.src.constants import IMAGE_TOOLKIT_DIR  # noqa: E402

DEFAULT_DB_PATH = IMAGE_TOOLKIT_DIR / "listings_secure.db"
DEFAULT_BACKUP_DIR = IMAGE_TOOLKIT_DIR / "backups"


def normalize_id_list(raw: Any) -> List[str]:
    """Coerce associated-ID fields from JSON into a list of non-empty strings."""
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def title_embedding(text: str, dim: int = 1024) -> List[float]:
    """Reproduce the default listing embedding used by the desktop app."""
    embedding = [0.0] * dim
    for i, byte in enumerate(text.encode("utf-8", errors="ignore")):
        if i < dim:
            embedding[i] = byte / 255.0
    return embedding


@dataclass
class AssociationFixPlan:
    """In-memory description of association repairs before persistence."""

    changed_content_ids: Set[str] = field(default_factory=set)
    changed_entity_ids: Set[str] = field(default_factory=set)
    content_to_entity_fixes: List[Tuple[str, str]] = field(default_factory=list)
    entity_to_content_fixes: List[Tuple[str, str]] = field(default_factory=list)
    entity_to_entity_fixes: List[Tuple[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def total_fixes(self) -> int:
        return (
            len(self.content_to_entity_fixes)
            + len(self.entity_to_content_fixes)
            + len(self.entity_to_entity_fixes)
        )


def compute_association_fixes(
    contents: Dict[str, Dict[str, Any]],
    entities: Dict[str, Dict[str, Any]],
) -> AssociationFixPlan:
    """Return the bidirectional association repairs required for *contents*/*entities*."""
    plan = AssociationFixPlan()

    content_entities: Dict[str, Set[str]] = {
        cid: set(normalize_id_list(entry.get("associated_entities")))
        for cid, entry in contents.items()
    }
    entity_content: Dict[str, Set[str]] = {
        eid: set(normalize_id_list(entry.get("associated_content")))
        for eid, entry in entities.items()
    }
    entity_entities: Dict[str, Set[str]] = {
        eid: set(normalize_id_list(entry.get("associated_entities")))
        for eid, entry in entities.items()
    }

    for cid, entity_ids in content_entities.items():
        for eid in entity_ids:
            if eid not in entities:
                plan.warnings.append(
                    f"Content '{contents[cid].get('title', cid)}' ({cid}) "
                    f"references missing entity id '{eid}'"
                )
                continue
            if cid not in entity_content[eid]:
                entity_content[eid].add(cid)
                plan.entity_to_content_fixes.append((eid, cid))
                plan.changed_entity_ids.add(eid)

    for eid, content_ids in entity_content.items():
        for cid in content_ids:
            if cid not in contents:
                plan.warnings.append(
                    f"Entity '{entities[eid].get('name', eid)}' ({eid}) "
                    f"references missing content id '{cid}'"
                )
                continue
            if eid not in content_entities[cid]:
                content_entities[cid].add(eid)
                plan.content_to_entity_fixes.append((cid, eid))
                plan.changed_content_ids.add(cid)

    for eid, peer_ids in entity_entities.items():
        for peer_id in peer_ids:
            if peer_id == eid:
                continue
            if peer_id not in entities:
                plan.warnings.append(
                    f"Entity '{entities[eid].get('name', eid)}' ({eid}) "
                    f"references missing entity id '{peer_id}'"
                )
                continue
            if eid not in entity_entities[peer_id]:
                entity_entities[peer_id].add(eid)
                plan.entity_to_entity_fixes.append((peer_id, eid))
                plan.changed_entity_ids.add(peer_id)

    for cid in plan.changed_content_ids:
        contents[cid]["associated_entities"] = sorted(content_entities[cid])

    for eid in plan.changed_entity_ids:
        entities[eid]["associated_content"] = sorted(entity_content[eid])
        entities[eid]["associated_entities"] = sorted(entity_entities[eid])

    return plan


def load_listings(
    db_path: str, password: str, salt: str
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Load content and entity rows from the secure listings database."""
    contents: Dict[str, Dict[str, Any]] = {}
    entities: Dict[str, Dict[str, Any]] = {}

    rows = base.fetch_all_listings_secure(db_path, password, salt)  # pyrefly: ignore [missing-attribute]
    for row in rows:
        id_, category, title, metadata_json, date_added = row
        try:
            record = json.loads(metadata_json)
        except json.JSONDecodeError:
            record = {}

        record["id"] = id_
        record["date_added"] = date_added

        if category == "Entity":
            record["name"] = title
            entities[str(id_)] = record
        else:
            record["type"] = category
            record["title"] = title
            contents[str(id_)] = record

    return contents, entities


def backup_database(db_path: Path, backup_dir: Path) -> Path:
    """Copy the listings database to *backup_dir* and return the backup path."""
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
        "script": "sync_listing_associations.py",
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


def upsert_content_entry(
    db_path: str, password: str, salt: str, entry: Dict[str, Any]
) -> None:
    base.insert_listing_secure(  # pyrefly: ignore [missing-attribute]
        db_path,
        password,
        salt,
        entry["id"],
        entry.get("type", "Other"),
        entry.get("title", ""),
        json.dumps(dict(entry), ensure_ascii=False),
        entry.get("date_added", ""),
        title_embedding(entry.get("title", "")),
    )


def upsert_entity_entry(
    db_path: str, password: str, salt: str, entity: Dict[str, Any]
) -> None:
    base.insert_listing_secure(  # pyrefly: ignore [missing-attribute]
        db_path,
        password,
        salt,
        entity["id"],
        "Entity",
        entity.get("name", ""),
        json.dumps(dict(entity), ensure_ascii=False),
        entity.get("date_added", ""),
        title_embedding(entity.get("name", "")),
    )


def apply_association_fixes(
    db_path: str,
    password: str,
    salt: str,
    contents: Dict[str, Dict[str, Any]],
    entities: Dict[str, Dict[str, Any]],
    plan: AssociationFixPlan,
) -> None:
    """Persist association repairs to the secure listings database."""
    for cid in sorted(plan.changed_content_ids):
        upsert_content_entry(db_path, password, salt, contents[cid])

    for eid in sorted(plan.changed_entity_ids):
        upsert_entity_entry(db_path, password, salt, entities[eid])


def print_plan(
    plan: AssociationFixPlan,
    contents: Dict[str, Dict[str, Any]],
    entities: Dict[str, Dict[str, Any]],
) -> None:
    print(f"Planned association fixes: {plan.total_fixes}")
    for cid, eid in plan.content_to_entity_fixes:
        title = contents[cid].get("title", cid)
        entity_name = entities.get(eid, {}).get("name", eid)
        print(f"  + content '{title}' ({cid}) → entity '{entity_name}' ({eid})")
    for eid, cid in plan.entity_to_content_fixes:
        entity_name = entities[eid].get("name", eid)
        title = contents.get(cid, {}).get("title", cid)
        print(f"  + entity '{entity_name}' ({eid}) → content '{title}' ({cid})")
    for peer_id, eid in plan.entity_to_entity_fixes:
        peer_name = entities.get(peer_id, {}).get("name", peer_id)
        entity_name = entities.get(eid, {}).get("name", eid)
        print(
            f"  + entity '{peer_name}' ({peer_id}) → entity '{entity_name}' ({eid})"
        )

    if plan.warnings:
        print(f"\nWarnings ({len(plan.warnings)}):")
        for warning in plan.warnings:
            print(f"  ! {warning}")


def run_migration(
    db_path: Path,
    password: str,
    salt: str,
    backup_dir: Path,
    dry_run: bool,
) -> int:
    contents, entities = load_listings(str(db_path), password, salt)
    plan = compute_association_fixes(contents, entities)

    print(
        f"Loaded {len(contents)} content entries and {len(entities)} entity entries."
    )
    print_plan(plan, contents, entities)

    if plan.total_fixes == 0:
        print("No association repairs needed.")
        return 0

    if dry_run:
        print("\nDry run — no backup created and no database changes written.")
        return 0

    backup_path = backup_database(db_path, backup_dir)
    print(f"\nBackup created: {backup_path}")
    apply_association_fixes(str(db_path), password, salt, contents, entities, plan)
    print(
        f"Updated {len(plan.changed_content_ids)} content entries and "
        f"{len(plan.changed_entity_ids)} entity entries."
    )
    print(
        "To roll back, run:\n"
        f"  python {Path(__file__).as_posix()} --rollback {backup_path}"
    )
    return 0


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill missing two-way associations between content listings, "
            "entity listings, and peer entity links in listings_secure.db."
        )
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to listings_secure.db (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=DEFAULT_BACKUP_DIR,
        help=f"Directory for database backups (default: {DEFAULT_BACKUP_DIR})",
    )
    parser.add_argument(
        "--account-name",
        help="Vault account name used as the SQLCipher salt (required unless --rollback).",
    )
    parser.add_argument(
        "--password",
        help="Vault password. Prompted securely when omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned fixes without creating a backup or writing changes.",
    )
    parser.add_argument(
        "--rollback",
        type=Path,
        metavar="BACKUP_PATH",
        help="Restore listings_secure.db from a backup created by this script.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)

    if args.rollback:
        restore_database(args.rollback, args.db_path)
        print(f"Restored database from {args.rollback} → {args.db_path}")
        return 0

    if not args.account_name:
        print("Error: --account-name is required unless using --rollback.", file=sys.stderr)
        return 2

    password = args.password or getpass.getpass("Vault password: ")
    if not password:
        print("Error: password is required.", file=sys.stderr)
        return 2

    try:
        return run_migration(
            db_path=args.db_path,
            password=password,
            salt=args.account_name,
            backup_dir=args.backup_dir,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
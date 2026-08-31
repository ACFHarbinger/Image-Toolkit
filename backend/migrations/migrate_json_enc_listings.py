"""Standalone migration — move the legacy ``listings.json.enc`` / ``entities.json.enc``
vault-encrypted stores into ``library.db`` (Phase DB).

These two files (``~/.image-toolkit/{listings,entities}.json.enc``) are the
*pre-DB* primary store, encrypted with the account's vault secret key. The
current subtabs read the unified library DB and never touch these anymore,
so anything only in them is invisible to the app. This migration:

  1. derives the account's vault secret key and decrypts both files;
  2. upserts every entry into the normalized tables — pass 1 writes the rows
     with associations stripped, pass 2 (re)links media<->entity and
     entity<->entity so cross-references resolve regardless of insert order
     (``MediaRepo`` / ``EntityRepo`` upsert by preserved legacy ``id`` and
     silently skip links to ids that don't exist — idempotent, re-runnable);
  3. verifies every source ``id`` is retrievable from the DB;
  4. only on a clean verification (``--delete``) removes the two files.

Run:
    python -m backend.migrations.migrate_json_enc_listings --account a
    python -m backend.migrations.migrate_json_enc_listings --account a --delete
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.src.constants import IMAGE_TOOLKIT_DIR

LISTINGS_ENC = str(Path(IMAGE_TOOLKIT_DIR) / "listings.json.enc")
ENTITIES_ENC = str(Path(IMAGE_TOOLKIT_DIR) / "entities.json.enc")

# association keys handled in pass 2, stripped from the pass-1 upsert dict
_MEDIA_ASSOC = ("associated_entities",)
_ENTITY_ASSOC = ("associated_content", "associated_entities")


# --------------------------------------------------------------------------- #
# decrypt
# --------------------------------------------------------------------------- #
def _secret_key(account_name: str, password: str) -> bytes:
    """Derive this account's vault secret key (same steps as the login flow)."""
    import backend.src.constants.crypto as udef
    from backend.src.core.vault_manager import VaultManager

    udef.update_cryptographic_values(account_name)
    vm = VaultManager()
    vm.load_keystore(udef.KEYSTORE_FILE, password)
    vm.get_secret_key(udef.KEY_ALIAS, password)
    if not vm.secret_key:
        raise RuntimeError(
            f"could not derive a secret key for account '{account_name}' "
            "(wrong password or missing keystore)"
        )
    return vm.secret_key


def _load_enc_list(secret_key: bytes, path: str) -> List[Dict[str, Any]]:
    """Decrypt one .json.enc file → list[dict] (tolerates {}, [], {'entries': [...]})."""
    from backend.src.core.vault_manager import SecureJsonVault

    if not os.path.exists(path):
        return []
    raw = SecureJsonVault(secret_key, path).loadData()
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{path}: decrypted content is not JSON: {exc}") from exc
    if isinstance(data, dict):
        for key in ("entries", "listings", "entities", "data", "items"):
            if isinstance(data.get(key), list):
                return [d for d in data[key] if isinstance(d, dict)]
        return []
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return []


# --------------------------------------------------------------------------- #
# migrate
# --------------------------------------------------------------------------- #
def run(
    account_name: str,
    password: str,
    listings_enc: Optional[str] = None,
    entities_enc: Optional[str] = None,
    db_path: Optional[str] = None,
    delete_on_success: bool = False,
) -> Dict[str, Any]:
    import base  # noqa: F401  (ensures the native extension is importable)

    from backend.src.database.unified import session
    from backend.src.database.unified.entity_repo import EntityRepo
    from backend.src.database.unified.media_repo import MediaRepo

    listings_enc = listings_enc or LISTINGS_ENC
    entities_enc = entities_enc or ENTITIES_ENC

    key = _secret_key(account_name, password)
    media_entries = [
        e for e in _load_enc_list(key, listings_enc) if e.get("id") not in (None, "")
    ]
    entity_entries = [
        e for e in _load_enc_list(key, entities_enc) if e.get("id") not in (None, "")
    ]
    media_ids = {str(e["id"]) for e in media_entries}
    entity_ids = {str(e["id"]) for e in entity_entries}

    close_after = not session.is_open()
    db = session.open_session(password, account_name, db_path=db_path)
    dangling: Dict[str, List[str]] = {}
    try:
        session.ensure_schema(db)
        media_repo = MediaRepo(db)
        entity_repo = EntityRepo(db)

        # pass 1 — rows without associations
        for e in media_entries:
            media_repo.save_media({k: v for k, v in e.items() if k not in _MEDIA_ASSOC})
        for e in entity_entries:
            entity_repo.save_entity({k: v for k, v in e.items() if k not in _ENTITY_ASSOC})

        # pass 2 — associations; repos skip ids that don't exist, so record
        # any reference that points outside the migrated set (never dropped
        # silently — the owning row is still written, only the link is lost).
        for e in media_entries:
            wanted = [str(x) for x in e.get("associated_entities") or []]
            media_repo.set_entity_links(str(e["id"]), wanted)
            missing = [x for x in wanted if x not in entity_ids]
            if missing:
                dangling[f"media:{e['id']} -> entities"] = missing

        for e in entity_entries:
            eid = str(e["id"])
            w_content = [str(x) for x in e.get("associated_content") or []]
            w_peers = [str(x) for x in e.get("associated_entities") or []]
            entity_repo.set_media_links(eid, w_content)
            entity_repo.set_peer_links(eid, w_peers)
            miss_c = [x for x in w_content if x not in media_ids]
            miss_p = [x for x in w_peers if x != eid and x not in entity_ids]
            if miss_c:
                dangling[f"entity:{eid} -> content"] = miss_c
            if miss_p:
                dangling[f"entity:{eid} -> peers"] = miss_p

        # ---- verify every source id is now retrievable ----
        missing_media = sorted(i for i in media_ids if media_repo.get_media(i) is None)
        missing_entities = sorted(
            i for i in entity_ids if entity_repo.get_entity(i) is None
        )
        verified = not missing_media and not missing_entities

        report: Dict[str, Any] = {
            "step": "migrate_json_enc_listings",
            "account": account_name,
            "listings_enc": listings_enc,
            "entities_enc": entities_enc,
            "media_in_source": len(media_entries),
            "entities_in_source": len(entity_entries),
            "media_in_target": media_repo.count(),
            "entities_in_target": entity_repo.count(),
            "missing_media_ids": missing_media,
            "missing_entity_ids": missing_entities,
            "dangling_references": dangling,
            "verified": verified,
            "deleted": [],
        }

        if delete_on_success and verified:
            for p in (listings_enc, entities_enc):
                if os.path.exists(p):
                    os.remove(p)
                    report["deleted"].append(p)
        elif delete_on_success and not verified:
            report["delete_skipped_reason"] = "verification failed — files kept"
    finally:
        if close_after:
            session.close_session()
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Migrate ~/.image-toolkit/{listings,entities}.json.enc into library.db"
    )
    ap.add_argument("--account", required=True, help="account name (also the DB salt)")
    ap.add_argument("--password", help="vault password (prompted if omitted)")
    ap.add_argument("--listings-enc", default=None)
    ap.add_argument("--entities-enc", default=None)
    ap.add_argument("--db-path", default=None)
    ap.add_argument(
        "--delete",
        action="store_true",
        help="delete the two .json.enc files after a verified migration",
    )
    args = ap.parse_args(argv)

    password = args.password
    if password is None:
        import getpass

        password = getpass.getpass(f"Vault password for '{args.account}': ")

    report = run(
        account_name=args.account,
        password=password,
        listings_enc=args.listings_enc,
        entities_enc=args.entities_enc,
        db_path=args.db_path,
        delete_on_success=args.delete,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())

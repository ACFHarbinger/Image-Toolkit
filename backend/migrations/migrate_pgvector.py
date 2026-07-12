"""003 — Migrate the PostgreSQL image index into library.db (Phase DB, DB.4).

Streams groups/subgroups/tags/images/image_tags out of the legacy pgvector
database and writes them into the unified store, resolving the denormalized
``group_name``/``subgroup_name`` text columns to FKs and preserving original
dates and pHashes. The legacy ``embedding`` column is ignored (NULL on every
GUI-written row; real embeddings arrive in DB.7).

Skippable by design: when psycopg2 is missing or the server is unreachable
the step returns ``{"skipped": True, ...}`` with a loud reason — it can be
re-run later; nothing else depends on it (roadmap risk register).

Idempotent: images upsert by file_path; vocabulary rows by name.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from backend.src.constants import ROOT_DIR

ENV_FILE = Path(ROOT_DIR) / "env" / "vars.env"

# Data provider contract: () -> dict with keys
#   groups:      iterable of (name,)
#   subgroups:   iterable of (subgroup_name, group_name)
#   tags:        iterable of (name, type_or_None)
#   images:      iterable of (file_path, filename, file_size, width, height,
#                             group_name, subgroup_name, date_added,
#                             date_modified, phash)
#   image_tags:  iterable of (file_path, tag_name)
DataProvider = Callable[[], Dict[str, Iterable[tuple]]]


def _load_pg_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key.strip().startswith("DB_"):
                    env[key.strip()] = value.strip()
    # Environment variables override the file.
    for key in ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def _postgres_provider() -> Dict[str, Iterable[tuple]]:
    """Default provider — the only surviving psycopg2 call site (guarded)."""
    import psycopg2  # deferred + guarded: package may be absent post-DB.6

    pg = _load_pg_env()
    conn = psycopg2.connect(
        dbname=pg.get("DB_NAME"),
        user=pg.get("DB_USER"),
        password=pg.get("DB_PASSWORD"),
        host=pg.get("DB_HOST"),
        port=pg.get("DB_PORT"),
        connect_timeout=10,
    )

    def fetch(sql: str):
        with conn.cursor() as cur:
            cur.execute(sql)
            while True:
                rows = cur.fetchmany(1000)
                if not rows:
                    break
                yield from rows

    return {
        "groups": list(fetch("SELECT name FROM groups")),
        "subgroups": list(fetch(
            "SELECT s.name, g.name FROM subgroups s "
            "JOIN groups g ON g.id = s.group_id"
        )),
        "tags": list(fetch("SELECT name, type FROM tags")),
        "images": list(fetch(
            "SELECT file_path, filename, COALESCE(file_size, 0), width, "
            "height, group_name, subgroup_name, date_added, date_modified, "
            "phash FROM images"
        )),
        "image_tags": list(fetch(
            "SELECT i.file_path, t.name FROM image_tags it "
            "JOIN images i ON i.id = it.image_id "
            "JOIN tags t ON t.id = it.tag_id"
        )),
    }


def run(
    password: str,
    salt: str,
    db_path: Optional[str] = None,
    provider: Optional[DataProvider] = None,
) -> Dict[str, Any]:
    """Migrate. Returns a report dict; skips gracefully when Postgres is out."""
    import base

    from backend.src.database.unified import session
    from backend.src.database.unified.image_repo import ImageRepo
    from backend.src.database.unified.tag_repo import TagRepo

    try:
        data = (provider or _postgres_provider)()
    except ImportError as e:
        return {"step": "003_migrate_pgvector", "skipped": True,
                "reason": f"psycopg2 unavailable: {e}"}
    except Exception as e:  # noqa: BLE001 — any connection failure = skip
        return {"step": "003_migrate_pgvector", "skipped": True,
                "reason": f"PostgreSQL unreachable: {e}"}

    path = str(db_path if db_path is not None else session.DEFAULT_DB_PATH)
    db = base.database.Database(path, password, salt)
    counts = {"groups": 0, "subgroups": 0, "tags": 0, "images": 0,
              "image_tags": 0}
    try:
        session.ensure_schema(db)
        images = ImageRepo(db)
        tags = TagRepo(db)

        db.begin()
        try:
            for (name,) in data.get("groups", ()):
                if name and name.strip():
                    images.add_group(name)
                    counts["groups"] += 1
            for sub_name, group_name in data.get("subgroups", ()):
                if sub_name and group_name:
                    images.add_subgroup(sub_name, group_name)
                    counts["subgroups"] += 1
            for name, type_ in data.get("tags", ()):
                if name and name.strip():
                    tags.add_tag(name, type_)
                    counts["tags"] += 1

            for (file_path, filename, file_size, width, height, group_name,
                 subgroup_name, date_added, date_modified, phash) in data.get(
                    "images", ()):
                group_id = (
                    images.add_group(group_name)
                    if group_name and str(group_name).strip() else None
                )
                subgroup_id = (
                    images.add_subgroup(subgroup_name, group_name)
                    if group_id is not None and subgroup_name
                    and str(subgroup_name).strip() else None
                )
                # Direct upsert (not ImageRepo.add_image) to preserve the
                # original date_added/date_modified timestamps.
                db.execute(
                    "INSERT INTO images (file_path, filename, file_size, "
                    "width, height, phash, group_id, subgroup_id, "
                    "date_added, date_modified) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(file_path) DO UPDATE SET "
                    "filename=excluded.filename, "
                    "file_size=excluded.file_size, "
                    "width=excluded.width, height=excluded.height, "
                    "phash=excluded.phash, group_id=excluded.group_id, "
                    "subgroup_id=excluded.subgroup_id, "
                    "date_added=excluded.date_added, "
                    "date_modified=excluded.date_modified",
                    (str(file_path), str(filename), int(file_size or 0),
                     width, height, phash, group_id, subgroup_id,
                     str(date_added) if date_added is not None else None,
                     str(date_modified) if date_modified is not None else None),
                )
                counts["images"] += 1

            for file_path, tag_name in data.get("image_tags", ()):
                changed = db.execute(
                    "INSERT OR IGNORE INTO image_tags (image_id, tag_id) "
                    "SELECT i.id, t.id FROM images i, tags t "
                    "WHERE i.file_path = ? AND t.name = ?",
                    (str(file_path), str(tag_name)),
                )
                counts["image_tags"] += changed
        except Exception:
            db.rollback()
            raise
        db.commit()

        report = {
            "step": "003_migrate_pgvector",
            "skipped": False,
            "migrated": counts,
            "images_in_target": images.count(),
        }
    finally:
        db.close()
    return report


def main() -> int:
    import getpass

    password = getpass.getpass("Vault password: ")
    salt = input("Account name (salt): ").strip()
    report = run(password, salt)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not report.get("skipped") else 2


if __name__ == "__main__":
    sys.exit(main())

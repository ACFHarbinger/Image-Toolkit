"""Media items (series listings) repository — DB.3.

Speaks the *legacy entry-dict* dialect the Listings subtabs already use
(`title`, `type`, `status`, CSV `genres`/`tags`, `associated_entities`,
`episode_list`, …) so the DB.5 tab port and migration 002 are drop-in:
``save_media(legacy_dict)`` explodes it into the normalized tables inside
one transaction; ``get_media``/``list_media`` reassemble it.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from ._util import (
    dumps_extra,
    intify,
    join_csv,
    loads_extra,
    split_csv,
    tag_bucket_clause,
    transaction,
)
from .tag_repo import TagRepo
from backend.src.constants.database import UNIFIED__COLUMN_KEYS, UNIFIED__RELATION_KEYS, UNIFIED__SELECT_COLUMNS, _EPISODE_FIELDS

# Legacy entry key -> media_items column (identical names omitted).
# Keys consumed by relations, not columns.


class MediaRepo:
    def __init__(self, db):
        self._db = db
        self._tags = TagRepo(db)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def save_media(self, entry: Dict[str, Any]) -> str:
        """Upsert a legacy-shaped content entry in one transaction."""
        entry = dict(entry)
        media_id = entry.get("id") or str(uuid.uuid4())
        entry["id"] = media_id
        entry.setdefault("date_added", str(date.today()))

        cols: Dict[str, Any] = {}
        extra: Dict[str, Any] = {}
        for key, value in entry.items():
            if key in UNIFIED__COLUMN_KEYS:
                cols[UNIFIED__COLUMN_KEYS[key]] = value
            elif key not in UNIFIED__RELATION_KEYS:
                extra[key] = value

        with transaction(self._db):
            column_names = list(cols) + ["extra"]
            placeholders = ", ".join("?" * len(column_names))
            updates = ", ".join(
                f"{c}=excluded.{c}" for c in column_names if c != "id"
            )
            self._db.execute(
                f"INSERT INTO media_items ({', '.join(column_names)}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}",
                tuple(cols.values()) + (dumps_extra(extra),),
            )

            if "episode_list" in entry:
                self._replace_episodes(media_id, entry.get("episode_list") or [])
            if "genres" in entry:
                self._replace_typed_tags(media_id, "Genre", split_csv(entry.get("genres")))
            if "tags" in entry:
                self._replace_typed_tags(media_id, "Tag", split_csv(entry.get("tags")))
            if "associated_entities" in entry:
                self._replace_entity_links(
                    media_id, list(entry.get("associated_entities") or [])
                )

            # Every series/content listing gets a self tag under Copyright
            # (this app's name for Danbooru's "franchise" category) so it's
            # part of the searchable vocabulary and shows up on linked
            # entities' grouped-tags section as an "associated series" chip.
            title = (entry.get("title") or cols.get("title") or "").strip()
            if title:
                self_tag_id = self._tags.get_or_create(title, "Copyright")
                self._db.execute(
                    "INSERT OR IGNORE INTO media_tags (media_item_id, tag_id) "
                    "VALUES (?, ?)",
                    (media_id, self_tag_id),
                )
        return media_id

    def delete_media(self, media_id: str) -> bool:
        """Delete an entry; episodes/associations/tag links cascade."""
        return self._db.execute(
            "DELETE FROM media_items WHERE id = ?", (media_id,)
        ) > 0

    def set_entity_links(self, media_id: str, entity_ids: List[str]) -> None:
        with transaction(self._db):
            self._replace_entity_links(media_id, entity_ids)

    # ---- DB.8a: media <-> image groups -----------------------------------

    def link_group(self, media_id: str, group_id: int) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO media_groups (media_item_id, group_id) "
            "VALUES (?, ?)",
            (media_id, group_id),
        )

    def unlink_group(self, media_id: str, group_id: int) -> None:
        self._db.execute(
            "DELETE FROM media_groups WHERE media_item_id = ? AND group_id = ?",
            (media_id, group_id),
        )

    def get_linked_groups(self, media_id: str) -> List[Dict[str, Any]]:
        """[{"id": group_id, "name": group_name}, ...] linked to *media_id*."""
        rows = self._db.query(
            "SELECT g.id, g.name FROM media_groups mg "
            "JOIN groups g ON g.id = mg.group_id "
            "WHERE mg.media_item_id = ? ORDER BY g.name",
            (media_id,),
        )
        return [{"id": r[0], "name": r[1]} for r in rows]

    def get_media_for_group(self, group_id: int) -> List[Dict[str, Any]]:
        """Media items (id/title) linked to *group_id* -- the reverse of
        get_linked_groups(), e.g. for a group's "linked series" panel."""
        rows = self._db.query(
            "SELECT m.id, m.title FROM media_groups mg "
            "JOIN media_items m ON m.id = mg.media_item_id "
            "WHERE mg.group_id = ? ORDER BY m.title",
            (group_id,),
        )
        return [{"id": r[0], "title": r[1]} for r in rows]

    def suggest_group_matches(self, title: str, all_group_names: List[str]) -> List[str]:
        """Fuzzy title<->group-name candidates for the "auto-suggest links"
        UI action -- case/whitespace-insensitive substring match either
        direction, ranked by match length (longest/most-specific first).
        Deliberately simple (no fuzzy-distance library dependency); good
        enough for suggesting, since a human always confirms before
        link_group() is actually called."""
        norm_title = " ".join(title.lower().split())
        if not norm_title:
            return []
        scored = []
        for name in all_group_names:
            norm_name = " ".join(name.lower().split())
            if not norm_name:
                continue
            if norm_name in norm_title or norm_title in norm_name:
                scored.append((len(norm_name), name))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [name for _, name in scored]

    # ---- DB.7: listings semantic search (BGE-M3) ------------------------

    def upsert_embedding(self, media_id: str, model: str, vector) -> None:
        """Store *vector* for this media item under *model* -- mirrors
        ImageRepo.upsert_embedding (image_repo.py)."""
        import numpy as np

        self._db.upsert_embedding(
            "media_item", media_id, model, np.asarray(vector, dtype=np.float32)
        )

    def count_unembedded(self, model: str) -> int:
        return self._db.query(
            "SELECT COUNT(*) FROM media_items m WHERE NOT EXISTS ("
            "SELECT 1 FROM embeddings e WHERE e.owner_type = 'media_item' "
            "AND e.owner_id = m.id AND e.model = ?)",
            (model,),
        )[0][0]

    def list_unembedded(self, model: str, limit: int = 500) -> List[Tuple[str, str]]:
        """[(media_id, title), ...] for media items with no *model*
        embedding yet -- the backfill worker's work queue."""
        return self._db.query(
            "SELECT m.id, m.title FROM media_items m WHERE NOT EXISTS ("
            "SELECT 1 FROM embeddings e WHERE e.owner_type = 'media_item' "
            "AND e.owner_id = m.id AND e.model = ?) "
            "ORDER BY m.id LIMIT ?",
            (model, limit),
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_media(self, media_id: str) -> Optional[Dict[str, Any]]:
        rows = self._db.query(
            f"SELECT {', '.join(UNIFIED__SELECT_COLUMNS)} FROM media_items WHERE id = ?",
            (media_id,),
        )
        if not rows:
            return None
        return self._assemble(rows[0])

    def list_media(self) -> List[Dict[str, Any]]:
        rows = self._db.query(
            f"SELECT {', '.join(UNIFIED__SELECT_COLUMNS)} FROM media_items "
            "ORDER BY date_added DESC, title",
            (),
        )
        return [self._assemble(row) for row in rows]

    def list_ids_and_titles(self) -> List[tuple]:
        return self._db.query("SELECT id, title FROM media_items ORDER BY title", ())

    def count(self) -> int:
        return self._db.query("SELECT count(*) FROM media_items", ())[0][0]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _assemble(self, row: tuple) -> Dict[str, Any]:
        data = dict(zip(UNIFIED__SELECT_COLUMNS, row, strict=False))
        media_id = data["id"]

        entry: Dict[str, Any] = loads_extra(data.pop("extra"))
        reverse = {col: key for key, col in UNIFIED__COLUMN_KEYS.items()}
        for col, value in data.items():
            entry[reverse[col]] = intify(value)

        entry["genres"] = join_csv(self._typed_tags(media_id, "Genre"))
        entry["tags"] = join_csv(self._typed_tags(media_id, "Tag"))
        entry["associated_entities"] = [
            r[0] for r in self._db.query(
                "SELECT entity_id FROM media_entity WHERE media_item_id = ? "
                "ORDER BY entity_id",
                (media_id,),
            )
        ]
        entry["episode_list"] = [
            dict(zip(("id",) + _EPISODE_FIELDS, map(intify, ep_row), strict=False))
            for ep_row in self._db.query(
                f"SELECT id, {', '.join(_EPISODE_FIELDS)} FROM episodes "
                "WHERE media_item_id = ? "
                "ORDER BY number IS NULL, number, id",
                (media_id,),
            )
        ]
        return entry

    # The unified vocabulary has UNIQUE tag names, so a name saved from a
    # listing CSV may already exist with an image-side category (Artist,
    # General, …). 'Genre' links reconstruct the genres CSV; every other
    # link reconstructs the tags CSV — this keeps round-trips stable even
    # when a name's category was claimed by another domain. See
    # _util.tag_bucket_clause for the shared 'Genre'/'Tag' bucket logic
    # (also used by search_repo.py's tag-filter search).

    def _typed_tags(self, media_id: str, tag_category: str) -> List[str]:
        return [
            r[0] for r in self._db.query(
                "SELECT t.name FROM media_tags mt JOIN tags t ON t.id = mt.tag_id "
                "LEFT JOIN tag_categories c ON c.id = t.category_id "
                f"WHERE mt.media_item_id = ? AND {tag_bucket_clause(tag_category)} "
                "ORDER BY t.name",
                (media_id,),
            )
        ]

    def get_grouped_tags(self, media_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """This media's tags grouped by category name, including tags
        carried transitively through associated entities (e.g. an actor's
        Appearance tags become visible/searchable on the series they're
        linked to). {"General": [{"name": ..., "color": ...}, ...], ...}."""
        rows = self._db.query(
            "SELECT t.name, COALESCE(c.name, 'General') AS cat, "
            "COALESCE(c.color, '#95a5a6') AS color, COALESCE(c.sort_order, 999) AS ord "
            "FROM media_tags mt JOIN tags t ON t.id = mt.tag_id "
            "LEFT JOIN tag_categories c ON c.id = t.category_id "
            "WHERE mt.media_item_id = ? "
            "UNION "
            "SELECT t.name, COALESCE(c.name, 'General') AS cat, "
            "COALESCE(c.color, '#95a5a6') AS color, COALESCE(c.sort_order, 999) AS ord "
            "FROM media_entity me JOIN entity_tags et ON et.entity_id = me.entity_id "
            "JOIN tags t ON t.id = et.tag_id "
            "LEFT JOIN tag_categories c ON c.id = t.category_id "
            "WHERE me.media_item_id = ? "
            "ORDER BY ord, t.name",
            (media_id, media_id),
        )
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for name, category, color, _order in rows:
            grouped.setdefault(category, []).append({"name": name, "color": color})
        return grouped

    def add_tag(self, media_id: str, name: str, category: Optional[str] = None) -> None:
        """Attach an arbitrary tag (any category) to this media item --
        the "+" add-tag action in the grouped-tags UI section. Unlike
        _replace_typed_tags, this doesn't touch any other tag link."""
        tag_id = self._tags.get_or_create(name, category)
        self._db.execute(
            "INSERT OR IGNORE INTO media_tags (media_item_id, tag_id) VALUES (?, ?)",
            (media_id, tag_id),
        )

    def _replace_episodes(self, media_id: str, episode_list: List[Dict[str, Any]]) -> None:
        self._db.execute("DELETE FROM episodes WHERE media_item_id = ?", (media_id,))
        if not episode_list:
            return
        rows = []
        for ep in episode_list:
            rows.append(
                (
                    ep.get("id") or str(uuid.uuid4()),
                    media_id,
                    ep.get("number"),
                    ep.get("title", "") or "",
                    ep.get("date_watched", "") or "",
                    ep.get("rating", 0) or 0,
                    ep.get("review", "") or "",
                    ep.get("image_path", "") or "",
                    ep.get("local_file", "") or "",
                    ep.get("web_link", "") or "",
                )
            )
        self._db.executemany(
            "INSERT INTO episodes (id, media_item_id, number, title, "
            "date_watched, rating, review, image_path, local_file, web_link) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    def _replace_typed_tags(self, media_id: str, tag_category: str, names: List[str]) -> None:
        """Replace this entry's links to tags of *tag_category* (others untouched)."""
        self._db.execute(
            "DELETE FROM media_tags WHERE media_item_id = ? AND tag_id IN "
            "(SELECT t.id FROM tags t LEFT JOIN tag_categories c ON c.id = t.category_id "
            f"WHERE {tag_bucket_clause(tag_category)})",
            (media_id,),
        )
        for name in names:
            tag_id = self._tags.get_or_create(name, tag_category)
            self._db.execute(
                "INSERT OR IGNORE INTO media_tags (media_item_id, tag_id) "
                "VALUES (?, ?)",
                (media_id, tag_id),
            )

    def _replace_entity_links(self, media_id: str, entity_ids: List[str]) -> None:
        """Replace media↔entity links; unknown entity ids are skipped
        (legacy data contains dangling references — migration 002 logs them)."""
        self._db.execute(
            "DELETE FROM media_entity WHERE media_item_id = ?", (media_id,)
        )
        for entity_id in entity_ids:
            self._db.execute(
                "INSERT OR IGNORE INTO media_entity (media_item_id, entity_id) "
                "SELECT ?, id FROM entities WHERE id = ?",
                (media_id, entity_id),
            )

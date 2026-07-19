"""Search queries — DB.3 / DB.5 / DB.7.

Structured image search (PgvectorImageDatabase.search_images parity), FTS5
text search with LIKE fallback, the advanced-listings-search SQL builder,
and knn wrappers that compose vector search with the structured filters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import session
from ._util import sql_string_literal

_IMAGE_SELECT = (
    "SELECT DISTINCT i.id, i.file_path, i.filename, i.file_size, i.width, "
    "i.height, i.phash, g.name AS group_name, s.name AS subgroup_name, "
    "i.date_added, i.date_modified "
    "FROM images i "
    "LEFT JOIN groups g ON g.id = i.group_id "
    "LEFT JOIN subgroups s ON s.id = i.subgroup_id "
)
_IMAGE_COLUMNS = (
    "id", "file_path", "filename", "file_size", "width", "height", "phash",
    "group_name", "subgroup_name", "date_added", "date_modified",
)


def _like(fragment: str) -> str:
    return f"%{fragment}%"


class SearchRepo:
    def __init__(self, db):
        self._db = db
        self._fts: Optional[bool] = None

    @property
    def fts_enabled(self) -> bool:
        if self._fts is None:
            self._fts = session.fts_enabled(self._db)
        return self._fts

    # ------------------------------------------------------------------
    # Structured image search (Search tab)
    # ------------------------------------------------------------------

    def _image_filter_sql(
        self,
        group_name: Optional[str],
        subgroup_name: Optional[str],
        tags: Optional[Sequence[str]],
        filename_pattern: Optional[str],
        input_formats: Optional[Sequence[str]],
        group_names: Optional[Sequence[str]] = None,
        subgroup_names: Optional[Sequence[str]] = None,
    ) -> Tuple[str, list]:
        conditions: List[str] = []
        params: list = []

        if tags:
            marks = ",".join("?" * len(tags))
            conditions.append(
                "i.id IN (SELECT it.image_id FROM image_tags it "
                f"JOIN tags t ON t.id = it.tag_id WHERE t.name IN ({marks}))"
            )
            params.extend(tags)

        # Multi-select group filter (OR logic)
        effective_groups: List[str] = list(group_names or [])
        if not effective_groups and group_name:
            effective_groups = [group_name]
        if effective_groups:
            or_clauses = ["g.name = ? COLLATE NOCASE" for _ in effective_groups]
            conditions.append("(" + " OR ".join(or_clauses) + ")")
            params.extend(effective_groups)

        # Multi-select subgroup filter (OR logic)
        effective_subgroups: List[str] = list(subgroup_names or [])
        if not effective_subgroups and subgroup_name:
            effective_subgroups = [subgroup_name]
        if effective_subgroups:
            or_clauses = ["s.name = ? COLLATE NOCASE" for _ in effective_subgroups]
            conditions.append("(" + " OR ".join(or_clauses) + ")")
            params.extend(effective_subgroups)

        if filename_pattern:
            conditions.append("i.filename LIKE ? COLLATE NOCASE")
            params.append(_like(filename_pattern))
        if input_formats:
            ext_conditions = []
            for ext in input_formats:
                ext_conditions.append("i.filename LIKE ? COLLATE NOCASE")
                params.append(f"%.{str(ext).strip().lstrip('.')}")
            conditions.append("(" + " OR ".join(ext_conditions) + ")")

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        return where, params

    def search_images(
        self,
        group_name: Optional[str] = None,
        subgroup_name: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        filename_pattern: Optional[str] = None,
        input_formats: Optional[Sequence[str]] = None,
        limit: int = 10000,
        group_names: Optional[Sequence[str]] = None,
        subgroup_names: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Filter search with legacy result shape (dicts incl. tag lists).

        Accepts either the legacy single-value ``group_name``/``subgroup_name``
        kwargs or the new multi-select ``group_names``/``subgroup_names`` lists
        (OR semantics).  Both can co-exist; the lists take precedence when
        non-empty.
        """
        where, params = self._image_filter_sql(
            group_name, subgroup_name, tags, filename_pattern, input_formats,
            group_names=group_names, subgroup_names=subgroup_names,
        )
        rows = self._db.query(
            _IMAGE_SELECT + where + " ORDER BY i.date_added DESC LIMIT ?",
            tuple(params) + (int(limit),),
        )
        results = [dict(zip(_IMAGE_COLUMNS, row)) for row in rows]
        if results:
            self._attach_tags(results)
        return results

    def _attach_tags(self, results: List[Dict[str, Any]]) -> None:
        ids = [r["id"] for r in results]
        tags_by_id: Dict[int, List[str]] = {}
        chunk = 500
        for i in range(0, len(ids), chunk):
            part = ids[i:i + chunk]
            marks = ",".join("?" * len(part))
            for image_id, tag_name in self._db.query(
                "SELECT it.image_id, t.name FROM image_tags it "
                "JOIN tags t ON t.id = it.tag_id "
                f"WHERE it.image_id IN ({marks}) ORDER BY t.name",
                tuple(part),
            ):
                tags_by_id.setdefault(image_id, []).append(tag_name)
        for r in results:
            r["tags"] = tags_by_id.get(r["id"], [])

    # ------------------------------------------------------------------
    # Text search (FTS5, LIKE fallback)
    # ------------------------------------------------------------------

    def search_media_text(self, query: str, limit: int = 500) -> List[str]:
        """Media ids matching *query* in title/review/creator."""
        query = (query or "").strip()
        if not query:
            return []
        if self.fts_enabled:
            rows = self._db.query(
                "SELECT m.id FROM media_fts f "
                "JOIN media_items m ON m.rowid = f.rowid "
                "WHERE media_fts MATCH ? ORDER BY rank LIMIT ?",
                (self._fts_query(query), int(limit)),
            )
        else:
            rows = self._db.query(
                "SELECT id FROM media_items WHERE title LIKE ? COLLATE NOCASE "
                "OR review LIKE ? COLLATE NOCASE OR creator LIKE ? COLLATE NOCASE "
                "LIMIT ?",
                (_like(query), _like(query), _like(query), int(limit)),
            )
        return [r[0] for r in rows]

    def search_entities_text(self, query: str, limit: int = 500) -> List[str]:
        """Entity ids matching *query* in name/notes."""
        query = (query or "").strip()
        if not query:
            return []
        if self.fts_enabled:
            rows = self._db.query(
                "SELECT e.id FROM entity_fts f "
                "JOIN entities e ON e.rowid = f.rowid "
                "WHERE entity_fts MATCH ? ORDER BY rank LIMIT ?",
                (self._fts_query(query), int(limit)),
            )
        else:
            rows = self._db.query(
                "SELECT id FROM entities WHERE name LIKE ? COLLATE NOCASE "
                "OR notes LIKE ? COLLATE NOCASE LIMIT ?",
                (_like(query), _like(query), int(limit)),
            )
        return [r[0] for r in rows]

    @staticmethod
    def _fts_query(query: str) -> str:
        """Turn free text into a prefix-match FTS5 query, quoting each token
        so user input can't inject FTS syntax."""
        tokens = [t.replace('"', '""') for t in query.split() if t]
        return " ".join(f'"{t}"*' for t in tokens)

    # ------------------------------------------------------------------
    # Advanced listings search (DB.5 — replaces the Python set math)
    # ------------------------------------------------------------------

    def advanced_media_search(self, criteria: Dict[str, Any]) -> List[str]:
        """Media ids for the Advanced Search dialog's criteria dict:

        include_entities / exclude_entities  — entity ids
        include_tags / exclude_tags          — tag names (type='Tag')
        include_genres / exclude_genres      — tag names (type='Genre')
        match_mode                           — 'AND' (all inclusions) or 'OR'
        """
        conditions: List[str] = []
        params: list = []

        def tag_subquery(names: Sequence[str], tag_type: str) -> Tuple[str, list]:
            marks = ",".join("?" * len(names))
            sql = (
                "SELECT mt.media_item_id FROM media_tags mt "
                "JOIN tags t ON t.id = mt.tag_id "
                f"WHERE t.type = ? AND t.name IN ({marks}) COLLATE NOCASE"
            )
            return sql, [tag_type, *names]

        # Exclusions always AND together.
        exclude_entities = list(criteria.get("exclude_entities") or [])
        if exclude_entities:
            marks = ",".join("?" * len(exclude_entities))
            conditions.append(
                "m.id NOT IN (SELECT media_item_id FROM media_entity "
                f"WHERE entity_id IN ({marks}))"
            )
            params.extend(exclude_entities)
        for key, tag_type in (("exclude_tags", "Tag"), ("exclude_genres", "Genre")):
            names = list(criteria.get(key) or [])
            if names:
                sub, sub_params = tag_subquery(names, tag_type)
                conditions.append(f"m.id NOT IN ({sub})")
                params.extend(sub_params)

        # Inclusions combine per match_mode.
        inclusion_terms: List[str] = []
        inclusion_params: list = []
        include_entities = list(criteria.get("include_entities") or [])
        if include_entities:
            if (criteria.get("match_mode") or "AND") == "AND":
                for entity_id in include_entities:
                    inclusion_terms.append(
                        "m.id IN (SELECT media_item_id FROM media_entity "
                        "WHERE entity_id = ?)"
                    )
                    inclusion_params.append(entity_id)
            else:
                marks = ",".join("?" * len(include_entities))
                inclusion_terms.append(
                    "m.id IN (SELECT media_item_id FROM media_entity "
                    f"WHERE entity_id IN ({marks}))"
                )
                inclusion_params.extend(include_entities)
        for key, tag_type in (("include_tags", "Tag"), ("include_genres", "Genre")):
            names = list(criteria.get(key) or [])
            if not names:
                continue
            if (criteria.get("match_mode") or "AND") == "AND":
                for name in names:
                    sub, sub_params = tag_subquery([name], tag_type)
                    inclusion_terms.append(f"m.id IN ({sub})")
                    inclusion_params.extend(sub_params)
            else:
                sub, sub_params = tag_subquery(names, tag_type)
                inclusion_terms.append(f"m.id IN ({sub})")
                inclusion_params.extend(sub_params)

        if inclusion_terms:
            joiner = " AND " if (criteria.get("match_mode") or "AND") == "AND" else " OR "
            conditions.append("(" + joiner.join(inclusion_terms) + ")")
            params.extend(inclusion_params)

        sql = "SELECT m.id FROM media_items m"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        return [r[0] for r in self._db.query(sql, tuple(params))]

    # ------------------------------------------------------------------
    # Semantic search wrappers (DB.7)
    # ------------------------------------------------------------------

    def semantic_image_search(
        self,
        query_vector,
        top_k: int = 50,
        model: str = "metaclip",
        group_name: Optional[str] = None,
        subgroup_name: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        input_formats: Optional[Sequence[str]] = None,
    ) -> List[Tuple[int, float, str]]:
        """knn over image embeddings composed with the structured filters.

        Returns [(image_id, score, file_path), ...] by descending score.
        The prefilter SQL cannot carry bound parameters (engine limitation),
        so filter values are escaped as literals.
        """
        prefilter = ""
        if any((group_name, subgroup_name, tags, input_formats)):
            conditions: List[str] = []
            if tags:
                names = ",".join(sql_string_literal(t) for t in tags)
                conditions.append(
                    "i.id IN (SELECT it.image_id FROM image_tags it "
                    f"JOIN tags t ON t.id = it.tag_id WHERE t.name IN ({names}))"
                )
            if group_name:
                conditions.append(
                    "g.name LIKE " + sql_string_literal(_like(group_name))
                    + " COLLATE NOCASE"
                )
            if subgroup_name:
                conditions.append(
                    "s.name LIKE " + sql_string_literal(_like(subgroup_name))
                    + " COLLATE NOCASE"
                )
            if input_formats:
                exts = [
                    "i.filename LIKE "
                    + sql_string_literal(f"%.{str(e).strip().lstrip('.')}")
                    + " COLLATE NOCASE"
                    for e in input_formats
                ]
                conditions.append("(" + " OR ".join(exts) + ")")
            prefilter = (
                "SELECT CAST(i.id AS TEXT) FROM images i "
                "LEFT JOIN groups g ON g.id = i.group_id "
                "LEFT JOIN subgroups s ON s.id = i.subgroup_id "
                "WHERE " + " AND ".join(conditions)
            )

        hits = self._db.knn("image", model, query_vector, top_k, prefilter)
        results: List[Tuple[int, float, str]] = []
        for owner_id, score in hits:
            row = self._db.query(
                "SELECT file_path FROM images WHERE id = ?", (int(owner_id),)
            )
            if row:
                results.append((int(owner_id), float(score), row[0][0]))
        return results

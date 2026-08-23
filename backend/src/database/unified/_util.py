"""Shared helpers for the unified DAL repositories."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.src.constants.database import _TAG_BUCKET_CLAUSE


@contextmanager
def transaction(db):
    """Run the block in a transaction, joining one if already open."""
    own = not db.in_transaction
    if own:
        db.begin()
    try:
        yield
    except Exception:
        if own:
            db.rollback()
        raise
    else:
        if own:
            db.commit()


def rows_to_dicts(columns: Sequence[str], rows: Iterable[tuple]) -> List[Dict[str, Any]]:
    return [dict(zip(columns, row, strict=False)) for row in rows]


def loads_extra(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def dumps_extra(extra: Dict[str, Any]) -> str:
    return json.dumps(extra, ensure_ascii=False) if extra else "{}"


def split_csv(raw: Any) -> List[str]:
    """Split a legacy CSV field ('a, b, c') into clean, deduped items."""
    if not raw or not isinstance(raw, str):
        return []
    out: List[str] = []
    seen = set()
    for item in raw.split(","):
        item = item.strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def join_csv(items: Iterable[str]) -> str:
    return ", ".join(items)


def sql_string_literal(value: str) -> str:
    """Escape *value* as a SQL string literal.

    Only for the knn prefilter_sql path, which cannot carry bound
    parameters; everything else must use ?-placeholders.
    """
    return "'" + value.replace("'", "''") + "'"


def normalized_pair(a: str, b: str) -> Tuple[str, str]:
    """Order an undirected entity pair for the entity_entity (a<b) CHECK."""
    return (a, b) if a < b else (b, a)


# media_tags/entity_tags round-trip the legacy "genres"/"tags" CSV fields as
# two buckets: the 'Genre' category, and everything else ('Tag' catch-all).
# 'Copyright' is excluded from the catch-all so the auto-created title/name
# self-tag (see MediaRepo.save_media / EntityRepo.save_entity) survives every
# subsequent CSV round-trip instead of being swept up and deleted. Shared by
# media_repo.py (round-trip) and search_repo.py (tag-filter search) so both
# agree on which category a "Tag"/"Genre" search term maps to in SQL.


def tag_bucket_clause(tag_category: str) -> str:
    """SQL boolean expression (references a `tag_categories` join aliased
    `c`) selecting tags belonging to *tag_category* ('Genre' or 'Tag')."""
    return _TAG_BUCKET_CLAUSE.get(tag_category, "c.name = " + sql_string_literal(tag_category))


def intify(value: Any) -> Any:
    """Collapse integral floats back to int.

    REAL columns make SQLite return 9.0 where the legacy JSON blobs stored 9;
    UI code does things like ``"★" * rating`` and breaks on floats. Genuinely
    fractional values (community_rating 8.8) pass through unchanged.
    """
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value

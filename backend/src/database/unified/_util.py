"""Shared helpers for the unified DAL repositories."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


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
    return [dict(zip(columns, row)) for row in rows]


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
    return "'" + str(value).replace("'", "''") + "'"


def normalized_pair(a: str, b: str) -> Tuple[str, str]:
    """Order an undirected entity pair for the entity_entity (a<b) CHECK."""
    return (a, b) if a < b else (b, a)

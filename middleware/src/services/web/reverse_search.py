"""Reverse image search projection service (B-05 / #910).

Qt-free surface over the existing ``ReverseImageSearchManager`` strategies:
the engine catalog mirrors the Qt tab's labels, and one search run carries
the command dict the bridge pins. The service itself makes no live calls —
the manager does, at the user's request, and tests inject a fake manager
(RESOURCE RULE: no live provider operations).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

#: Engine labels mirror the Qt tab's ``_ENGINE_LABELS`` plus the extended
#: web engines the search_engines package registers.
ENGINE_LABELS: dict[str, str] = {
    "bing": "Bing Visual Search",
    "google": "Google Lens",
    "iqdb": "IQDB",
    "local_cbir": "Local AI Search",
    "saucenao": "SauceNAO",
    "tineye": "TinEye API",
    "yandex": "Yandex",
}


def engines_result() -> dict[str, Any]:
    """Bridge payload for ``reverse_search.engines``."""
    from middleware.src.web.crawlers.reverse_image_search_crawler import SUPPORTED_ENGINES

    engines = [{"id": engine, "label": ENGINE_LABELS.get(engine, engine)} for engine in sorted(SUPPORTED_ENGINES)]
    return {"engines": engines}


def search_result(manager: Any, params: Mapping[str, Any]) -> dict[str, Any]:
    """Run one search through the manager and normalize the payload.

    The manager raises ``ValueError`` for an unknown engine; the schema's
    enum already rejects that before dispatch, but the service still maps
    it to a failed result rather than leaking the error.
    """
    engine = str(params["engine"])
    image_path = str(params["image_path"])
    limit = _limit(params.get("limit"))
    roi = _roi(params.get("roi"))

    try:
        rows = manager.perform_reverse_search(
            image_path,
            engine_type=engine,
            roi=roi,
            **_count_args(engine, limit),
        )
    except ValueError as exc:
        return _failed(engine, str(exc))
    except Exception as exc:  # a provider/browser failure is a failed search, not a bridge error
        return _failed(engine, f"{type(exc).__name__}: {exc}")

    results = [_item(row) for row in rows][:limit]
    return {"ok": True, "engine": engine, "results": results, "error": None}


def _item(row: Mapping[str, Any]) -> dict[str, Any]:
    """The legacy ``ReverseSearchResult.to_dict`` shape with a numeric score."""
    score: float
    try:
        score = float(row.get("score", 1.0))
    except (TypeError, ValueError):
        score = 1.0
    return {
        "url": str(row.get("url", "")),
        "engine": str(row.get("engine", "")),
        "score": score,
        "resolution": str(row.get("resolution", "Unknown")),
        "title": row.get("title") or None,
    }


def _failed(engine: str, reason: str) -> dict[str, Any]:
    return {"ok": False, "engine": engine, "results": [], "error": reason}


# Strategy.search() does not share one count parameter: TinEye reads
# ``limit``, local CBIR reads ``top_k``, and SauceNAO reads ``numres``.
_COUNT_PARAM = {
    "local_cbir": "top_k",
    "saucenao": "numres",
}


def _count_args(engine: str, limit: int) -> dict[str, int]:
    return {_COUNT_PARAM.get(engine, "limit"): limit}


def _limit(value: Any) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return 20
    return max(1, min(limit, 100))


def _roi(value: Any) -> Optional[tuple[int, int, int, int]]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x, y, width, height = (int(component) for component in value)
    except (TypeError, ValueError):
        return None
    return (x, y, width, height)


__all__ = ["ENGINE_LABELS", "engines_result", "search_result"]

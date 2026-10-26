"""Reverse search differential: the legacy GUI row shape vs the service
payload (B-05 / #910, #883 harness).

The legacy side projects ``ReverseSearchResult.to_dict`` exactly as the
Qt tab's worker signal carried it; the service side projects
``search_result`` over the same rows. The comparison is the normalized
field set with the legacy string score coerced to the contract's number.
No live engine runs: both sides start from the same seeded rows.
"""

from __future__ import annotations

from middleware.src.services.web.reverse_search import search_result


def pair(tmp: object) -> tuple[dict[str, object], dict[str, object]]:
    rows = [
        {"url": "https://example.com/a", "engine": "tineye", "score": "0.8123", "resolution": "1920x1080", "title": "A match"},
        {"url": "https://example.com/b", "engine": "tineye", "score": "1.0000", "resolution": "Unknown", "title": None},
    ]
    return _legacy(rows), _service(rows)


class _FakeManager:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def perform_reverse_search(self, image_path, engine_type, roi=None, **kwargs):
        return self._rows


def _legacy(rows: list[dict[str, object]]) -> dict[str, object]:
    projected = [
        {
            "url": row["url"],
            "engine": row["engine"],
            "score": float(row["score"]),
            "resolution": row["resolution"],
            "title": row["title"],
        }
        for row in rows
    ]
    return {"ok": True, "engine": "tineye", "results": projected}


def _service(rows: list[dict[str, object]]) -> dict[str, object]:
    result = search_result(
        _FakeManager(rows),
        {"engine": "tineye", "image_path": "/pics/q.png", "limit": 20},
    )
    return {
        "ok": result["ok"],
        "engine": result["engine"],
        "results": [
            {
                "url": item["url"],
                "engine": item["engine"],
                "score": item["score"],
                "resolution": item["resolution"],
                "title": item["title"],
            }
            for item in result["results"]
        ],
    }

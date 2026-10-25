"""Reverse search service projection (B-05 / #910): the engine catalog,
the legacy-shape normalization, and the failure paths. The manager is a
fake — no live HTTP, no Selenium, no provider operations.
"""

from __future__ import annotations

from typing import Any

import pytest
from middleware.src.services.web.reverse_search import engines_result, search_result

SUPPORTED = {"bing", "google", "iqdb", "local_cbir", "saucenao", "tineye", "yandex"}


class _FakeManager:
    """Mirrors the real manager: unknown engines raise ValueError."""

    def __init__(self, rows=None, error: Exception | None = None) -> None:
        self.rows = rows or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def perform_reverse_search(self, image_path, engine_type, roi=None, **kwargs):
        if engine_type not in SUPPORTED:
            raise ValueError(f"Unknown engine_type {engine_type!r}.")
        self.calls.append({"image_path": image_path, "engine_type": engine_type, "roi": roi, **kwargs})
        if self.error is not None:
            raise self.error
        return self.rows


def test_engine_catalog_lists_every_supported_engine_sorted() -> None:
    result = engines_result()
    ids = [engine["id"] for engine in result["engines"]]
    assert ids == sorted(ids)
    assert "google" in ids and "tineye" in ids and "local_cbir" in ids
    labels = {engine["id"]: engine["label"] for engine in result["engines"]}
    assert labels["google"] == "Google Lens"
    assert labels["tineye"] == "TinEye API"
    assert labels["local_cbir"] == "Local AI Search"


def test_search_normalizes_the_legacy_to_dict_shape() -> None:
    manager = _FakeManager(
        rows=[
            {"url": "https://example.com/a", "engine": "tineye", "score": "0.8123", "resolution": "1920x1080", "title": "A match"},
            {"url": "https://example.com/b", "engine": "tineye", "score": "not-a-number", "resolution": "", "title": None},
        ]
    )
    result = search_result(manager, {"engine": "tineye", "image_path": "/pics/q.png", "limit": 10})

    assert result["ok"] is True
    assert result["engine"] == "tineye"
    assert result["error"] is None
    assert result["results"][0]["score"] == pytest.approx(0.8123)
    assert result["results"][0]["title"] == "A match"
    # A malformed score falls back to 1.0, and an empty title to None.
    assert result["results"][1]["score"] == 1.0
    assert result["results"][1]["title"] is None
    assert result["results"][1]["resolution"] == ""
    # The manager received the engine, path, roi and limit exactly once.
    assert manager.calls == [
        {"image_path": "/pics/q.png", "engine_type": "tineye", "roi": None, "limit": 10}
    ]


def test_roi_is_passed_as_a_tuple_and_bounded() -> None:
    manager = _FakeManager()
    search_result(manager, {"engine": "google", "image_path": "/q.png", "roi": [10, 20, 30, 40], "limit": 9999})
    call = manager.calls[0]
    assert call["roi"] == (10, 20, 30, 40)
    assert call["limit"] == 100  # bounded


def test_a_provider_failure_is_a_failed_search_not_a_crash() -> None:
    manager = _FakeManager(error=RuntimeError("connection refused"))
    result = search_result(manager, {"engine": "tineye", "image_path": "/q.png"})
    assert result["ok"] is False
    assert "connection refused" in result["error"]
    assert result["results"] == []


def test_an_unknown_engine_is_reported_by_the_service() -> None:
    result = search_result(_FakeManager(), {"engine": "bogus", "image_path": "/q.png"})
    # The schema's enum rejects this before dispatch; the service still
    # answers honestly for direct callers.
    assert result["ok"] is False
    assert "bogus" in result["error"]


def test_limit_defaults_and_invalid_roi_is_dropped() -> None:
    manager = _FakeManager()
    search_result(manager, {"engine": "local_cbir", "image_path": "/q.png", "roi": [1, 2, 3]})
    assert manager.calls[0]["limit"] == 20
    assert manager.calls[0]["roi"] is None

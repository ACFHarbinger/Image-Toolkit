"""Entity recon service projection (B-06 / #911): the config snapshot,
the resolution normalization, and the dispatch paths. The engine is a
fake — no dataset index build, no web dispatch, no network."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from middleware.src.services.web.entity_recon import describe_result, resolve_result
from middleware.src.web.recon.config import ReconConfig


@dataclass
class _FakeReport:
    query_hash: str = "abc123"
    predicted_name: str = "rin tohsaka"
    confidence: float = 0.91
    method: str = "ArcFace -> Local DB"
    created_at: str = "2026-10-25T00:00:00+00:00"
    entries: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "kind": "local",
                "label": "rin tohsaka",
                "source": "/dataset/rin/001.png",
                "score": 0.91,
                "method": "ArcFace -> Local DB",
            }
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_hash": self.query_hash,
            "predicted_name": self.predicted_name,
            "confidence": self.confidence,
            "method": self.method,
            "created_at": self.created_at,
            "entries": self.entries,
        }


@dataclass
class _FakeResolution:
    name: str = "rin tohsaka"
    confidence: float = 0.91
    method: str = "ArcFace -> Local DB"
    origin: str = "local"
    report: Any = field(default_factory=_FakeReport)
    local_matches: list[dict[str, Any]] = field(
        default_factory=lambda: [{"label": "rin_tohsaka", "path": "/dataset/rin/001.png", "score": 0.91}]
    )
    web_domains: list[dict[str, Any]] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.name)


class _FakeEngine:
    def __init__(self, resolution: Any | None = None, error: Exception | None = None) -> None:
        self.config = ReconConfig()
        self.resolution = resolution or _FakeResolution()
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def resolve(self, cutout_rgb, cutout_png):
        self.calls.append({"rgb_shape": getattr(cutout_rgb, "shape", None), "png_len": len(cutout_png)})
        if self.error is not None:
            raise self.error
        return self.resolution


def test_describe_without_engine_stays_unavailable_with_defaults() -> None:
    result = describe_result(None)
    assert result["available"] is False
    assert result["config"]["search_scope"] == "local"
    assert result["config"]["privacy_mode"] is True
    assert result["config"]["embed_mode"] == "face"
    assert result["config"]["local_match_threshold"] == pytest.approx(0.55)


def test_describe_with_engine_reports_its_config() -> None:
    engine = _FakeEngine()
    engine.config = ReconConfig(search_scope="both", top_k=7, embed_mode="clip")
    result = describe_result(engine)
    assert result["available"] is True
    assert result["config"]["search_scope"] == "both"
    # describe snapshots the stored config; privacy_mode is derived from
    # the scope only when a resolve applies overrides.
    assert result["config"]["privacy_mode"] is True
    assert result["config"]["top_k"] == 7
    assert result["config"]["embed_mode"] == "clip"


def test_resolve_normalizes_identity_and_provenance() -> None:
    engine = _FakeEngine()
    result = resolve_result(engine, "rgb-mock", b"\x89PNG", {"image_path": "/cutouts/rin.png"})
    assert result["available"] is True
    assert result["found"] is True
    assert result["name"] == "rin tohsaka"
    assert result["origin"] == "local"
    assert result["local_matches"][0]["path"] == "/dataset/rin/001.png"
    assert result["report"]["entries"][0]["kind"] == "local"
    assert result["error"] is None


def test_resolve_applies_scope_overrides_privacy_derived() -> None:
    engine = _FakeEngine()
    resolve_result(engine, "rgb", b"png", {"image_path": "/x.png", "search_scope": "web", "top_k": 3})
    assert engine.config.search_scope == "web"
    assert engine.config.privacy_mode is False  # derived: web is not strict privacy
    assert engine.config.top_k == 3


def test_resolve_copies_top_k_onto_the_indexer() -> None:
    engine = _FakeEngine()
    original = engine.config

    class _Indexer:
        def __init__(self) -> None:
            self.config = original
            self.seen_top_k: int | None = None

        def query(self, _embedding: object) -> list[object]:
            self.seen_top_k = self.config.top_k
            return []

    engine.indexer = _Indexer()

    def resolve(_cutout_rgb, _cutout_png):
        engine.indexer.query(None)
        return engine.resolution

    engine.resolve = resolve  # type: ignore[method-assign]
    resolve_result(engine, "rgb", b"png", {"image_path": "/x.png", "top_k": 3})
    assert engine.config.top_k == 3
    assert engine.indexer.config is engine.config
    assert engine.indexer.seen_top_k == 3


def test_resolve_without_engine_is_unavailable() -> None:
    result = resolve_result(None, None, b"", {"image_path": "/x.png"})
    assert result["available"] is False
    assert result["found"] is False
    assert result["report"]["entries"] == []


def test_an_unreadable_image_is_a_failed_resolve() -> None:
    engine = _FakeEngine()
    result = resolve_result(engine, None, b"", {"image_path": "/missing.png"})
    assert result["available"] is True
    assert "could not be read" in result["error"]
    assert engine.calls == []


def test_an_engine_failure_is_a_failed_resolve_not_a_crash() -> None:
    engine = _FakeEngine(error=RuntimeError("index is corrupt"))
    result = resolve_result(engine, "rgb", b"png", {"image_path": "/x.png"})
    assert result["available"] is True
    assert "index is corrupt" in result["error"]

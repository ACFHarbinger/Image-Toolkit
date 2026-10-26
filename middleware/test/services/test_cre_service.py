"""Unit tests for the Content Recommendation Engine (CRE) service (W0-03 Phase C, #867)."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest
from middleware.src.services.base import CommandValidationError
from middleware.src.services.cre import (
    CreService,
    CreServiceProtocol,
    IndexMediaItemCommand,
    RecommendCommand,
    RecommendResult,
)


class _PipelineDouble:
    """``run(self, query: str)`` rejects ``user_id`` the way CRE's pipeline does."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def run(self, query: str):
        self.calls.append((query,))
        item = SimpleNamespace(id="item-101", title="Ghost in the Shell", type="anime")
        return [
            SimpleNamespace(
                item=item,
                recommendation_value=0.94,
                reasons=["Matches cyberpunk themes", "High rating"],
            )
        ]


class _StoreDouble:
    def __init__(self) -> None:
        self.by_id: dict[str, object] = {}

    def create_collection(self) -> bool:
        return True

    def upsert(self, items: list[object]) -> int:
        for embedded in items:
            self.by_id[embedded.item.id] = embedded
        return len(items)

    def fetch_all(self, where_clause: str = "", params: list | None = None) -> list[dict[str, str]]:
        params = list(params or [])
        if where_clause == "id = ?" and params:
            item_id = params[0]
            if item_id in self.by_id:
                return [{"id": item_id}]
            return []
        return [{"id": item_id} for item_id in self.by_id]


class _InsertOnlyStore:
    def __init__(self) -> None:
        self.insert_called = False

    def insert_item(self, **kwargs: object) -> None:
        self.insert_called = True

    def fetch_all(self, where_clause: str = "", params: list | None = None) -> list[dict[str, str]]:
        return []


def test_cre_protocol_conformance() -> None:
    service = CreService()
    assert isinstance(service, CreServiceProtocol)


def test_cre_command_immutability() -> None:
    cmd = RecommendCommand(query="cyberpunk anime")
    with pytest.raises(dataclasses.FrozenInstanceError):
        cmd.query = "fantasy"  # type: ignore[misc]

    res = RecommendResult(success=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.success = False  # type: ignore[misc]


def test_recommend_validation() -> None:
    service = CreService()
    with pytest.raises(CommandValidationError):
        service.recommend(RecommendCommand(query=""))


def test_recommend_pipeline_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CreService()
    monkeypatch.setattr(service, "_get_pipeline", lambda: None)
    result = service.recommend(RecommendCommand(query="cyberpunk"))
    assert result.success is False
    assert result.items == ()
    assert result.error is not None
    assert "unavailable" in result.error


def test_recommend_maps_explained_result() -> None:
    pipeline = _PipelineDouble()
    with pytest.raises(TypeError):
        pipeline.run("cyberpunk", user_id="user-1")  # type: ignore[call-arg]

    service = CreService(pipeline=pipeline)
    result = service.recommend(
        RecommendCommand(query="cyberpunk", user_id="user-1", top_k=5)
    )

    assert pipeline.calls == [("cyberpunk",)]
    assert result.success is True
    assert result.total_found == 1
    assert len(result.items) == 1
    assert result.items[0].item_id == "item-101"
    assert result.items[0].title == "Ghost in the Shell"
    assert result.items[0].media_type == "anime"
    assert result.items[0].score == 0.94
    assert result.items[0].explanation == "Matches cyberpunk themes; High rating"
    assert result.elapsed_seconds >= 0.0


def test_recommend_result_without_item_fails() -> None:
    class _BarePipeline:
        def run(self, query: str):
            return [SimpleNamespace(title="untitled")]

    result = CreService(pipeline=_BarePipeline()).recommend(RecommendCommand(query="cyberpunk"))
    assert result.success is False
    assert result.items == ()


def test_index_item_validation() -> None:
    service = CreService()
    with pytest.raises(CommandValidationError):
        service.index_item(IndexMediaItemCommand(item_id="", title="Test"))
    with pytest.raises(CommandValidationError):
        service.index_item(IndexMediaItemCommand(item_id="1", title=""))


def test_index_item_upserts_and_fetches() -> None:
    store = _StoreDouble()
    service = CreService(store=store)
    command = IndexMediaItemCommand(
        item_id="m-42",
        title="Steins;Gate",
        media_type="anime",
        description="Time travel mystery",
        tags=("sci-fi", "thriller"),
    )
    result = service.index_item(command)
    assert result.success is True
    assert result.item_id == "m-42"
    assert store.fetch_all("id = ?", ["m-42"]) == [{"id": "m-42"}]

    saved = store.by_id["m-42"]
    assert saved.item.title == "Steins;Gate"
    assert saved.item.type == "anime"
    assert list(saved.item.tags) == ["sci-fi", "thriller"]
    assert saved.item.review_notes == "Time travel mystery"
    assert len(saved.dense_vector) >= 8
    assert len(saved.sparse_indices) >= 8
    assert len(saved.sparse_values) >= 8
    first_dense = list(saved.dense_vector)

    assert service.index_item(command).success is True
    assert list(store.by_id["m-42"].dense_vector) == first_dense

    other = service.index_item(
        IndexMediaItemCommand(
            item_id="m-43",
            title="Steins;Gate",
            description="different description",
        )
    )
    assert other.success is True
    assert store.fetch_all("id = ?", ["m-43"]) == [{"id": "m-43"}]
    assert list(store.by_id["m-43"].dense_vector) != first_dense


def test_index_item_without_upsert_fails() -> None:
    store = _InsertOnlyStore()
    service = CreService(store=store)
    result = service.index_item(
        IndexMediaItemCommand(item_id="m-42", title="Steins;Gate")
    )
    assert result.success is False
    assert result.error
    assert store.insert_called is False

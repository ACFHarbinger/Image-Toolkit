"""Unit tests for the Content Recommendation Engine (CRE) service (W0-03 Phase C, #867)."""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest
from middleware.src.services.base import CommandValidationError
from middleware.src.services.cre import (
    CreService,
    CreServiceProtocol,
    IndexMediaItemCommand,
    RecommendCommand,
    RecommendResult,
)


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


def test_recommend_with_mock_pipeline() -> None:
    mock_pipeline = MagicMock()
    mock_item = MagicMock(
        item_id="item-101",
        title="Ghost in the Shell",
        media_type="anime",
        score=0.94,
        explanation="Matches cyberpunk themes",
    )
    mock_pipeline.run.return_value = [mock_item]

    service = CreService(pipeline=mock_pipeline)
    result = service.recommend(RecommendCommand(query="cyberpunk", top_k=5))

    assert result.success is True
    assert result.total_found == 1
    assert len(result.items) == 1
    assert result.items[0].title == "Ghost in the Shell"
    assert result.items[0].score == 0.94
    assert result.items[0].explanation == "Matches cyberpunk themes"
    assert result.elapsed_seconds >= 0.0


def test_index_item_validation() -> None:
    service = CreService()
    with pytest.raises(CommandValidationError):
        service.index_item(IndexMediaItemCommand(item_id="", title="Test"))
    with pytest.raises(CommandValidationError):
        service.index_item(IndexMediaItemCommand(item_id="1", title=""))


def test_index_item_with_mock_store() -> None:
    mock_store = MagicMock()
    service = CreService(store=mock_store)
    result = service.index_item(
        IndexMediaItemCommand(
            item_id="m-42",
            title="Steins;Gate",
            media_type="anime",
            description="Time travel mystery",
            tags=("sci-fi", "thriller"),
        )
    )
    assert result.success is True
    assert result.item_id == "m-42"
    mock_store.insert_item.assert_called_once_with(
        item_id="m-42",
        title="Steins;Gate",
        media_type="anime",
        description="Time travel mystery",
        tags=("sci-fi", "thriller"),
    )

"""ASP → HybridStitch handoff contract (issue #1088)."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from middleware.src.services.asp import (
    HANDOFF_KIND,
    StitchCommand,
    StitchService,
)
from middleware.src.services.asp.handoff import (
    AspHybridHandoff,
    HandoffContractError,
    build_hybrid_handoff,
    handoff_from_session,
    handoff_summary,
    hybrid_handoff_payload,
    pairwise_homographies_from_global_affines,
)
from PIL import Image


def _frame(path, color: tuple[int, int, int]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color).save(path)
    return str(path)


def _translate(ty: float) -> list[list[float]]:
    return [[1.0, 0.0, 0.0], [0.0, 1.0, ty]]


def test_global_translation_becomes_hybridstitch_homography() -> None:
    """H maps frame A onto frame B, matching findHomography(pts_a, pts_b)."""
    pairs = pairwise_homographies_from_global_affines([_translate(0.0), _translate(40.0)])

    assert len(pairs) == 1
    assert pairs[0].index_a == 0
    assert pairs[0].index_b == 1
    homography = np.asarray(pairs[0].matrix)
    assert np.allclose(
        homography,
        [[1.0, 0.0, 0.0], [0.0, 1.0, -40.0], [0.0, 0.0, 1.0]],
    )
    mapped = homography @ np.array([3.0, 10.0, 1.0])
    assert np.allclose(mapped[:2], [3.0, -30.0])


def test_3x3_affines_and_singular_destination_are_skipped() -> None:
    identity = np.eye(3)
    singular = np.zeros((2, 3))
    pairs = pairwise_homographies_from_global_affines([identity, singular, identity])

    assert [pair.index_a for pair in pairs] == [1]
    assert pairs[0].index_b == 2


def test_affine_count_must_match_frames() -> None:
    with pytest.raises(HandoffContractError, match="does not match"):
        build_hybrid_handoff(image_paths=("a.png", "b.png"), affines=[_translate(0.0)])


def test_handoff_roundtrip_is_frozen_and_json_safe() -> None:
    handoff = build_hybrid_handoff(
        image_paths=("a.png", "b.png", "c.png"),
        affines=[_translate(0.0), _translate(10.0), _translate(25.0)],
        output_path="panorama.png",
        identity="raw_asp",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        handoff.output_path = "other.png"  # type: ignore[misc]

    payload = handoff.to_payload()
    assert payload["kind"] == HANDOFF_KIND
    assert payload["version"] == 1
    restored = AspHybridHandoff.from_payload(payload)
    assert restored == handoff
    assert len(restored.pair_homographies) == 2
    assert restored.pair_homographies[1].index_a == 1


def test_payload_rejects_a_broken_contract() -> None:
    handoff = build_hybrid_handoff(image_paths=("a.png", "b.png"))
    payload = handoff.to_payload()

    with pytest.raises(HandoffContractError, match="kind"):
        AspHybridHandoff.from_payload({**payload, "kind": "other"})
    with pytest.raises(HandoffContractError, match="version"):
        AspHybridHandoff.from_payload({**payload, "version": 2})
    with pytest.raises(HandoffContractError, match="at least two"):
        build_hybrid_handoff(image_paths=("only.png",))
    with pytest.raises(HandoffContractError, match="empty"):
        build_hybrid_handoff(image_paths=("a.png", "  "))

    bad_pair = {
        **payload,
        "pair_homographies": [
            {"index_a": 0, "index_b": 1, "matrix": np.eye(3).tolist()},
            {"index_a": 0, "index_b": 1, "matrix": np.eye(3).tolist()},
        ],
    }
    with pytest.raises(HandoffContractError, match="duplicate"):
        AspHybridHandoff.from_payload(bad_pair)

    non_finite = {
        **payload,
        "pair_homographies": [
            {
                "index_a": 0,
                "index_b": 1,
                "matrix": [[1, 0, 0], [0, 1, np.nan], [0, 0, 1]],
            }
        ],
    }
    with pytest.raises(HandoffContractError, match="finite"):
        AspHybridHandoff.from_payload(non_finite)


def test_session_keeps_only_frames_asp_kept() -> None:
    session = SimpleNamespace(
        inputs=SimpleNamespace(
            image_paths=["a.png", "b.png", "c.png"],
            output_path="staged.png",
        ),
        frame_provenance=[
            {"path": "a.png", "kept": True},
            {"path": "b.png", "kept": False, "drop_reason": "near_static"},
            {"path": "c.png", "kept": True},
        ],
        artifacts={
            "affines": [_translate(0.0), _translate(12.0)],
            "output_path": "panorama.png",
        },
        identity="raw_asp",
        fallback_reason=None,
        fallbacks=[],
    )

    handoff = handoff_from_session(session)

    assert handoff.image_paths == ("a.png", "c.png")
    assert handoff.output_path == "panorama.png"
    assert len(handoff.pair_homographies) == 1
    assert handoff.identity == "raw_asp"


def test_session_drops_affines_that_do_not_match_kept_frames() -> None:
    session = SimpleNamespace(
        inputs=SimpleNamespace(image_paths=["a.png", "b.png", "c.png"], output_path="out.png"),
        frame_provenance=[
            {"path": "a.png", "kept": True},
            {"path": "b.png", "kept": True},
            {"path": "c.png", "kept": True},
        ],
        artifacts={"affines": [_translate(0.0), _translate(4.0)]},
        identity="scans",
        fallback_reason=None,
        fallbacks=[{"reason": "no_edges"}],
    )

    handoff = handoff_from_session(session)

    assert handoff.image_paths == ("a.png", "b.png", "c.png")
    assert handoff.pair_homographies == ()
    assert handoff.identity == "scans"
    assert handoff.fallback_reason == "no_edges"
    assert "usable alignment" in handoff_summary(handoff)
    assert "ASP fallback: no_edges." in handoff_summary(handoff)


def test_legacy_snapshot_and_unset_pipeline_payload() -> None:
    legacy = SimpleNamespace(
        last_session=None,
        _hybrid_handoff_state={
            "image_paths": ["a.png", "b.png"],
            "affines": [_translate(0.0), _translate(8.0)],
            "output_path": "out.png",
            "identity": "raw_asp",
            "fallback_reason": None,
        },
    )
    payload = hybrid_handoff_payload(legacy)
    assert payload is not None
    assert payload["output_path"] == "out.png"
    assert len(payload["pair_homographies"]) == 1

    unset = SimpleNamespace(last_session=None)
    assert hybrid_handoff_payload(unset) is None
    assert hybrid_handoff_payload(MagicMock()) is None


def test_stitch_service_attaches_session_handoff(tmp_path) -> None:
    frame_a = _frame(tmp_path / "a.png", (20, 40, 60))
    frame_b = _frame(tmp_path / "b.png", (60, 40, 20))
    output = str(tmp_path / "panorama.png")
    session = SimpleNamespace(
        inputs=SimpleNamespace(image_paths=[frame_a, frame_b], output_path=output),
        frame_provenance=[
            {"path": frame_a, "kept": True},
            {"path": frame_b, "kept": True},
        ],
        artifacts={
            "affines": [_translate(0.0), _translate(15.0)],
            "output_path": output,
        },
        identity="raw_asp",
        fallback_reason=None,
        fallbacks=[],
    )
    pipeline = MagicMock()
    pipeline.run.return_value = MagicMock(width=8, height=16, metrics={"alignment_score": 0.5})
    pipeline.last_session = session

    result = StitchService(pipeline_factory=lambda **_kwargs: pipeline).stitch(
        StitchCommand(image_paths=(frame_a, frame_b), output_path=output)
    )

    assert result.success is True
    assert result.hybrid_handoff is not None
    assert result.hybrid_handoff["kind"] == HANDOFF_KIND
    restored = AspHybridHandoff.from_payload(result.hybrid_handoff)
    assert restored.image_paths == (frame_a, frame_b)
    assert len(restored.pair_homographies) == 1


def test_stitch_service_without_a_session_omits_handoff(tmp_path) -> None:
    frame_a = _frame(tmp_path / "a.png", (1, 2, 3))
    frame_b = _frame(tmp_path / "b.png", (3, 2, 1))
    pipeline = MagicMock()
    pipeline.run.return_value = MagicMock(width=1, height=1, metrics={})
    pipeline.last_session = None

    result = StitchService(pipeline_factory=lambda **_kwargs: pipeline).stitch(
        StitchCommand(image_paths=(frame_a, frame_b), output_path=str(tmp_path / "out.png"))
    )

    assert result.success is True
    assert result.hybrid_handoff is None

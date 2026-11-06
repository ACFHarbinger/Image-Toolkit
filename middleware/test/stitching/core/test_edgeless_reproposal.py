"""#472 edgeless-graph recovery: compose retained-adjacent chains.

No GPU. Pure functions + the existing rematch neighbour contract.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from middleware.src.stitching.core.pipeline._edge_filters import _reject_static_edges
from middleware.src.stitching.core.pipeline._frame_utils import (
    compose_retained_adjacent_edges,
    edgeless_compose_enabled,
    edgeless_reproposal_enabled,
    kept_original_indices,
)
from middleware.src.stitching.core.pipeline.run_stage import _RunStageMixin


def _edge(i: int, j: int, dx: float, dy: float, weight: float = 0.9) -> dict:
    return {
        "i": i,
        "j": j,
        "M": np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32),
        "weight": weight,
    }


def test_kept_original_indices_is_strictly_increasing_subsequence():
    pre = ["a.png", "b.png", "c.png", "d.png"]
    assert kept_original_indices(pre, ["a.png", "d.png"]) == [0, 3]
    assert kept_original_indices(pre, ["b.png", "c.png"]) == [1, 2]
    assert kept_original_indices(pre, ["a.png", "missing.png"]) is None


def test_compose_sums_adjacent_hops_between_retained_frames():
    # 16-frame case with 15 adjacent 20 px hops: spatial dedup keeps 0 and 15.
    hops = [_edge(i, i + 1, 0.0, 20.0) for i in range(15)]
    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(2)]
    composed = compose_retained_adjacent_edges(hops, [0, 15], frames)
    assert len(composed) == 1
    assert composed[0]["i"] == 0 and composed[0]["j"] == 1
    assert composed[0]["composed_hops"] == 15
    assert float(composed[0]["M"][1, 2]) == pytest.approx(300.0)
    # Each hop is below the 50 px static floor; the chain is not.
    assert _reject_static_edges(hops) == []
    assert len(_reject_static_edges(composed)) == 1


def test_compose_skips_pair_when_a_hop_is_missing():
    hops = [_edge(0, 1, 0.0, 20.0), _edge(2, 3, 0.0, 20.0)]  # missing 1→2
    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(2)]
    assert compose_retained_adjacent_edges(hops, [0, 3], frames) == []


def test_compose_two_retained_pairs():
    hops = [_edge(i, i + 1, 10.0, 0.0) for i in range(4)]
    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(3)]
    composed = compose_retained_adjacent_edges(hops, [0, 2, 4], frames)
    assert [(e["i"], e["j"]) for e in composed] == [(0, 1), (1, 2)]
    assert float(composed[0]["M"][0, 2]) == pytest.approx(20.0)
    assert float(composed[1]["M"][0, 2]) == pytest.approx(20.0)


def test_edgeless_reproposal_flag_defaults_on(monkeypatch):
    monkeypatch.delenv("ASP_EDGELESS_REPROPOSAL", raising=False)
    assert edgeless_reproposal_enabled() is True
    monkeypatch.setenv("ASP_EDGELESS_REPROPOSAL", "0")
    assert edgeless_reproposal_enabled() is False
    monkeypatch.setenv("ASP_EDGELESS_REPROPOSAL", "1")
    assert edgeless_reproposal_enabled() is True


def test_edgeless_compose_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("ASP_EDGELESS_COMPOSE", raising=False)
    assert edgeless_compose_enabled() is False
    monkeypatch.setenv("ASP_EDGELESS_COMPOSE", "1")
    assert edgeless_compose_enabled() is True
    monkeypatch.setenv("ASP_EDGELESS_COMPOSE", "0")
    assert edgeless_compose_enabled() is False


def _recovery_host(filter_fn, rematch_fn):
    return SimpleNamespace(
        _filter_edges=filter_fn,
        _rematch_retained_adjacent_edges=rematch_fn,
    )


def _recover(host, pre_edges, post_paths):
    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(len(post_paths))]
    # 15 adjacent hops index originals 0..15. Shorter graphs use the post paths.
    pre_paths = (
        [f"f{i}.png" for i in range(len(pre_edges) + 1)]
        if len(pre_edges) > 2
        else list(post_paths)
    )
    counts: dict = {}
    edges = _RunStageMixin._recover_edgeless_edges(
        host,
        [],
        frames=frames,
        bg_masks=[None] * len(frames),
        image_paths=post_paths,
        pre_dedup_paths=pre_paths,
        pre_dedup_edges=pre_edges,
        active_loftr=None,
        edge_stage_counts=counts,
        frame_h=8,
        frame_w=8,
    )
    return edges, counts


def test_edgeless_recovery_disabled_skips_compose_and_rematch(monkeypatch):
    monkeypatch.setenv("ASP_EDGELESS_REPROPOSAL", "0")
    monkeypatch.setenv("ASP_EDGELESS_COMPOSE", "1")
    calls = {"filter": 0, "rematch": 0}

    def fake_filter(*_args, **_kwargs):
        calls["filter"] += 1
        return []

    def fake_rematch(*_args, **_kwargs):
        calls["rematch"] += 1
        return []

    edges, counts = _recover(
        _recovery_host(fake_filter, fake_rematch),
        [_edge(0, 1, 0.0, 20.0)],
        ["f0.png", "f1.png"],
    )
    assert edges == []
    assert calls == {"filter": 0, "rematch": 0}
    assert counts == {}


def test_edgeless_recovery_compose_off_rematches(monkeypatch):
    monkeypatch.delenv("ASP_EDGELESS_COMPOSE", raising=False)
    monkeypatch.delenv("ASP_EDGELESS_REPROPOSAL", raising=False)
    calls = {"rematch": 0, "filtered_sources": []}

    def fake_filter(edges, *_args, **_kwargs):
        calls["filtered_sources"].append([edge.get("source") for edge in edges])
        return list(edges)

    def fake_rematch(*_args, **_kwargs):
        calls["rematch"] += 1
        return [_edge(0, 1, 0.0, 80.0)]

    pre = [_edge(i, i + 1, 0.0, 20.0) for i in range(15)]
    edges, counts = _recover(
        _recovery_host(fake_filter, fake_rematch),
        pre,
        ["f0.png", "f15.png"],
    )
    assert calls["rematch"] == 1
    assert counts["edgeless_compose_input"] == 0
    assert counts["edgeless_reproposal_input"] == 1
    assert counts["edgeless_reproposal_output"] == 1
    assert len(edges) == 1
    assert edges[0].get("source") != "edgeless_compose"


def test_edgeless_recovery_compose_keeps_chain_and_skips_rematch(monkeypatch):
    monkeypatch.setenv("ASP_EDGELESS_COMPOSE", "1")
    monkeypatch.delenv("ASP_EDGELESS_REPROPOSAL", raising=False)
    calls = {"rematch": 0}

    def fake_filter(edges, *_args, **_kwargs):
        # The 50 px floor is the real filter's job; here we only check that
        # the composed chain is what gets filtered, and that it is kept.
        assert edges and edges[0].get("source") == "edgeless_compose"
        assert float(edges[0]["M"][1, 2]) == pytest.approx(300.0)
        return list(edges)

    def fake_rematch(*_args, **_kwargs):
        calls["rematch"] += 1
        return []

    pre = [_edge(i, i + 1, 0.0, 20.0) for i in range(15)]
    edges, counts = _recover(
        _recovery_host(fake_filter, fake_rematch),
        pre,
        ["f0.png", "f15.png"],
    )
    assert calls["rematch"] == 0
    assert counts["edgeless_compose_input"] == 1
    assert counts["edgeless_compose_output"] == 1
    assert "edgeless_reproposal_input" not in counts
    assert edges[0]["source"] == "edgeless_compose"


def test_edgeless_recovery_rematches_when_composed_chain_is_filtered_out(monkeypatch):
    monkeypatch.setenv("ASP_EDGELESS_COMPOSE", "1")
    monkeypatch.delenv("ASP_EDGELESS_REPROPOSAL", raising=False)

    def fake_filter(edges, *_args, **_kwargs):
        if edges and edges[0].get("source") == "edgeless_compose":
            return []
        return list(edges)

    def fake_rematch(*_args, **_kwargs):
        return [_edge(0, 1, 0.0, 80.0)]

    pre = [_edge(i, i + 1, 0.0, 20.0) for i in range(15)]
    edges, counts = _recover(
        _recovery_host(fake_filter, fake_rematch),
        pre,
        ["f0.png", "f15.png"],
    )
    assert counts["edgeless_compose_input"] == 1
    assert counts["edgeless_compose_output"] == 0
    assert counts["edgeless_reproposal_output"] == 1
    assert len(edges) == 1


def test_edgeless_recovery_rematches_when_a_compose_hop_is_missing(monkeypatch):
    monkeypatch.setenv("ASP_EDGELESS_COMPOSE", "1")
    monkeypatch.delenv("ASP_EDGELESS_REPROPOSAL", raising=False)
    calls = {"rematch": 0}

    def fake_filter(edges, *_args, **_kwargs):
        return list(edges)

    def fake_rematch(*_args, **_kwargs):
        calls["rematch"] += 1
        return [_edge(0, 1, 0.0, 80.0)]

    # Missing hop 1→2, so the retained pair cannot be composed.
    pre = [_edge(0, 1, 0.0, 20.0), _edge(2, 3, 0.0, 20.0)]
    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(2)]
    counts: dict = {}
    edges = _RunStageMixin._recover_edgeless_edges(
        _recovery_host(fake_filter, fake_rematch),
        [],
        frames=frames,
        bg_masks=[None, None],
        image_paths=["a.png", "d.png"],
        pre_dedup_paths=["a.png", "b.png", "c.png", "d.png"],
        pre_dedup_edges=pre,
        active_loftr=None,
        edge_stage_counts=counts,
        frame_h=8,
        frame_w=8,
    )
    assert counts["edgeless_compose_input"] == 0
    assert calls["rematch"] == 1
    assert len(edges) == 1


def test_edgeless_reproposal_matches_only_retained_neighbours(monkeypatch):
    import middleware.src.stitching.alignment.matching as matching

    calls = []

    def fake_match(_frames, _masks, i, j, *_args, **_kwargs):
        calls.append((i, j))
        return {"i": i, "j": j, "M": np.eye(2, 3)}

    monkeypatch.setattr(matching, "_match_pair", fake_match)
    host = SimpleNamespace(
        motion_model="translation",
        _aliked=None,
        use_aliked=False,
        _roma=None,
        use_roma=False,
        bg_masked_matching=False,
    )
    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(3)]
    edges = _RunStageMixin._rematch_retained_adjacent_edges(host, frames, [None] * 3, None)
    assert calls == [(0, 1), (1, 2)]
    assert [(edge["i"], edge["j"]) for edge in edges] == calls

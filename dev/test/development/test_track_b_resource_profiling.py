"""Unit tests for Track B Phase 5: Resource, Latency, and Causal Profiling (#397)."""

from __future__ import annotations

import pytest
from tool.host import discover_plugins
from tool.host.store import WorkspaceStore
from tool.model.flame_graph import FlameGraph, FlameNode
from tool.model.resource_profile import (
    CausalImpactCurve,
    MemoryArena,
    estimate_latency_little_law,
    rank_bottlenecks,
)
from tool.plugins.resource_profiling import plugin
from tool.research.resource_profiling import (
    detect_leak_suspects,
    rank_targets,
    simulate_virtual_speedup,
    summarize_arenas,
)


def _flame() -> FlameGraph:
    # root(1000) -> decode(600: self 100 + yuv(500)) + render(400: self 400).
    yuv = FlameNode(name="yuv_convert", value=500.0, self_time_ms=500.0)
    decode = FlameNode(name="decode", value=600.0, self_time_ms=100.0, children=[yuv])
    render = FlameNode(name="render", value=400.0, self_time_ms=400.0)
    root = FlameNode(name="root", value=1000.0, children=[decode, render])
    return FlameGraph(root=root, total_time_ms=1000.0)


# ---------------------------------------------------------------------------
# CausalImpactCurve math
# ---------------------------------------------------------------------------

def test_amdahl_gain_half_profile_doubled():
    curve = CausalImpactCurve(target="x", target_share=0.5, baseline_total_ms=1000.0)
    assert curve.predicted_gain(1.0) == pytest.approx(0.25)  # 1 - (0.5 + 0.5/2)

def test_zero_share_has_no_leverage():
    curve = CausalImpactCurve(target="missing", target_share=0.0, baseline_total_ms=1000.0)
    assert curve.predicted_gain(2.0) == 0.0

def test_negative_speedup_rejected():
    curve = CausalImpactCurve(target="x", target_share=0.5, baseline_total_ms=1.0)
    with pytest.raises(ValueError):
        curve.predicted_gain(-0.1)

def test_curve_dict_roundtrip():
    curve = CausalImpactCurve(target="decode", target_share=0.6, baseline_total_ms=1000.0)
    restored = CausalImpactCurve.from_dict(curve.to_dict())
    assert restored.target == "decode"
    assert restored.target_share == 0.6


# ---------------------------------------------------------------------------
# Virtual speedup over a recorded flame tree
# ---------------------------------------------------------------------------

def test_virtual_speedup_finds_recursive_share():
    curve = simulate_virtual_speedup(_flame(), "yuv_convert")
    assert curve.target_share == pytest.approx(0.5)
    assert curve.points
    assert curve.points[0].predicted_gain >= 0.0

def test_virtual_speedup_unknown_target_is_zero():
    curve = simulate_virtual_speedup(_flame(), "no_such_frame")
    assert curve.target_share == 0.0
    assert all(p.predicted_gain == 0.0 for p in curve.points)

def test_rank_targets_orders_by_leverage():
    ranked = rank_targets(_flame(), top_n=3)
    assert ranked[0]["target"] == "decode"  # 0.6 share beats render's 0.4
    assert ranked[0]["gain_at_2x"] > ranked[1]["gain_at_2x"]

def test_rank_bottlenecks_top_down():
    rows = rank_bottlenecks(_flame(), top_n=2)
    assert rows[0]["name"] == "root"
    assert rows[0]["share"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Little's law
# ---------------------------------------------------------------------------

def test_little_law_sane_queue():
    out = estimate_latency_little_law(arrival_per_sec=10.0, mean_service_ms=50.0)
    assert out["utilization"] == pytest.approx(0.5)
    assert out["mean_latency_ms"] == pytest.approx(100.0)

def test_little_law_unstable_rejected():
    with pytest.raises(ValueError):
        estimate_latency_little_law(arrival_per_sec=100.0, mean_service_ms=50.0)

def test_little_law_bad_input_rejected():
    with pytest.raises(ValueError):
        estimate_latency_little_law(arrival_per_sec=0.0, mean_service_ms=50.0)


# ---------------------------------------------------------------------------
# Memory arenas
# ---------------------------------------------------------------------------

def _arena(monotonic: bool = True) -> MemoryArena:
    arena = MemoryArena(name="vram0", kind="vram", capacity_bytes=8 * 1024**3)
    vals = [100, 120, 140, 160, 180, 200] if monotonic else [100, 180, 120, 200, 110, 190]
    for i, mb in enumerate(vals):
        arena.add_sample(float(i * 100), mb * 1024 * 1024)
    return arena

def test_arena_peak_growth_capacity():
    arena = _arena()
    assert arena.peak_bytes == 200 * 1024 * 1024
    assert arena.growth_bytes() == 100 * 1024 * 1024
    assert not arena.over_capacity()

def test_arena_over_capacity():
    arena = MemoryArena(name="tiny", capacity_bytes=10)
    arena.add_sample(0.0, 100)
    assert arena.over_capacity()

def test_leak_suspect_on_monotonic_climb():
    suspects = detect_leak_suspects(_arena(monotonic=True), min_growth_bytes=1)
    assert len(suspects) == 1
    assert suspects[0]["growth_bytes"] == 100 * 1024 * 1024

def test_no_leak_suspect_on_sawtooth():
    assert detect_leak_suspects(_arena(monotonic=False), min_growth_bytes=1) == []

def test_arena_timeseries_feeds_track_a_views():
    series = _arena().as_timeseries()
    assert series.unit == "MB"
    assert len(series.points) == 6
    assert series.max_val == pytest.approx(200.0)

def test_arena_dict_roundtrip():
    restored = MemoryArena.from_dict(_arena().to_dict())
    assert restored.name == "vram0"
    assert len(restored.samples) == 6

def test_summarize_arenas_sorted_by_peak():
    rows = summarize_arenas([_arena(), MemoryArena(name="small")])
    assert rows[0]["name"] == "vram0"
    assert rows[0]["leak_suspects"] >= 0


# ---------------------------------------------------------------------------
# Plugin surface
# ---------------------------------------------------------------------------

def test_plugin_manifest_channels():
    assert plugin.manifest.name == "resource_profiling"
    assert plugin.manifest.channel_keys() == ("causal_profile", "memory_arenas")

def test_host_discovers_resource_profiling(tmp_path):
    store = WorkspaceStore(root=tmp_path)
    from tool.host import Host

    names = [p.manifest.name for p in Host(store=store).discover()]
    assert "resource_profiling" in names

def test_discover_plugins_convenience():
    assert "resource_profiling" in [p.manifest.name for p in discover_plugins()]

def test_plugin_profile_flame_end_to_end():
    out = plugin.profile_flame(_flame().to_dict(), top_n=2)
    assert out["total_ms"] == 1000.0
    assert out["targets"][0]["target"] == "decode"

def test_plugin_curve_for_end_to_end():
    curve = plugin.curve_for(_flame().to_dict(), "render")
    assert curve["target"] == "render"
    assert curve["target_share"] == pytest.approx(0.4)

def test_plugin_check_arenas_end_to_end():
    out = plugin.check_arenas([_arena().to_dict()])
    assert out["arenas"][0]["name"] == "vram0"
    assert isinstance(out["leak_suspects"], list)

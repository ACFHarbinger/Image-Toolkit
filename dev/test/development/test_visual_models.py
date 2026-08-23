"""Unit tests for Devtool v2 Visual & World State Models (#415, #418, #419)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tool.model.meta_graph import MetaGraph, MetaGraphEdge, MetaGraphNode
from tool.model.pipeline_scrubber import PipelineScrubSession, PipelineStageEvent
from tool.model.world_state import (
    WorldState,
)


def test_world_state_persistence_and_bookmarks(tmp_path: Path):
    ws = WorldState(workspace=str(tmp_path))

    # Add a custom node coordinate
    ws.update_node_position("backend.src.app", x=12.5, y=0.0, z=-4.2, pinned=True)
    assert "backend.src.app" in ws.nodes
    assert ws.nodes["backend.src.app"].pinned is True

    # Add a camera bookmark linked to an investigation
    bm = ws.add_bookmark(
        label="Investigate Seam Artifact",
        position=[10.0, 20.0, 30.0],
        target=[12.5, 0.0, -4.2],
        investigation_id="inv-001",
        pinned_node_id="backend.src.app",
    )
    assert len(ws.bookmarks) == 1
    assert bm.investigation_id == "inv-001"

    # Save to disk
    saved_path = ws.save(tmp_path)
    assert saved_path.exists()
    assert saved_path.name == "world_state.json"

    # Load from disk and verify fidelity
    loaded = WorldState.load(tmp_path)
    assert loaded.workspace == str(tmp_path.resolve())
    assert "backend.src.app" in loaded.nodes
    assert loaded.nodes["backend.src.app"].position == [12.5, 0.0, -4.2]
    assert len(loaded.bookmarks) == 1
    assert loaded.bookmarks[0].label == "Investigate Seam Artifact"


def test_meta_graph_tiered_galaxy_layout():
    graph = MetaGraph()

    # Add frontend layer nodes (+Y)
    graph.add_node(MetaGraphNode(id="ui.main", label="Main Window", layer="frontend", cluster_id="gui"))
    graph.add_node(MetaGraphNode(id="ui.tabs", label="Tab Bar", layer="frontend", cluster_id="gui"))

    # Add core layer nodes (Y=0)
    graph.add_node(MetaGraphNode(id="core.pipeline", label="ASP Pipeline", layer="core", cluster_id="asp"))
    graph.add_node(MetaGraphNode(id="core.models", label="PyTorch Models", layer="core", cluster_id="asp"))

    # Add native layer nodes (-Y)
    graph.add_node(MetaGraphNode(id="native.simd", label="C++ SIMD Core", layer="native", cluster_id="cpp"))

    # Add connecting edges
    graph.add_edge(MetaGraphEdge(id="e1", source_id="ui.main", target_id="core.pipeline", kind="call"))
    graph.add_edge(MetaGraphEdge(id="e2", source_id="core.pipeline", target_id="native.simd", kind="call"))
    graph.add_edge(MetaGraphEdge(id="e3", source_id="core.pipeline", target_id="core.models", kind="call"))

    # Compute 3D tiered layout
    graph.compute_tiered_layout(layer_spacing_y=40.0)

    # Verify Y-axis strict partitioning
    assert graph.nodes["ui.main"].position[1] == 40.0
    assert graph.nodes["ui.tabs"].position[1] == 40.0
    assert graph.nodes["core.pipeline"].position[1] == 0.0
    assert graph.nodes["core.models"].position[1] == 0.0
    assert graph.nodes["native.simd"].position[1] == -40.0

    # Verify nexus nodes calculation (core.pipeline has highest degree = 3)
    nexus = graph.get_nexus_nodes(top_n=1)
    assert len(nexus) == 1
    assert nexus[0].id == "core.pipeline"


def test_pipeline_scrubber_timeline_evaluation():
    session = PipelineScrubSession(session_id="run-101", pipeline_name="ASP Stitching")

    session.add_stage(PipelineStageEvent(id="s1", stage_name="Stage 1: Frame Dedup", start_ms=0.0, end_ms=100.0))
    session.add_stage(PipelineStageEvent(id="s2", stage_name="Stage 2: Pairwise Match", start_ms=100.0, end_ms=300.0))
    session.add_stage(PipelineStageEvent(id="s3", stage_name="Stage 3: Bundle Adjust", start_ms=300.0, end_ms=600.0))

    assert session.total_duration_ms == 600.0

    # Evaluate at t = 50ms (inside stage 1)
    eval_50 = session.evaluate_at(50.0)
    assert eval_50["active_stage_ids"] == ["s1"]
    assert eval_50["completed_stage_ids"] == []
    assert eval_50["stages"][0]["progress"] == pytest.approx(0.5)
    assert eval_50["stages"][1]["status"] == "pending"

    # Evaluate at t = 200ms (inside stage 2, stage 1 completed)
    eval_200 = session.evaluate_at(200.0)
    assert eval_200["active_stage_ids"] == ["s2"]
    assert eval_200["completed_stage_ids"] == ["s1"]
    assert eval_200["stages"][0]["status"] == "completed"
    assert eval_200["stages"][1]["progress"] == pytest.approx(0.5)
    assert eval_200["stages"][2]["status"] == "pending"

    # Evaluate at t = 700ms (all completed)
    eval_700 = session.evaluate_at(700.0)
    assert eval_700["active_stage_ids"] == []
    assert eval_700["completed_stage_ids"] == ["s1", "s2", "s3"]


def test_flame_graph_hierarchical_construction():
    from dataclasses import dataclass

    from tool.model.flame_graph import FlameGraph

    @dataclass
    class DummySpan:
        id: str
        name: str
        start_ms: float
        duration_ms: float
        end_ms: float
        category: str
        module: str

    spans = [
        DummySpan("s1", "app.main", 0.0, 100.0, 100.0, "lifecycle", "app"),
        DummySpan("s2", "db.init", 10.0, 40.0, 50.0, "database", "db"),
        DummySpan("s3", "gui.render", 50.0, 40.0, 90.0, "ui", "gui"),
    ]

    fg = FlameGraph.from_spans(spans)
    assert fg.total_time_ms == 100.0
    assert len(fg.root.children) == 1  # app.main is the root span
    app_node = fg.root.children[0]
    assert app_node.name == "app.main"
    assert len(app_node.children) == 2  # db.init and gui.render are nested inside app.main

    db_nodes = fg.find_nodes_by_category("database")
    assert len(db_nodes) == 1
    assert db_nodes[0].name == "db.init"


def test_timeseries_lttb_downsampling():
    import math

    from tool.model.metrics_timeline import TimeSeries

    ts = TimeSeries(name="rss_memory", unit="MB", alert_threshold=200.0)

    # Generate 1000 noisy sinusoidal data points
    for i in range(1000):
        t = float(i)
        val = 100.0 + 50.0 * math.sin(i / 50.0) + (i % 5)
        ts.add_point(t_ms=t, val=val)

    assert len(ts.points) == 1000
    assert ts.max_val > 140.0
    assert ts.min_val < 60.0

    # Downsample to 50 points
    sampled = ts.downsample(target_points=50)
    assert len(sampled) == 50
    # First and last point must be preserved exactly
    assert sampled[0].t_ms == ts.points[0].t_ms
    assert sampled[-1].t_ms == ts.points[-1].t_ms


def test_cross_view_bridge_event_dispatch():
    from tool.model.interaction_linking import CrossViewBridge, HoverTarget, SelectionTarget

    bridge = CrossViewBridge()
    selections: list[SelectionTarget] = []
    hovers: list[HoverTarget] = []

    bridge.on_selection(lambda sel: selections.append(sel))
    bridge.on_hover(lambda h: hovers.append(h) if h else None)

    # Dispatch selection
    sel = SelectionTarget(
        entity_id="node-asp-core",
        entity_kind="meta_node",
        source_surface="3d_world",
        linked_meta_node_id="node-asp-core",
    )
    bridge.set_selection(sel)
    assert len(selections) == 1
    assert bridge.active_selection.entity_id == "node-asp-core"

    # Dispatch hover
    hov = HoverTarget(
        entity_id="node-asp-core",
        entity_kind="meta_node",
        source_surface="flame_graph",
        pulse_color="#38bdf8",
    )
    bridge.set_hover(hov)
    assert len(hovers) == 1
    assert bridge.active_hover.pulse_color == "#38bdf8"


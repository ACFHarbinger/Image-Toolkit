"""Unit tests for Devtool v2 Visual & World State Models (#415, #418, #419)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tool.model.meta_graph import MetaGraph, MetaGraphEdge, MetaGraphNode
from tool.model.pipeline_scrubber import PipelineScrubSession, PipelineStageEvent
from tool.model.world_state import (
    CameraBookmark,
    NodeSpatialState,
    WorldFilterState,
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

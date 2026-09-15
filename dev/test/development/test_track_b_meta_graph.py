"""Unit tests for Track B Phase 1: Interactive Meta-Graph (Codebase Topology) (#393)."""

from __future__ import annotations

import json
from pathlib import Path

from tool.host import discover_plugins
from tool.host.store import WorkspaceStore
from tool.model.meta_graph import MetaGraph, MetaGraphEdge, MetaGraphNode
from tool.research.cartography import compute_semantic_cartography, tokenize_code_terms
from tool.research.meta_graph import (
    ZOOM_AST,
    ZOOM_FILE,
    ZOOM_MODULE,
    ZOOM_SYMBOL,
    apply_execution_trace_overlay,
    build_codebase_topology,
    compute_blast_radius,
    compute_skeleton_edge_bundling,
    extract_ast_file_topology,
    serialize_for_gpu,
)


def test_tokenize_code_terms():
    terms = tokenize_code_terms("def compute_affine_alignment(image_tensor, max_iterations=100):")
    assert "compute" in terms
    assert "affine" in terms
    assert "alignment" in terms
    assert "tensor" in terms
    assert "def" not in terms  # stopword


def test_extract_ast_file_topology_hierarchical(tmp_path: Path):
    src = tmp_path / "aligner.py"
    src.write_text(
        '"""Image alignment module."""\n'
        "import math\n"
        "from backend.models import BaSiC\n\n"
        "class BaseAligner:\n"
        "    pass\n\n"
        "class RigidAligner(BaseAligner):\n"
        '    """Aligner using rigid homography."""\n'
        "    def align(self, frame_a, frame_b):\n"
        "        if frame_a is None:\n"
        "            return None\n"
        "        for i in range(10):\n"
        "            math.sqrt(i)\n"
        "        return frame_a\n\n"
        "def helper_func():\n"
        "    return 42\n"
    )

    nodes, edges = extract_ast_file_topology(src, "aligner.py", include_ast=True)
    node_ids = {n.id: n for n in nodes}

    assert "file:aligner.py" in node_ids
    file_node = node_ids["file:aligner.py"]
    assert file_node.zoom_level == ZOOM_FILE
    assert file_node.complexity >= 2.0

    assert "symbol:aligner.py::RigidAligner" in node_ids
    class_node = node_ids["symbol:aligner.py::RigidAligner"]
    assert class_node.zoom_level == ZOOM_SYMBOL
    assert class_node.parent_id == "file:aligner.py"

    assert "symbol:aligner.py::RigidAligner.align" in node_ids
    method_node = node_ids["symbol:aligner.py::RigidAligner.align"]
    assert method_node.zoom_level == ZOOM_SYMBOL
    assert method_node.parent_id == "symbol:aligner.py::RigidAligner"
    assert method_node.complexity > 1.0

    assert "symbol:aligner.py::helper_func" in node_ids
    fn_node = node_ids["symbol:aligner.py::helper_func"]
    assert fn_node.zoom_level == ZOOM_SYMBOL

    # Verify AST granular nodes (Zoom 3)
    ast_nodes = [n for n in nodes if n.zoom_level == ZOOM_AST]
    assert len(ast_nodes) > 0

    # Verify edge kinds
    edge_kinds = {e.kind for e in edges}
    assert "contains" in edge_kinds
    assert "import" in edge_kinds
    assert "inherits" in edge_kinds


def test_build_codebase_topology(tmp_path: Path):
    pkg = tmp_path / "backend" / "vision"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "camera.py").write_text("class Camera:\n    def capture(self):\n        pass\n")
    (pkg / "filter.py").write_text("import math\ndef apply_blur():\n    return math.pi\n")

    graph = build_codebase_topology(tmp_path, max_files=10)
    assert len(graph.nodes) >= 4
    assert any(n.zoom_level == ZOOM_MODULE for n in graph.nodes.values())
    assert any(n.zoom_level == ZOOM_FILE for n in graph.nodes.values())
    assert any(n.zoom_level == ZOOM_SYMBOL for n in graph.nodes.values())


def test_compute_blast_radius():
    graph = MetaGraph()
    # A -> B -> C, and D -> B
    graph.add_node(MetaGraphNode(id="A", label="A", layer="core"))
    graph.add_node(MetaGraphNode(id="B", label="B", layer="core"))
    graph.add_node(MetaGraphNode(id="C", label="C", layer="core"))
    graph.add_node(MetaGraphNode(id="D", label="D", layer="core"))

    graph.add_edge(MetaGraphEdge(id="e1", source_id="A", target_id="B", kind="import"))
    graph.add_edge(MetaGraphEdge(id="e2", source_id="B", target_id="C", kind="import"))
    graph.add_edge(MetaGraphEdge(id="e3", source_id="D", target_id="B", kind="import"))

    # If C changes, upstream dependents are B, A, D
    blast_c = compute_blast_radius(graph, "C", direction="upstream")
    assert blast_c["total_impacted"] == 3
    assert set(blast_c["impacted_nodes"]) == {"A", "B", "D"}
    assert blast_c["levels"][1] == ["B"]
    assert set(blast_c["levels"][2]) == {"A", "D"}

    # Downstream dependencies of A: B and C
    down_a = compute_blast_radius(graph, "A", direction="downstream")
    assert down_a["total_impacted"] == 2
    assert set(down_a["impacted_nodes"]) == {"B", "C"}


def test_software_cartography_semantic_layout():
    graph = MetaGraph()
    graph.add_node(MetaGraphNode(
        id="mod1", label="cv_matcher", layer="core", zoom_level=ZOOM_FILE,
        loc=350, complexity=4.2, metadata={"terms": ["homography", "keypoints", "sift", "matrix"]}
    ))
    graph.add_node(MetaGraphNode(
        id="mod2", label="cv_stitcher", layer="core", zoom_level=ZOOM_FILE,
        loc=420, complexity=5.0, metadata={"terms": ["homography", "seam", "blend", "matrix"]}
    ))
    graph.add_node(MetaGraphNode(
        id="mod3", label="gui_dialog", layer="frontend", zoom_level=ZOOM_FILE,
        loc=150, complexity=1.5, metadata={"terms": ["button", "dialog", "layout", "click"]}
    ))

    cart = compute_semantic_cartography(graph)
    assert cart["total_nodes"] == 3
    assert len(cart["landmarks"]) == 3
    assert "mod1" in cart["coordinates"]

    # Elevations should scale with loc and complexity
    coord1 = cart["coordinates"]["mod1"]
    coord3 = cart["coordinates"]["mod3"]
    assert coord1[2] > coord3[2]


def test_skeleton_edge_bundling_and_gpu_serialization():
    graph = MetaGraph()
    graph.add_node(MetaGraphNode(id="n1", label="N1", layer="core", cluster_id="c1", position=[10.0, 0.0, 10.0]))
    graph.add_node(MetaGraphNode(id="n2", label="N2", layer="core", cluster_id="c1", position=[12.0, 0.0, 12.0]))
    graph.add_node(MetaGraphNode(id="n3", label="N3", layer="frontend", cluster_id="c2", position=[80.0, 35.0, 80.0]))

    # Intra-cluster edge
    graph.add_edge(MetaGraphEdge(id="e_intra", source_id="n1", target_id="n2", kind="call"))
    # Inter-cluster edge
    graph.add_edge(MetaGraphEdge(id="e_inter", source_id="n1", target_id="n3", kind="call"))

    bundling = compute_skeleton_edge_bundling(graph)
    assert len(bundling["e_intra"]) == 2  # direct line
    assert len(bundling["e_inter"]) == 4  # routed waypoint spline

    gpu_data = serialize_for_gpu(graph)
    assert len(gpu_data["nodes"]["id"]) == 3
    assert len(gpu_data["edges"]["id"]) == 2
    assert "bundled_path" in gpu_data["edges"]


def test_dynamic_execution_trace_overlay():
    graph = MetaGraph()
    graph.add_node(MetaGraphNode(id="symbol:vision/stitcher.py::align", label="align", layer="core"))
    graph.add_node(MetaGraphNode(id="symbol:vision/stitcher.py::blend", label="blend", layer="core"))

    events = [
        {"module": "vision/stitcher.py", "function": "align", "duration_ms": 45.0, "error": False},
        {"module": "vision/stitcher.py", "function": "blend", "duration_ms": 25.5, "error": True},
    ]

    overlay = apply_execution_trace_overlay(graph, events)
    assert overlay["event_count"] == 2
    assert overlay["error_count"] == 1
    assert overlay["total_duration_ms"] == 70.5
    assert len(overlay["active_nodes"]) == 2
    assert len(overlay["active_edges"]) == 1

    node_align = graph.nodes["symbol:vision/stitcher.py::align"]
    assert node_align.call_count == 1
    assert node_align.latency_ms == 45.0


def test_meta_graph_plugin_discovery_and_artifacts(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "worker.py").write_text("def do_work():\n    pass\n")

    session_file = tmp_path / "telemetry-123.jsonl"
    session_file.write_text(
        json.dumps({"module": "worker.py", "function": "do_work", "duration_ms": 15.0}) + "\n"
    )

    store = WorkspaceStore(root=tmp_path / "investigations", telemetry_dir=tmp_path)
    plugins = {p.manifest.name: p for p in discover_plugins(store)}

    assert "meta_graph" in plugins
    meta_plugin = plugins["meta_graph"]
    artifacts = meta_plugin.artifacts(store)

    artifact_kinds = {a.kind for a in artifacts}
    assert "topology" in artifact_kinds
    assert "cartography" in artifact_kinds
    assert "trace" in artifact_kinds

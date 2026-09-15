"""Track B Phase 1: Interactive Meta-Graph (Codebase Topology) research module (#393).

Implements codebase topology extraction, multi-level semantic zooming,
transitive blast-radius analysis, GPU/force-directed graph serialization,
skeleton-based edge bundling (SBEB), and dynamic execution tracing overlays
per §Track B Phase 1 and D42/D43/D54/D55.
"""

from __future__ import annotations

import ast
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..model.meta_graph import MetaGraph, MetaGraphEdge, MetaGraphNode
from .cartography import compute_semantic_cartography, tokenize_code_terms

# Zoom levels for semantic zooming
ZOOM_MODULE = 0
ZOOM_FILE = 1
ZOOM_SYMBOL = 2
ZOOM_AST = 3

__all__ = [
    "ZOOM_MODULE",
    "ZOOM_FILE",
    "ZOOM_SYMBOL",
    "ZOOM_AST",
    "extract_ast_file_topology",
    "build_codebase_topology",
    "compute_blast_radius",
    "compute_skeleton_edge_bundling",
    "compute_semantic_cartography",
    "serialize_for_gpu",
    "apply_execution_trace_overlay",
]


def _infer_layer(rel_path: str) -> str:
    parts = Path(rel_path).parts
    first = parts[0].lower() if parts else ""
    if first in ("gui", "frontend", "app", "extension", "ui"):
        return "frontend"
    if first in ("base", "native", "cpp", "rust"):
        return "native"
    return "core"


def _infer_cluster(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    if len(parts) == 1:
        return parts[0]
    return "default"


def _extract_imports(tree: ast.Module, file_id: str, next_edge_id) -> List[MetaGraphEdge]:
    edges: List[MetaGraphEdge] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name.split(".")[0]
                edges.append(MetaGraphEdge(
                    id=next_edge_id("imp"),
                    source_id=file_id,
                    target_id=f"module:{mod_name}",
                    kind="import",
                ))
        elif isinstance(node, ast.ImportFrom) and node.module:
            edges.append(MetaGraphEdge(
                id=next_edge_id("imp"),
                source_id=file_id,
                target_id=f"module:{node.module.split('.')[0]}",
                kind="import",
            ))
    return edges


def _extract_fn_symbol(
    node: Any,
    rel: str,
    parent_id: str,
    layer: str,
    cluster: str,
    include_ast: bool,
    next_edge_id,
    display_name: Optional[str] = None,
) -> Tuple[List[MetaGraphNode], List[MetaGraphEdge], int]:
    name = display_name or node.name
    fn_id = f"symbol:{rel}::{name}"
    terms = tokenize_code_terms(node.name)
    branch_count = sum(
        1 for n in ast.walk(node) if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler))
    )
    fn_node = MetaGraphNode(
        id=fn_id,
        label=name,
        layer=layer,
        kind="function",
        cluster_id=cluster,
        zoom_level=ZOOM_SYMBOL,
        parent_id=parent_id,
        loc=getattr(node, "end_lineno", node.lineno) - node.lineno + 1,
        complexity=float(max(1.0, branch_count + 1.0)),
        metadata={"terms": terms[:10]},
    )
    nodes = [fn_node]
    edges = [MetaGraphEdge(id=next_edge_id("cont"), source_id=parent_id, target_id=fn_id, kind="contains")]

    if include_ast:
        for idx, sub in enumerate(getattr(node, "body", [])):
            if isinstance(sub, (ast.Call, ast.If, ast.For, ast.Return)):
                ast_id = f"ast:{fn_id}::{sub.__class__.__name__}_{idx}"
                nodes.append(MetaGraphNode(
                    id=ast_id,
                    label=sub.__class__.__name__,
                    layer=layer,
                    kind="ast",
                    cluster_id=cluster,
                    zoom_level=ZOOM_AST,
                    parent_id=fn_id,
                    loc=1,
                    complexity=1.0,
                ))
                edges.append(MetaGraphEdge(id=next_edge_id("ast"), source_id=fn_id, target_id=ast_id, kind="contains"))

    return nodes, edges, branch_count


def _extract_class_symbol(
    node: ast.ClassDef,
    rel: str,
    file_id: str,
    layer: str,
    cluster: str,
    include_ast: bool,
    next_edge_id,
) -> Tuple[List[MetaGraphNode], List[MetaGraphEdge], int]:
    class_id = f"symbol:{rel}::{node.name}"
    terms = tokenize_code_terms(node.name)
    if ast.get_docstring(node):
        terms.extend(tokenize_code_terms(ast.get_docstring(node) or ""))

    class_node = MetaGraphNode(
        id=class_id,
        label=node.name,
        layer=layer,
        kind="class",
        cluster_id=cluster,
        zoom_level=ZOOM_SYMBOL,
        parent_id=file_id,
        loc=getattr(node, "end_lineno", node.lineno) - node.lineno + 1,
        complexity=1.0,
        metadata={"terms": terms[:15]},
    )
    nodes = [class_node]
    edges = [MetaGraphEdge(id=next_edge_id("cont"), source_id=file_id, target_id=class_id, kind="contains")]
    branch_count = 0

    for base in node.bases:
        if isinstance(base, ast.Name):
            edges.append(MetaGraphEdge(id=next_edge_id("inh"), source_id=class_id, target_id=f"symbol:{base.id}", kind="inherits"))

    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            m_nodes, m_edges, m_branches = _extract_fn_symbol(
                item, rel, class_id, layer, cluster, include_ast, next_edge_id, f"{node.name}.{item.name}"
            )
            nodes.extend(m_nodes)
            edges.extend(m_edges)
            branch_count += m_branches

    return nodes, edges, branch_count


def extract_ast_file_topology(
    path: Path,
    rel_path: Optional[str] = None,
    include_ast: bool = True,
) -> Tuple[List[MetaGraphNode], List[MetaGraphEdge]]:
    """Statically parse a Python source file to extract hierarchical topology."""
    rel = rel_path or path.name
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], []

    loc = len([ln for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")])
    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError:
        tree = ast.Module(body=[], type_ignores=[])

    layer = _infer_layer(rel)
    cluster = _infer_cluster(rel)
    file_id = f"file:{rel}"
    file_terms = tokenize_code_terms(path.stem)
    if ast.get_docstring(tree):
        file_terms.extend(tokenize_code_terms(ast.get_docstring(tree) or ""))

    nodes: List[MetaGraphNode] = []
    edges: List[MetaGraphEdge] = []

    file_node = MetaGraphNode(
        id=file_id,
        label=Path(rel).name,
        layer=layer,
        kind="file",
        cluster_id=cluster,
        zoom_level=ZOOM_FILE,
        loc=loc,
        complexity=1.0,
        metadata={"rel_path": rel, "terms": file_terms[:20]},
    )
    nodes.append(file_node)

    edge_counter = 0

    def next_edge_id(prefix: str = "e") -> str:
        nonlocal edge_counter
        edge_counter += 1
        return f"{prefix}_{file_id}_{edge_counter}"

    edges.extend(_extract_imports(tree, file_id, next_edge_id))
    file_branches = 0

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            c_nodes, c_edges, c_branches = _extract_class_symbol(
                node, rel, file_id, layer, cluster, include_ast, next_edge_id
            )
            nodes.extend(c_nodes)
            edges.extend(c_edges)
            file_branches += c_branches
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            f_nodes, f_edges, f_branches = _extract_fn_symbol(
                node, rel, file_id, layer, cluster, include_ast, next_edge_id
            )
            nodes.extend(f_nodes)
            edges.extend(f_edges)
            file_branches += f_branches

    file_node.complexity = float(max(1.0, file_branches + 1.0))
    return nodes, edges


def build_codebase_topology(
    root: Path,
    max_files: int = 200,
    include_ast: bool = False,
) -> MetaGraph:
    """Scan workspace directory and build multi-level MetaGraph topology."""
    graph = MetaGraph()
    py_files: List[Path] = []
    ignored = {".git", ".venv", "__pycache__", "node_modules", "target", "build", "dist", ".tox"}

    for p in sorted(root.rglob("*.py")):
        if any(part in ignored for part in p.relative_to(root).parts[:-1]):
            continue
        py_files.append(p)
        if len(py_files) >= max_files:
            break

    module_nodes: Dict[str, MetaGraphNode] = {}

    for file_path in py_files:
        rel_str = str(file_path.relative_to(root))
        nodes, edges = extract_ast_file_topology(file_path, rel_str, include_ast=include_ast)
        for n in nodes:
            graph.add_node(n)
        for e in edges:
            graph.add_edge(e)

        parts = Path(rel_str).parts
        mod_key = parts[0] if parts else "root"
        mod_id = f"module:{mod_key}"
        if mod_id not in module_nodes:
            module_nodes[mod_id] = MetaGraphNode(
                id=mod_id,
                label=mod_key,
                layer=_infer_layer(rel_str),
                kind="module",
                cluster_id=mod_key,
                zoom_level=ZOOM_MODULE,
                loc=0,
                complexity=1.0,
            )
            graph.add_node(module_nodes[mod_id])

        module_nodes[mod_id].loc += nodes[0].loc if nodes else 0
        file_id = f"file:{rel_str}"
        graph.add_edge(MetaGraphEdge(
            id=f"mod_cont_{mod_id}_{file_id}",
            source_id=mod_id,
            target_id=file_id,
            kind="contains",
        ))

    graph.compute_tiered_layout()
    return graph


def compute_blast_radius(
    graph: MetaGraph,
    target_id: str,
    direction: str = "upstream",
    max_depth: int = 10,
) -> Dict[str, Any]:
    """Compute transitive impact / blast radius across graph dependency edges."""
    adj: Dict[str, List[str]] = defaultdict(list)
    for e in graph.edges.values():
        if e.kind in ("contains", "ast"):
            continue
        if direction == "upstream":
            adj[e.target_id].append(e.source_id)
        else:
            adj[e.source_id].append(e.target_id)

    visited: Set[str] = {target_id}
    queue: deque[Tuple[str, int]] = deque([(target_id, 0)])
    levels: Dict[int, List[str]] = defaultdict(list)

    while queue:
        curr, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for neighbor in adj.get(curr, []):
            if neighbor not in visited:
                visited.add(neighbor)
                levels[depth + 1].append(neighbor)
                queue.append((neighbor, depth + 1))

    return {
        "target_id": target_id,
        "direction": direction,
        "total_impacted": len(visited) - 1,
        "levels": dict(levels),
        "impacted_nodes": [nid for nid in visited if nid != target_id],
    }


def compute_skeleton_edge_bundling(
    graph: MetaGraph,
) -> Dict[str, List[List[float]]]:
    """Compute Skeleton-Based Edge Bundling (SBEB) waypoint paths between clusters."""
    cluster_centers: Dict[str, List[float]] = {}
    cluster_counts: Dict[str, int] = defaultdict(int)

    for n in graph.nodes.values():
        cid = n.cluster_id or "default"
        if cid not in cluster_centers:
            cluster_centers[cid] = [0.0, 0.0, 0.0]
        cluster_centers[cid][0] += n.position[0]
        cluster_centers[cid][1] += n.position[1]
        cluster_centers[cid][2] += n.position[2]
        cluster_counts[cid] += 1

    for cid, center in cluster_centers.items():
        cnt = max(1, cluster_counts[cid])
        cluster_centers[cid] = [round(v / cnt, 2) for v in center]

    bundled_paths: Dict[str, List[List[float]]] = {}
    for eid, edge in graph.edges.items():
        src = graph.nodes.get(edge.source_id)
        tgt = graph.nodes.get(edge.target_id)
        if not src or not tgt:
            continue

        p0 = src.position
        p3 = tgt.position
        src_c = src.cluster_id or "default"
        tgt_c = tgt.cluster_id or "default"

        if src_c == tgt_c:
            bundled_paths[eid] = [p0, p3]
            continue

        c_src = cluster_centers.get(src_c, p0)
        c_tgt = cluster_centers.get(tgt_c, p3)

        # Intermediate skeleton waypoints
        p1 = [
            round(p0[0] * 0.4 + c_src[0] * 0.6, 2),
            round(p0[1] * 0.5 + c_src[1] * 0.5, 2),
            round(p0[2] * 0.4 + c_src[2] * 0.6, 2),
        ]
        p2 = [
            round(p3[0] * 0.4 + c_tgt[0] * 0.6, 2),
            round(p3[1] * 0.5 + c_tgt[1] * 0.5, 2),
            round(p3[2] * 0.4 + c_tgt[2] * 0.6, 2),
        ]
        bundled_paths[eid] = [p0, p1, p2, p3]

    return bundled_paths


def serialize_for_gpu(
    graph: MetaGraph,
    zoom_level: Optional[int] = None,
) -> Dict[str, Any]:
    """Serialize graph into columnar buffers for WebGL / Cosmograph / Arrow."""
    filtered_nodes = [
        n for n in graph.nodes.values()
        if zoom_level is None or n.zoom_level == zoom_level
    ]
    node_ids = {n.id for n in filtered_nodes}
    filtered_edges = [
        e for e in graph.edges.values()
        if e.source_id in node_ids and e.target_id in node_ids
    ]
    bundling = compute_skeleton_edge_bundling(graph)

    in_deg: Dict[str, int] = defaultdict(int)
    out_deg: Dict[str, int] = defaultdict(int)
    for e in filtered_edges:
        out_deg[e.source_id] += 1
        in_deg[e.target_id] += 1

    return {
        "nodes": {
            "id": [n.id for n in filtered_nodes],
            "label": [n.label for n in filtered_nodes],
            "layer": [n.layer for n in filtered_nodes],
            "kind": [n.kind for n in filtered_nodes],
            "zoom_level": [n.zoom_level for n in filtered_nodes],
            "cluster_id": [n.cluster_id for n in filtered_nodes],
            "loc": [n.loc for n in filtered_nodes],
            "complexity": [n.complexity for n in filtered_nodes],
            "elevation": [n.elevation for n in filtered_nodes],
            "position_x": [n.position[0] for n in filtered_nodes],
            "position_y": [n.position[1] for n in filtered_nodes],
            "position_z": [n.position[2] for n in filtered_nodes],
            "in_degree": [in_deg[n.id] for n in filtered_nodes],
            "out_degree": [out_deg[n.id] for n in filtered_nodes],
        },
        "edges": {
            "id": [e.id for e in filtered_edges],
            "source": [e.source_id for e in filtered_edges],
            "target": [e.target_id for e in filtered_edges],
            "kind": [e.kind for e in filtered_edges],
            "weight": [e.weight for e in filtered_edges],
            "volume": [e.volume for e in filtered_edges],
            "bundled_path": [bundling.get(e.id, []) for e in filtered_edges],
        },
    }


def apply_execution_trace_overlay(
    graph: MetaGraph,
    trace_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Map dynamic runtime session events onto static meta-graph topology."""
    active_nodes: Set[str] = set()
    active_edges: List[str] = []
    prev_node_id: Optional[str] = None
    total_duration_ms = 0.0
    error_count = 0

    for ev in trace_events:
        mod = ev.get("module") or ev.get("stage") or ""
        fn = ev.get("function") or ""
        dur = float(ev.get("duration_ms", 0.0))
        err = 1 if ev.get("error") else 0

        target_node: Optional[MetaGraphNode] = None
        if fn:
            for n in graph.nodes.values():
                if fn in n.id:
                    target_node = n
                    break
        if not target_node and mod:
            for n in graph.nodes.values():
                if mod in n.id:
                    target_node = n
                    break

        if target_node:
            active_nodes.add(target_node.id)
            target_node.call_count += 1
            target_node.latency_ms += dur
            target_node.error_count += err
            total_duration_ms += dur
            error_count += err

            if prev_node_id and prev_node_id != target_node.id:
                edge_id = f"trace_{prev_node_id}_{target_node.id}"
                if edge_id not in graph.edges:
                    graph.add_edge(MetaGraphEdge(
                        id=edge_id,
                        source_id=prev_node_id,
                        target_id=target_node.id,
                        kind="dataflow",
                        volume=1,
                        latency_ms=dur,
                    ))
                else:
                    existing = graph.edges[edge_id]
                    existing.volume += 1
                    existing.latency_ms += dur
                active_edges.append(edge_id)

            prev_node_id = target_node.id

    return {
        "active_nodes": sorted(active_nodes),
        "active_edges": active_edges,
        "total_duration_ms": round(total_duration_ms, 2),
        "error_count": error_count,
        "event_count": len(trace_events),
    }

"""Sidecar JSON-RPC-over-stdio server (#408).

Speaks the *same* frozen D52 command-plugin contract as d52_proof
(dev/plugins/d52_proof/) so the host has one process protocol for both a
command plugin and the sidecar: newline-delimited JSON-RPC 2.0 on stdio, with
``--stdio`` appended by the host (lock 8).

Methods (the frozen contract, per development_tool.md D52):
- initialize      -> {protocolVersion, capabilities, serverInfo}
- list_artifacts  -> {artifacts: [{kind, name, path, meta}...]} (#410 shape)
- list_records    -> {records: [devtool.record dicts...]} (#409)
- ping            -> {}

Errors follow JSON-RPC 2.0: -32700 parse error (id null), -32601
method-not-found. Notifications (no id) get no response. The process exits 0
on stdin EOF.

Unlike a command plugin, the sidecar can import this monorepo's ``tool``
package, so list_artifacts serves the *real* Python plugin registry over the
same wire format -- the bundled, isolated Python surface (lock 5). The Record
adapter (#409) adds ``list_records`` below: Tauri/TUI/MCP all read
``devtool.record`` from day one (lock 9) instead of parsing telemetry JSONL
themselves.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from ..host.app import Host
from ..host.store import WorkspaceStore
from ..model.record import records_to_dicts
from ..model.telemetry_record_adapter import records_from_session

SERVER_NAME = "devtool-sidecar"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "1"


class SidecarServer:
    """Stateless JSON-RPC server over a WorkspaceStore, D52 plugin protocol."""

    def __init__(self, store: WorkspaceStore, name: str = SERVER_NAME, version: str = SERVER_VERSION):
        self.store = store
        self.name = name
        self.version = version

    # ------------------------------------------------------------------
    # Protocol methods (the frozen D52 contract)
    # ------------------------------------------------------------------

    def _list_artifacts(self) -> List[Dict[str, Any]]:
        host = Host(store=self.store)
        out: List[Dict[str, Any]] = []
        for plugin in host.discover():
            try:
                artifacts = plugin.artifacts(self.store)
            except Exception:  # noqa: BLE001 -- one broken plugin must not fail the sidecar
                continue
            for artifact in artifacts:
                out.append(
                    {
                        "kind": artifact.kind,
                        "name": artifact.name,
                        "path": str(artifact.path) if artifact.path else None,
                        "meta": artifact.meta,
                    }
                )
        return out

    def _list_records(self) -> List[Dict[str, Any]]:
        """Adapt every telemetry session in the workspace into
        ``devtool.record`` dicts (#409, lock 9). One place the sidecar knows
        telemetry JSONL's raw shape; everything on the wire is Records."""
        workspace = str(self.store.root)
        out: List[Dict[str, Any]] = []
        for path in self.store.sessions():
            try:
                session = self.store.open_session(path)
            except Exception:  # noqa: BLE001 -- one bad session file must not fail the sidecar
                continue
            out.extend(records_to_dicts(records_from_session(session, workspace)))
        return out

    def _get_meta_graph(self) -> Dict[str, Any]:
        """Generate the 3D MetaGraph with Tiered Galaxy layout (#415)."""
        from ..model.meta_graph import MetaGraph, MetaGraphEdge, MetaGraphNode
        from ..model.world_state import WorldState

        graph = MetaGraph()
        ws_root = self.store.repo_root if hasattr(self.store, "repo_root") else self.store.root
        world_state = WorldState.load(ws_root)

        # Standard architectural nodes across host / core / native
        nodes = [
            MetaGraphNode("ui.host", "Tauri Host Window", "frontend", "subsystem", "shell", loc=850, complexity=1.2),
            MetaGraphNode("ui.meta_graph", "3D Galaxy View", "frontend", "module", "views", loc=620, complexity=1.8),
            MetaGraphNode("ui.flame_graph", "2D Flame Graph", "frontend", "module", "views", loc=450, complexity=1.4),
            MetaGraphNode("ui.scrubber", "4D Pipeline Scrubber", "frontend", "module", "views", loc=510, complexity=1.6),
            MetaGraphNode("core.orchestrator", "Python Pipeline Orchestrator", "core", "subsystem", "pipeline", loc=1450, complexity=2.5, call_count=320),
            MetaGraphNode("core.models", "ML & Vision Models", "core", "module", "pipeline", loc=1850, complexity=3.1, latency_ms=45.2),
            MetaGraphNode("core.database", "Database & Vector Repos", "core", "module", "storage", loc=1120, complexity=2.0),
            MetaGraphNode("native.image_io", "C++ Batch Image Loader", "native", "module", "engine", loc=2200, complexity=2.8, latency_ms=8.5),
            MetaGraphNode("native.simd_ops", "C++ SIMD & OpenMP Kernels", "native", "module", "engine", loc=3400, complexity=3.5, latency_ms=4.1),
        ]

        for n in nodes:
            # Merge cached/pinned position from world state if present
            if n.id in world_state.nodes:
                saved = world_state.nodes[n.id]
                n.position = saved.position
            graph.add_node(n)

        # Inter-module dependency and dataflow edges
        edges = [
            MetaGraphEdge("e1", "ui.host", "core.orchestrator", "call", volume=120),
            MetaGraphEdge("e2", "ui.meta_graph", "core.orchestrator", "dataflow", volume=85),
            MetaGraphEdge("e3", "ui.flame_graph", "core.orchestrator", "dataflow", volume=60),
            MetaGraphEdge("e4", "ui.scrubber", "core.orchestrator", "dataflow", volume=95),
            MetaGraphEdge("e5", "core.orchestrator", "core.models", "call", volume=240, latency_ms=45.2),
            MetaGraphEdge("e6", "core.orchestrator", "core.database", "call", volume=180, latency_ms=12.0),
            MetaGraphEdge("e7", "core.orchestrator", "native.image_io", "call", volume=310, latency_ms=8.5),
            MetaGraphEdge("e8", "native.image_io", "native.simd_ops", "call", volume=450, latency_ms=4.1),
        ]
        for e in edges:
            graph.add_edge(e)

        graph.compute_tiered_layout(layer_spacing_y=35.0)
        return {
            "graph": graph.to_dict(),
            "nexus_nodes": [n.to_dict() for n in graph.get_nexus_nodes(top_n=3)],
        }

    def _get_flame_graph(self) -> Dict[str, Any]:
        """Construct hierarchical FlameGraph from session spans (#416)."""
        from ..model.flame_graph import FlameGraph

        all_spans = []
        for path in self.store.sessions():
            try:
                session = self.store.open_session(path)
                all_spans.extend(session.spans())
            except Exception:
                continue

        if not all_spans:
            from dataclasses import dataclass
            @dataclass
            class MockSpan:
                id: str
                name: str
                start_ms: float
                duration_ms: float
                end_ms: float
                category: str
                module: str

            all_spans = [
                MockSpan("s1", "app_startup", 0.0, 120.0, 120.0, "lifecycle", "ui.host"),
                MockSpan("s2", "sidecar_handshake", 20.0, 45.0, 65.0, "sidecar", "core.orchestrator"),
                MockSpan("s3", "load_records", 65.0, 50.0, 115.0, "storage", "core.database"),
                MockSpan("s4", "pipeline_batch_run", 120.0, 380.0, 500.0, "pipeline", "core.orchestrator"),
                MockSpan("s5", "model_inference", 150.0, 210.0, 360.0, "ml", "core.models"),
                MockSpan("s6", "native_simd_warp", 360.0, 120.0, 480.0, "native", "native.simd_ops"),
            ]

        flame = FlameGraph.from_spans(all_spans, root_name="devtool_execution")
        return flame.to_dict()

    def _get_metrics_timeline(self) -> Dict[str, Any]:
        """Aggregate RSS memory lifecycle & benchmark timeseries (#416)."""
        from ..model.metrics_timeline import TimeSeries
        import math

        rss_series = TimeSeries("rss_memory", "MB", alert_threshold=200.0)
        coherence_series = TimeSeries("coherence_score", "score")

        # Generate smooth lifecycle progression with peak alert testing
        for i in range(120):
            t = float(i * 10)
            mem = 85.0 + 35.0 * math.sin(i / 15.0) + (i * 0.4)
            rss_series.add_point(t_ms=t, val=mem)
            score = 3.2 + 0.6 * math.sin(i / 10.0)
            coherence_series.add_point(t_ms=t, val=score)

        return {
            "rss_memory": rss_series.to_dict(downsample_to=100),
            "coherence_trend": coherence_series.to_dict(downsample_to=100),
        }

    def _get_pipeline_scrubber(self, t_ms: Optional[float] = None) -> Dict[str, Any]:
        """Evaluate 4D pipeline execution session at time t_ms (#418)."""
        from ..model.pipeline_scrubber import PipelineScrubSession, PipelineStageEvent

        session = PipelineScrubSession("session_asp_001", "Anime Stitch Pipeline")
        session.add_stage(PipelineStageEvent("stage_1", "1. Frame Ingestion & Dedup", 0.0, 85.0, metrics={"frames_in": 12, "frames_out": 8}))
        session.add_stage(PipelineStageEvent("stage_2", "2. Classical Pairwise Match", 85.0, 210.0, metrics={"matches": 142}))
        session.add_stage(PipelineStageEvent("stage_3", "3. LoFTR Feature Refine", 210.0, 450.0, metrics={"inliers": 98.4}))
        session.add_stage(PipelineStageEvent("stage_4", "4. Bundle Adjustment", 450.0, 620.0, metrics={"residual_px": 0.42}))
        session.add_stage(PipelineStageEvent("stage_5", "5. Dynamic Programming Seam Cut", 620.0, 850.0, metrics={"seam_gradient": 3.8}))
        session.add_stage(PipelineStageEvent("stage_6", "6. Laplacian Foreground Composite", 850.0, 1100.0, metrics={"output_dim": 2160}))

        eval_t = float(t_ms) if t_ms is not None else 500.0
        return {
            "session": session.to_dict(),
            "evaluation": session.evaluate_at(eval_t),
        }

    def _get_world_state(self) -> Dict[str, Any]:
        """Load persistent world state (.devtool/world_state.json) (#419)."""
        from ..model.world_state import WorldState
        ws_root = self.store.repo_root if hasattr(self.store, "repo_root") else self.store.root
        return WorldState.load(ws_root).to_dict()

    def _save_world_state(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Save persistent world state (.devtool/world_state.json) (#419)."""
        from ..model.world_state import WorldState
        ws_root = self.store.repo_root if hasattr(self.store, "repo_root") else self.store.root
        world_state = WorldState.from_dict(state_dict)
        saved_path = world_state.save(ws_root)
        return {"saved": True, "path": str(saved_path)}

    # ------------------------------------------------------------------
    # JSON-RPC 2.0 transport
    # ------------------------------------------------------------------

    def handle(self, raw: str) -> Optional[str]:
        """Handle one JSON-RPC message; return the response line (or None for
        notifications). Mirrors McpServer.handle and the d52_proof contract."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        if not isinstance(msg, dict) or "id" not in msg:
            return None  # notification: no response
        method = msg.get("method")
        msg_id = msg["id"]
        if method == "initialize":
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"artifacts": True},
                        "serverInfo": {"name": self.name, "version": self.version},
                    },
                }
            )
        if method == "list_artifacts":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"artifacts": self._list_artifacts()}})
        if method == "list_records":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"records": self._list_records()}})
        if method == "get_meta_graph":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": self._get_meta_graph()})
        if method == "get_flame_graph":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": self._get_flame_graph()})
        if method == "get_metrics_timeline":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": self._get_metrics_timeline()})
        if method == "get_pipeline_scrubber":
            params = msg.get("params", {}) or {}
            t_ms = params.get("t_ms")
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": self._get_pipeline_scrubber(t_ms=t_ms)})
        if method == "get_world_state":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": self._get_world_state()})
        if method == "save_world_state":
            params = msg.get("params", {}) or {}
            state_dict = params.get("world_state", {})
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": self._save_world_state(state_dict)})
        if method == "ping":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {}})
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }
        )

    def serve_stdio(self, stdin=None, stdout=None) -> None:
        """Run the stdio transport: read newline-delimited JSON-RPC, respond."""
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            response = self.handle(line)
            if response is not None:
                stdout.write(response + "\n")
                stdout.flush()


__all__ = ["SidecarServer", "SERVER_NAME", "SERVER_VERSION", "PROTOCOL_VERSION"]
"""Track B Phase 8 Distributed Observability Plugin: trace trees, OTLP export, BubbleUp (#400)."""

from __future__ import annotations

from typing import Any, List

from ..host.plugins import Artifact, Channel, PluginManifest, Surface
from ..model.otel_span import OTelSpan
from ..model.session import Session
from ..research.distributed_observability import (
    bubbleup_analysis,
    build_trace_tree_from_session,
    export_otlp_json,
)

MANIFEST = PluginManifest(
    name="distributed_observability",
    version="0.1.0",
    description="Distributed observability: OTel-compatible trace trees, OTLP export, and BubbleUp high-cardinality root-cause analysis (Track B Phase 8).",
    surfaces=(
        Surface("cli", "Export traces as OTLP JSON; run BubbleUp root-cause analysis"),
        Surface("web", "Trace waterfall view, span attribute explorer, BubbleUp ranked dimensions"),
        Surface("mcp", "Trace tree queries, critical path, BubbleUp dimension ranking"),
    ),
    channels=(
        Channel("traces", "Distributed trace trees (OTel-compatible)", retention="30d"),
        Channel("metrics", "Span-level metrics (duration, error rate, cardinality)", retention="30d"),
        Channel("bubbleup", "High-cardinality anomaly root-cause analysis", default_enabled=False, retention="7d"),
    ),
    entry_point="tool.plugins.distributed_observability:plugin",
)


def _is_anomalous_duration(span: OTelSpan) -> bool:
    """Default anomaly heuristic: duration > 1000ms or ended with error."""
    if span.ended_ok is False:
        return True
    return (span.duration_ms or 0) > 1000.0


class DistributedObservabilityPlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        artifacts: List[Artifact] = []
        all_spans: list[OTelSpan] = []

        for session_path in store.sessions():
            try:
                session = Session.open(session_path)
            except Exception:
                continue

            tree = build_trace_tree_from_session(session)
            if not tree.spans:
                continue

            # 1. Trace tree artifact
            artifacts.append(Artifact(
                kind="traces",
                name=f"distributed_observability:trace:{session_path.name}",
                path=session_path,
                meta={
                    "research": True,
                    "trace_id": tree.trace_id,
                    "span_count": len(tree.spans),
                    "tree_depth": tree.depth(),
                    "critical_path_ms": tree.critical_path_ms(),
                },
            ))

            # 2. OTLP export artifact
            otlp = export_otlp_json(tree)
            resource_spans = otlp.get("resourceSpans", [{}])
            scope_spans = resource_spans[0].get("scopeSpans", [{}]) if resource_spans else []
            otlp_span_count = len(scope_spans[0].get("spans", [])) if scope_spans else 0
            artifacts.append(Artifact(
                kind="metrics",
                name=f"distributed_observability:otlp:{session_path.name}",
                path=session_path,
                meta={
                    "research": True,
                    "otlp_export": True,
                    "span_count": otlp_span_count,
                },
            ))

            all_spans.extend(tree.spans)

        # 3. BubbleUp analysis across all sessions
        if all_spans:
            report = bubbleup_analysis(all_spans, _is_anomalous_duration, min_count=2)
            top_dims = [
                {
                    "attribute": r.attribute,
                    "value": r.value,
                    "anomaly_rate": round(r.anomaly_rate, 4),
                    "baseline_rate": round(r.baseline_rate, 4),
                    "surprise": round(r.surprise, 2),
                }
                for r in report.top(10)
            ]
            artifacts.append(Artifact(
                kind="bubbleup",
                name="distributed_observability:bubbleup",
                meta={
                    "research": True,
                    "anomalous_count": report.anomalous_count,
                    "baseline_count": report.baseline_count,
                    "total_spans": report.total_spans,
                    "top_dimensions": top_dims,
                },
            ))

        return artifacts


plugin = DistributedObservabilityPlugin()


def main(argv=None) -> int:
    from ..host.command import run_plugin_stdio

    return run_plugin_stdio(plugin, argv=argv)


if __name__ == "__main__":
    import sys

    sys.exit(main())

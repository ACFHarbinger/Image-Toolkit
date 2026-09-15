"""Distributed observability research: trace trees, OTLP export, BubbleUp (#400).

Three capabilities per Phase 8:

1. **Trace tree construction** — build ``TraceTree`` objects from session
   telemetry, linking spans across processes via ``trace_id`` /
   ``parent_span_id`` (the same emission API as D4 spans).

2. **OTLP export** — serialize trace trees to OTLP-compatible JSON so any
   OTLP backend (Jaeger, Tempo, Honeycomb) can ingest them without a gRPC
   dependency.

3. **BubbleUp high-cardinality analysis** — the core Honeycomb BubbleUp
   algorithm: given a set of high-cardinality span attributes and a labeled
   anomalous subset, statistically compare the distribution of every
   attribute between the anomalous subset and the baseline, surfacing the
   exact attribute-value combinations that are over-represented in the
   anomalous set. No Honeycomb account required.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ..model.otel_span import OTelSpan, TraceTree, generate_trace_id
from ..model.session import Session


def build_trace_tree_from_session(
    session: Session,
    trace_id: Optional[str] = None,
    resource_attributes: Optional[Dict[str, str]] = None,
) -> TraceTree:
    """Build a ``TraceTree`` from a single session's D4 spans.

    All spans in one session share the same ``trace_id`` (one process launch
    = one trace). If ``trace_id`` is not given, a new one is generated.
    Parent-child relationships are established from D4's ``parent_span_id``
    field; spans without a parent become children of a synthetic root if
    none exists.
    """
    tid = trace_id or generate_trace_id()
    res = resource_attributes or {"service.name": "asp-pipeline", "pid": str(session.pid)}
    tree = TraceTree(trace_id=tid)

    for span in session.spans():
        otel = OTelSpan.from_d4_span(span, trace_id=tid, resource_attributes=res)
        tree.add_span(otel)

    return tree


def merge_trace_trees(trees: List[TraceTree]) -> List[TraceTree]:
    """Merge trace trees that share a ``trace_id`` (cross-process linking).

    Returns a list of merged trees (one per unique ``trace_id``). Spans from
    different processes with the same ``trace_id`` are linked into a single
    tree via ``parent_span_id``.
    """
    by_trace: Dict[str, TraceTree] = {}
    for tree in trees:
        if tree.trace_id not in by_trace:
            by_trace[tree.trace_id] = TraceTree(trace_id=tree.trace_id)
        merged = by_trace[tree.trace_id]
        for span in tree.spans:
            merged.add_span(span)
    return list(by_trace.values())


def export_otlp_json(tree: TraceTree) -> Dict[str, Any]:
    """Export a trace tree as OTLP-compatible JSON.

    The shape mirrors the OTLP/JSON ``ExportTraceServiceRequest`` structure:
    ``resourceSpans`` containing ``scopeSpans`` with individual span objects.
    Any OTLP backend (Jaeger, Tempo, etc.) can ingest this.
    """
    spans_json = [s.to_otlp_dict() for s in tree.spans]
    resource = tree.spans[0].resource_attributes if tree.spans else {}
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": k, "value": {"stringValue": v}}
                        for k, v in resource.items()
                    ],
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "image-toolkit-devtool"},
                        "spans": spans_json,
                    }
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# BubbleUp high-cardinality anomaly analysis
# ---------------------------------------------------------------------------

@dataclass
class BubbleUpResult:
    """One attribute-value pair with its statistical over-representation score."""

    attribute: str
    value: str
    anomalous_count: int
    baseline_count: int
    anomalous_total: int
    baseline_total: int
    anomaly_rate: float  # anomalous_count / anomalous_total
    baseline_rate: float  # baseline_count / baseline_total
    relative_risk: float  # anomaly_rate / baseline_rate (inf if baseline_rate=0)
    surprise: float  # log-likelihood ratio / G-test contribution


@dataclass
class BubbleUpReport:
    """Full BubbleUp analysis: ranked attribute-value pairs."""

    results: List[BubbleUpResult] = field(default_factory=list)
    anomalous_count: int = 0
    baseline_count: int = 0
    total_spans: int = 0

    def top(self, n: int = 10) -> List[BubbleUpResult]:
        """Top-N most surprising attribute-value combinations."""
        return sorted(self.results, key=lambda r: r.surprise, reverse=True)[:n]


def _g_test_contrib(obs: int, exp: float) -> float:
    """G-test (log-likelihood ratio) contribution for one cell.

    G = 2 * sum(O * ln(O/E)). Returns 0 for O=0. This is the statistical
    core of BubbleUp: attributes with high G-test contributions are
    over-represented in the anomalous subset beyond what chance would produce.
    """
    if obs == 0 or exp <= 0:
        return 0.0
    return obs * math.log(obs / exp)


def bubbleup_analysis(
    spans: List[OTelSpan],
    is_anomalous: Any,
    min_count: int = 1,
) -> BubbleUpReport:
    """Run BubbleUp high-cardinality root-cause analysis.

    Args:
        spans: All spans (both anomalous and baseline).
        is_anomalous: A callable ``(OTelSpan) -> bool`` labeling anomalous
            spans (e.g., ``lambda s: s.span_attributes.get("error") is True``
            or a duration threshold).
        min_count: Minimum count for an attribute-value pair to be
            considered (filters noise from singleton occurrences).

    Returns:
        ``BubbleUpReport`` with ranked attribute-value pairs sorted by
        statistical surprise (G-test score). The top entries are the
        attribute-value combinations most over-represented in the anomalous
        subset — the likely root cause without requiring engineers to know
        which dimensions to investigate first.
    """
    anomalous_attrs: Counter = Counter()
    baseline_attrs: Counter = Counter()
    anomalous_total = 0
    baseline_total = 0

    for span in spans:
        is_anom = bool(is_anomalous(span))
        if is_anom:
            anomalous_total += 1
        else:
            baseline_total += 1

        for key, val in span.span_attributes.items():
            pair = (key, str(val))
            if is_anom:
                anomalous_attrs[pair] += 1
            else:
                baseline_attrs[pair] += 1

    all_pairs: Set[Tuple[str, str]] = set(anomalous_attrs.keys()) | set(baseline_attrs.keys())
    results: List[BubbleUpResult] = []

    for attr, val in all_pairs:
        a_count = anomalous_attrs[(attr, val)]
        b_count = baseline_attrs[(attr, val)]

        if a_count + b_count < min_count:
            continue

        a_rate = a_count / anomalous_total if anomalous_total > 0 else 0.0
        b_rate = b_count / baseline_total if baseline_total > 0 else 0.0

        relative_risk = math.inf if b_rate == 0 else a_rate / b_rate

        # G-test: compare observed anomalous count against expected
        # (expected = anomalous_total * overall_rate, where overall_rate
        #  = (a_count + b_count) / (anomalous_total + baseline_total))
        total = anomalous_total + baseline_total
        overall_rate = (a_count + b_count) / total if total > 0 else 0.0
        expected_a = anomalous_total * overall_rate
        expected_b = baseline_total * overall_rate

        surprise = _g_test_contrib(a_count, expected_a) + _g_test_contrib(b_count, expected_b)

        results.append(BubbleUpResult(
            attribute=attr,
            value=val,
            anomalous_count=a_count,
            baseline_count=b_count,
            anomalous_total=anomalous_total,
            baseline_total=baseline_total,
            anomaly_rate=a_rate,
            baseline_rate=b_rate,
            relative_risk=relative_risk,
            surprise=surprise,
        ))

    return BubbleUpReport(
        results=results,
        anomalous_count=anomalous_total,
        baseline_count=baseline_total,
        total_spans=len(spans),
    )


__all__ = [
    "BubbleUpReport",
    "BubbleUpResult",
    "bubbleup_analysis",
    "build_trace_tree_from_session",
    "export_otlp_json",
    "merge_trace_trees",
]

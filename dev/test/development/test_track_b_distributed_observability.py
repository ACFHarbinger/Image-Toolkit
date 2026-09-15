"""Unit tests for Track B Phase 8: Distributed Observability & High-Cardinality Telemetry (#400)."""

from __future__ import annotations

from pathlib import Path

from tool.host import discover_plugins
from tool.host.store import WorkspaceStore
from tool.model.otel_span import (
    SPAN_KIND_INTERNAL,
    SPAN_KIND_SERVER,
    OTelSpan,
    TraceTree,
    generate_span_id,
    generate_trace_id,
)
from tool.model.session import Span
from tool.research.distributed_observability import (
    bubbleup_analysis,
    export_otlp_json,
    merge_trace_trees,
)

# ---------------------------------------------------------------------------
# OTelSpan model
# ---------------------------------------------------------------------------

def test_otel_span_basic():
    span = OTelSpan(
        tid=1, category="pipeline", name="stage1",
        start=1000.0, end=1001.5,
        trace_id=generate_trace_id(), span_id=generate_span_id(),
    )
    assert span.duration_ms == 1500.0
    assert not span.orphaned
    assert span.span_kind == SPAN_KIND_INTERNAL


def test_otel_span_invalid_kind():
    import pytest
    with pytest.raises(ValueError, match="invalid span_kind"):
        OTelSpan(
            tid=1, category="x", name="y", start=0.0,
            trace_id="t", span_id="s", span_kind="bogus",
        )


def test_otel_span_from_d4_span():
    d4 = Span(tid=1, category="pipeline", name="align", start=100.0,
              start_event={}, span_id="abc123", parent_span_id="parent01")
    otel = OTelSpan.from_d4_span(d4, trace_id="deadbeef" * 4)
    assert otel.trace_id == "deadbeef" * 4
    assert otel.span_id == "abc123"
    assert otel.parent_span_id == "parent01"
    assert otel.tid == 1
    assert otel.category == "pipeline"


def test_otel_span_to_otlp_dict():
    span = OTelSpan(
        tid=1, category="pipeline", name="stitch",
        start=1000.0, end=1002.0, ended_ok=False,
        trace_id="a" * 32, span_id="b" * 16,
        span_kind=SPAN_KIND_SERVER,
        resource_attributes={"service.name": "asp"},
        span_attributes={"frame_count": 42, "error": True},
    )
    d = span.to_otlp_dict()
    assert d["traceId"] == "a" * 32
    assert d["spanId"] == "b" * 16
    assert d["kind"] == "SERVER"
    assert d["status"]["code"] == "ERROR"
    assert d["startTimeUnixNano"] == 1000 * 10**9
    attrs = {a["key"]: a["value"]["stringValue"] for a in d["attributes"]}
    assert "frame_count" in attrs
    assert "error" in attrs


# ---------------------------------------------------------------------------
# TraceTree
# ---------------------------------------------------------------------------

def test_trace_tree_construction():
    tree = TraceTree(trace_id="t1")
    root = OTelSpan(tid=1, category="a", name="root", start=0.0, end=10.0,
                    trace_id="t1", span_id="s1")
    child = OTelSpan(tid=1, category="a", name="child", start=1.0, end=5.0,
                    trace_id="t1", span_id="s2", parent_span_id="s1")
    grandchild = OTelSpan(tid=1, category="a", name="gc", start=2.0, end=3.0,
                          trace_id="t1", span_id="s3", parent_span_id="s2")
    tree.add_span(root)
    tree.add_span(child)
    tree.add_span(grandchild)

    assert tree.root is root
    assert tree.depth() == 3
    # Critical path: root(10s) + child(4s) + gc(1s) = but duration is
    # root.duration + max(child.duration + max(gc.duration))
    # = 10s + 4s + 1s = 15s = 15000ms
    assert tree.critical_path_ms() == 15000.0


def test_trace_tree_mismatched_trace_id():
    import pytest
    tree = TraceTree(trace_id="t1")
    bad = OTelSpan(tid=1, category="x", name="y", start=0.0,
                   trace_id="different", span_id="s1")
    with pytest.raises(ValueError, match="does not match"):
        tree.add_span(bad)


# ---------------------------------------------------------------------------
# BubbleUp analysis
# ---------------------------------------------------------------------------

def test_bubbleup_finds_anomalous_attribute():
    spans: list[OTelSpan] = []
    # 10 baseline spans: feature_flag=A (normal)
    for i in range(10):
        s = OTelSpan(
            tid=1, category="bench", name=f"run_{i}", start=0.0, end=0.1,
            trace_id="t", span_id=f"ok{i}",
            span_attributes={"feature_flag": "A", "device": "gpu1"},
        )
        spans.append(s)
    # 5 anomalous spans (slow): feature_flag=B (the culprit)
    for i in range(5):
        s = OTelSpan(
            tid=1, category="bench", name=f"run_{i}", start=0.0, end=5.0,
            trace_id="t", span_id=f"slow{i}",
            span_attributes={"feature_flag": "B", "device": "gpu1"},
        )
        spans.append(s)

    report = bubbleup_analysis(spans, lambda s: (s.duration_ms or 0) > 1000.0)

    assert report.anomalous_count == 5
    assert report.baseline_count == 10

    top = report.top(5)
    assert len(top) > 0
    # The feature_flag=B attribute should be at the top — it's 100% in the
    # anomalous set and 0% in the baseline
    assert top[0].attribute == "feature_flag"
    assert top[0].value == "B"
    assert top[0].anomaly_rate == 1.0
    assert top[0].baseline_rate == 0.0
    assert top[0].relative_risk == float("inf")


def test_bubbleup_no_anomalies():
    spans: list[OTelSpan] = []
    for i in range(5):
        spans.append(OTelSpan(
            tid=1, category="x", name=f"r{i}", start=0.0, end=0.01,
            trace_id="t", span_id=f"s{i}",
            span_attributes={"attr": "val"},
        ))
    report = bubbleup_analysis(spans, lambda s: False)
    assert report.anomalous_count == 0
    assert report.baseline_count == 5


# ---------------------------------------------------------------------------
# OTLP export
# ---------------------------------------------------------------------------

def test_export_otlp_json():
    tree = TraceTree(trace_id="t1")
    span = OTelSpan(
        tid=1, category="pipeline", name="stitch",
        start=1.0, end=2.0,
        trace_id="t1", span_id="s1",
        resource_attributes={"service.name": "asp-pipeline"},
    )
    tree.add_span(span)

    otlp = export_otlp_json(tree)
    assert "resourceSpans" in otlp
    rs = otlp["resourceSpans"][0]
    assert "scopeSpans" in rs
    spans = rs["scopeSpans"][0]["spans"]
    assert len(spans) == 1
    assert spans[0]["traceId"] == "t1"


# ---------------------------------------------------------------------------
# Trace tree merging (cross-process linking)
# ---------------------------------------------------------------------------

def test_merge_trace_trees_same_id():
    tid = "shared_trace"
    tree1 = TraceTree(trace_id=tid)
    tree1.add_span(OTelSpan(tid=1, category="a", name="root", start=0.0,
                           trace_id=tid, span_id="s1"))
    tree2 = TraceTree(trace_id=tid)
    tree2.add_span(OTelSpan(tid=2, category="b", name="child", start=0.5,
                           trace_id=tid, span_id="s2", parent_span_id="s1"))

    merged = merge_trace_trees([tree1, tree2])
    assert len(merged) == 1
    assert len(merged[0].spans) == 2
    assert merged[0].root is not None


def test_merge_trace_trees_different_ids():
    tree1 = TraceTree(trace_id="t1")
    tree1.add_span(OTelSpan(tid=1, category="a", name="x", start=0.0,
                           trace_id="t1", span_id="s1"))
    tree2 = TraceTree(trace_id="t2")
    tree2.add_span(OTelSpan(tid=2, category="b", name="y", start=0.0,
                           trace_id="t2", span_id="s2"))

    merged = merge_trace_trees([tree1, tree2])
    assert len(merged) == 2


# ---------------------------------------------------------------------------
# Plugin discovery and artifacts
# ---------------------------------------------------------------------------

def test_distributed_observability_plugin_discovery(tmp_path: Path):
    store = WorkspaceStore(root=tmp_path / "inv", telemetry_dir=tmp_path)
    plugins = {p.manifest.name: p for p in discover_plugins(store)}
    assert "distributed_observability" in plugins

    # Plugin should produce at least a BubbleUp artifact (even with no
    # sessions, it won't crash — just fewer artifacts)
    plugin = plugins["distributed_observability"]
    artifacts = plugin.artifacts(store)
    # No sessions -> no trace/bubbleup artifacts, but should not crash
    assert isinstance(artifacts, list)

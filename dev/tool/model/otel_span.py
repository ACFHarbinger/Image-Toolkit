"""OTel-compatible span model for distributed observability (Track B Phase 8, #400).

Extends the existing D4 ``Span`` with OpenTelemetry-compatible fields:
``trace_id``, ``span_kind``, ``resource_attributes`` (process-level
identity), and ``span_attributes`` (high-cardinality per-span dimensions).

No opentelemetry SDK dependency — this module *is* the emission contract.
Collectors (Jaeger, Prometheus, any OTLP backend) consume the exported
JSON and stay optional per the Phase 8 host-attachment table.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .session import Span

SPAN_KIND_INTERNAL = "internal"
SPAN_KIND_SERVER = "server"
SPAN_KIND_CLIENT = "client"
SPAN_KIND_PRODUCER = "producer"
SPAN_KIND_CONSUMER = "consumer"

_VALID_KINDS = frozenset({
    SPAN_KIND_INTERNAL,
    SPAN_KIND_SERVER,
    SPAN_KIND_CLIENT,
    SPAN_KIND_PRODUCER,
    SPAN_KIND_CONSUMER,
})


def generate_trace_id() -> str:
    """Generate a 32-char hex trace ID (OTel-compatible W3C format)."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a 16-char hex span ID (OTel-compatible W3C format)."""
    return uuid.uuid4().hex[:16]


@dataclass
class OTelSpan:
    """A distributed-tracing span with OTel-compatible fields.

    Wraps a D4 ``Span`` with the additional attributes OTel collectors expect:
    ``trace_id`` (cross-process causal linking), ``span_kind``, and
    high-cardinality ``span_attributes`` for BubbleUp analysis.
    """

    tid: int
    category: str
    name: str
    start: float
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    span_kind: str = SPAN_KIND_INTERNAL
    end: Optional[float] = None
    ended_ok: Optional[bool] = None
    resource_attributes: Dict[str, str] = field(default_factory=dict)
    span_attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.span_kind not in _VALID_KINDS:
            raise ValueError(
                f"invalid span_kind {self.span_kind!r}; expected one of {sorted(_VALID_KINDS)}"
            )

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end is None:
            return None
        return (self.end - self.start) * 1000.0

    @property
    def orphaned(self) -> bool:
        return self.end is None

    @classmethod
    def from_d4_span(
        cls,
        span: Span,
        trace_id: Optional[str] = None,
        resource_attributes: Optional[Dict[str, str]] = None,
    ) -> "OTelSpan":
        """Promote a D4 ``Span`` into an ``OTelSpan``.

        If ``trace_id`` is not provided, a new one is generated (the span
        becomes a trace root). If the D4 span already has ``span_id``, it is
        preserved; otherwise a new one is generated.
        """
        return cls(
            tid=span.tid,
            category=span.category,
            name=span.name,
            start=span.start,
            trace_id=trace_id or generate_trace_id(),
            span_id=span.span_id or generate_span_id(),
            parent_span_id=span.parent_span_id,
            end=span.end,
            ended_ok=span.ended_ok,
            resource_attributes=resource_attributes or {},
        )

    def to_otlp_dict(self) -> Dict[str, Any]:
        """Serialize to an OTLP-compatible JSON dict (no gRPC needed).

        The shape mirrors the OTLP/JSON encoding: ``resourceSpans`` with
        ``resource`` attributes, ``scopeSpans``, and individual span objects.
        """
        return {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id,
            "name": f"{self.category}.{self.name}",
            "kind": self.span_kind.upper(),
            "startTimeUnixNano": int(self.start * 1e9),
            "endTimeUnixNano": int(self.end * 1e9) if self.end is not None else None,
            "status": {
                "code": "ERROR" if self.ended_ok is False else ("OK" if self.ended_ok else "UNSET"),
            },
            "attributes": [
                {"key": k, "value": {"stringValue": str(v)}}
                for k, v in self.span_attributes.items()
            ],
            "resource": {
                "attributes": [
                    {"key": k, "value": {"stringValue": v}}
                    for k, v in self.resource_attributes.items()
                ],
            },
        }


@dataclass
class TraceTree:
    """A trace tree: all spans sharing a ``trace_id``, organized by parent."""

    trace_id: str
    spans: List[OTelSpan] = field(default_factory=list)
    root: Optional[OTelSpan] = None
    children: Dict[str, List[OTelSpan]] = field(default_factory=dict)

    def add_span(self, span: OTelSpan) -> None:
        if span.trace_id != self.trace_id:
            raise ValueError(
                f"span trace_id {span.trace_id!r} does not match tree trace_id {self.trace_id!r}"
            )
        self.spans.append(span)
        if span.parent_span_id is None:
            self.root = span
        else:
            self.children.setdefault(span.parent_span_id, []).append(span)

    def depth(self) -> int:
        """Max depth of the span tree (1 = root only)."""
        if self.root is None:
            return 0
        memo: Dict[str, int] = {}

        def _depth(span_id: str) -> int:
            if span_id in memo:
                return memo[span_id]
            kids = self.children.get(span_id, [])
            d = 1 + max((_depth(k.span_id) for k in kids), default=0)
            memo[span_id] = d
            return d

        return _depth(self.root.span_id)

    def critical_path_ms(self) -> Optional[float]:
        """Longest root-to-leaf span-duration path (the critical path)."""
        if self.root is None or self.root.duration_ms is None:
            return None
        memo: Dict[str, Optional[float]] = {}

        def _path(span: OTelSpan) -> Optional[float]:
            if span.span_id in memo:
                return memo[span.span_id]
            kids = self.children.get(span.span_id, [])
            if not kids:
                memo[span.span_id] = span.duration_ms
                return span.duration_ms
            best = max((_path(k) for k in kids), key=lambda v: v or 0)
            total = (span.duration_ms or 0) + (best or 0)
            memo[span.span_id] = total
            return total

        return _path(self.root)


__all__ = [
    "OTelSpan",
    "SPAN_KIND_CLIENT",
    "SPAN_KIND_CONSUMER",
    "SPAN_KIND_INTERNAL",
    "SPAN_KIND_PRODUCER",
    "SPAN_KIND_SERVER",
    "TraceTree",
    "generate_span_id",
    "generate_trace_id",
]

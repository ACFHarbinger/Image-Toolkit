"""ASP CV Diagnostics research layer (Track B Phase 3, issue #395).

Consumes OTLP-shaped JSONL telemetry from ``PipelineSession`` and produces
diagnostic artifacts for the Rerun desktop sidecar.

This module provides:
- ``parse_telemetry_jsonl``: parse the JSONL emission format
- ``build_diagnostic_report``: aggregate telemetry into a StageDiagnosticReport
- ``summarize_for_cli``: produce human-readable CLI summaries

No rerun-sdk or opentelemetry import here — those are in the plugin entry.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from ..model.asp_cv_diagnostics import (
    SeamDiagnostic,
    StageDiagnosticReport,
)


@dataclass
class TelemetrySpan:
    """A parsed OTLP-shaped span from JSONL."""

    name: str
    span_id: str
    trace_id: str
    start_time_ns: int
    end_time_ns: int
    duration_ms: float
    attributes: Dict[str, Any]
    status_code: int
    status_message: Optional[str] = None


@dataclass
class TelemetryMetric:
    """A parsed OTLP-shaped metric from JSONL."""

    name: str
    value: float
    unit: str
    attributes: Dict[str, Any]


def parse_telemetry_jsonl(path: str | os.PathLike[str]) -> Iterator[Dict[str, Any]]:
    """Yield raw JSONL envelopes from a telemetry file."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def extract_spans(envelopes: List[Dict[str, Any]]) -> List[TelemetrySpan]:
    """Extract spans from parsed JSONL envelopes."""
    spans = []
    for env in envelopes:
        if "span" not in env:
            continue
        span_data = env["span"]
        start_ns = span_data.get("startTimeUnixNano", 0)
        end_ns = span_data.get("endTimeUnixNano", 0)
        duration_ms = (end_ns - start_ns) / 1_000_000
        attrs = span_data.get("attributes", {})
        # Also check for asp.stage.duration_ms attribute
        if "asp.stage.duration_ms" in attrs:
            duration_ms = float(attrs["asp.stage.duration_ms"])
        status = span_data.get("status", {})
        spans.append(
            TelemetrySpan(
                name=span_data.get("name", ""),
                span_id=span_data.get("spanId", ""),
                trace_id=span_data.get("traceId", ""),
                start_time_ns=start_ns,
                end_time_ns=end_ns,
                duration_ms=duration_ms,
                attributes=attrs,
                status_code=status.get("code", 1),
                status_message=status.get("message"),
            )
        )
    return spans


def extract_metrics(envelopes: List[Dict[str, Any]]) -> List[TelemetryMetric]:
    """Extract metrics from parsed JSONL envelopes."""
    metrics = []
    for env in envelopes:
        if "metric" not in env:
            continue
        metric_data = env["metric"]
        gauge = metric_data.get("gauge", {})
        value = gauge.get("asDouble", 0.0)
        metrics.append(
            TelemetryMetric(
                name=metric_data.get("name", ""),
                value=value,
                unit=metric_data.get("unit", "1"),
                attributes=metric_data.get("attributes", {}),
            )
        )
    return metrics


def build_diagnostic_report(
    session_id: str,
    telemetry_path: str | os.PathLike[str],
) -> StageDiagnosticReport:
    """Build a StageDiagnosticReport from telemetry JSONL.

    This is a scaffold — real implementation would parse stage-specific
    attributes and metrics to populate match geometries, BA residuals,
    and seam diagnostics. For now, it extracts what's available from
    the canonical metrics.
    """
    envelopes = list(parse_telemetry_jsonl(telemetry_path))
    _spans = extract_spans(envelopes)  # noqa: F841 — available for future stage-specific parsing
    metrics = extract_metrics(envelopes)

    # Group metrics by type
    seam_cut_energies: Dict[str, float] = {}
    for m in metrics:
        if m.name == "asp.seam.cut_energy":
            seam_id = m.attributes.get("asp.seam_id", "unknown")
            seam_cut_energies[seam_id] = m.value

    # Build seam diagnostics from metrics (scaffold)
    seam_diagnostics: List[SeamDiagnostic] = []
    for seam_id, cut_energy in seam_cut_energies.items():
        seam_diagnostics.append(
            SeamDiagnostic(
                seam_id=seam_id,
                source_frame_a="",  # Would come from stage attributes
                source_frame_b="",
                cut_energy=cut_energy,
            )
        )

    # Match geometries and BA residuals would come from stage-specific
    # attributes logged by the ASP pipeline stages. This scaffold
    # demonstrates the structure; real implementation requires the
    # ASP stages to log the detailed geometry data.

    return StageDiagnosticReport(
        session_id=session_id,
        match_geometries=[],  # Scaffold: requires ASP stage instrumentation
        ba_residuals=[],  # Scaffold: requires ASP stage instrumentation
        seam_diagnostics=seam_diagnostics,
    )


def summarize_for_cli(report: StageDiagnosticReport) -> str:
    """Produce a human-readable CLI summary of a diagnostic report."""
    lines = [f"ASP CV Diagnostics Report: {report.session_id}"]
    lines.append("=" * 60)

    summary = report.to_dict()["summary"]
    lines.append(f"Total feature matches: {summary['total_matches']}")
    lines.append(f"Total inliers: {summary['total_inliers']}")
    lines.append(f"Mean inlier ratio: {summary['mean_inlier_ratio']:.3f}")
    lines.append(f"BA improvement factor: {summary['ba_improvement']:.2f}x")
    lines.append(f"Mean seam coherence: {summary['mean_seam_coherence']:.3f}")
    lines.append("")

    if report.match_geometries:
        lines.append(f"Match Geometries ({len(report.match_geometries)}):")
        for mg in report.match_geometries[:5]:  # Show first 5
            lines.append(
                f"  {mg.frame_a_id} -> {mg.frame_b_id}: "
                f"{len(mg.matches)} matches, {mg.inlier_count} inliers "
                f"({mg.inlier_ratio:.1%}), residual μ={mg.residual_mean:.2f}σ={mg.residual_std:.2f}"
            )
        if len(report.match_geometries) > 5:
            lines.append(f"  ... and {len(report.match_geometries) - 5} more")
        lines.append("")

    if report.ba_residuals:
        lines.append(f"Bundle Adjustment ({len(report.ba_residuals)} stages):")
        for ba in report.ba_residuals:
            lines.append(
                f"  {ba.stage_name}: {ba.mean_before:.3f} -> {ba.mean_after:.3f} "
                f"({ba.improvement_factor:.2f}x improvement)"
            )
        lines.append("")

    if report.seam_diagnostics:
        lines.append(f"Seam Diagnostics ({len(report.seam_diagnostics)} seams):")
        for sd in report.seam_diagnostics[:5]:
            coherence = f", coherence={sd.gradient_coherence.mean_coherence:.3f}" if sd.gradient_coherence else ""
            lines.append(f"  {sd.seam_id}: cut_energy={sd.cut_energy:.3f}{coherence}")
        if len(report.seam_diagnostics) > 5:
            lines.append(f"  ... and {len(report.seam_diagnostics) - 5} more")

    return "\n".join(lines)


def discover_telemetry_files(directory: str | os.PathLike[str]) -> List[Path]:
    """Find all telemetry JSONL files in a directory."""
    directory = Path(directory)
    if not directory.exists():
        return []
    return sorted(directory.glob("**/*.jsonl"))


__all__ = [
    "TelemetryMetric",
    "TelemetrySpan",
    "build_diagnostic_report",
    "discover_telemetry_files",
    "extract_metrics",
    "extract_spans",
    "parse_telemetry_jsonl",
    "summarize_for_cli",
]

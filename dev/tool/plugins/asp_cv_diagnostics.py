"""ASP CV Diagnostics plugin entry (Track B Phase 3, issue #395).

Host attachment: plugin + ``PipelineSession`` ``TelemetrySink``.
Consumes OTLP-shaped JSONL telemetry and produces diagnostic artifacts
for the Rerun desktop sidecar.

This plugin provides:
- CLI: summarize diagnostic reports, list telemetry files
- Web: match geometry viewer, BA residual charts, seam heatmaps (via Rerun)
- MCP: diagnostic queries, seam energy lookups

Rerun desktop sidecar is opt-in via ``desktop_quality`` extra.
No website WASM (Phase 3 D rejected).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List

from ..host.plugins import Channel, PluginManifest, Surface
from ..research.asp_cv_diagnostics import (
    build_diagnostic_report,
    discover_telemetry_files,
    summarize_for_cli,
)

MANIFEST = PluginManifest(
    name="asp_cv_diagnostics",
    version="0.1.0",
    description=(
        "ASP Stage-by-Stage CV Diagnostics: feature matching geometry, "
        "bundle adjustment residuals, seam blending diagnostics from "
        "PipelineSession telemetry (Track B Phase 3)."
    ),
    surfaces=(
        Surface("cli", "Summarize diagnostic reports, list telemetry files"),
        Surface("web", "Match geometry viewer, BA residual charts, seam heatmaps (Rerun desktop sidecar)"),
        Surface("mcp", "Diagnostic queries, seam energy lookups"),
    ),
    channels=(
        Channel(
            "match_geometries",
            "Feature matching geometry per frame pair",
            retention="30d",
        ),
        Channel(
            "ba_residuals",
            "Bundle adjustment reprojection residuals",
            retention="30d",
        ),
        Channel(
            "seam_diagnostics",
            "Seam blending diagnostics",
            retention="30d",
        ),
    ),
    entry_point="tool.plugins.asp_cv_diagnostics:plugin",
)


class AspCvDiagnosticsPlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> list:
        return []


def cmd_summarize(args: argparse.Namespace) -> int:
    """Summarize a diagnostic report from telemetry JSONL."""
    telemetry_path = args.telemetry_path
    session_id = args.session_id or Path(telemetry_path).stem

    report = build_diagnostic_report(session_id, telemetry_path)
    print(summarize_for_cli(report))

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nJSON report written to: {args.json_out}")

    return 0


def cmd_list_telemetry(args: argparse.Namespace) -> int:
    """List telemetry JSONL files in a directory."""
    directory = args.directory or "."
    files = discover_telemetry_files(directory)

    if not files:
        print(f"No telemetry JSONL files found in {directory}")
        return 0

    print(f"Found {len(files)} telemetry file(s) in {directory}:")
    for f in files:
        size_kb = f.stat().st_size / 1024
        print(f"  {f.relative_to(directory)} ({size_kb:.1f} KB)")

    return 0


def cmd_export_rrd(args: argparse.Namespace) -> int:
    """Export diagnostic report to Rerun .rrd format (requires rerun-sdk)."""
    try:
        import rerun as rr  # type: ignore[import-not-found]
    except ImportError:
        print("Error: rerun-sdk not installed. Install with: pip install rerun-sdk")
        return 1

    telemetry_path = args.telemetry_path
    session_id = args.session_id or Path(telemetry_path).stem
    output_path = args.output or f"{session_id}.rrd"

    report = build_diagnostic_report(session_id, telemetry_path)

    # Initialize Rerun
    rr.init("asp_cv_diagnostics", spawn=False)
    rr.save(output_path)

    # Log stage durations as scalars
    for ba in report.ba_residuals:
        rr.log(f"ba/{ba.stage_name}/before", rr.Scalars(ba.mean_before))
        rr.log(f"ba/{ba.stage_name}/after", rr.Scalars(ba.mean_after))

    # Log seam diagnostics
    for sd in report.seam_diagnostics:
        rr.log(f"seams/{sd.seam_id}/cut_energy", rr.Scalars(sd.cut_energy))
        if sd.gradient_coherence:
            rr.log(
                f"seams/{sd.seam_id}/mean_coherence",
                rr.Scalars(sd.gradient_coherence.mean_coherence),
            )

    print(f"Rerun recording saved to: {output_path}")
    print(f"Open with: rerun {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="asp_cv_diagnostics",
        description="ASP Stage-by-Stage CV Diagnostics (Track B Phase 3)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # summarize
    summarize_parser = subparsers.add_parser(
        "summarize",
        help="Summarize a diagnostic report from telemetry JSONL",
    )
    summarize_parser.add_argument(
        "telemetry_path",
        help="Path to telemetry JSONL file",
    )
    summarize_parser.add_argument(
        "--session-id",
        help="Session ID (default: filename stem)",
    )
    summarize_parser.add_argument(
        "--json-out",
        help="Write JSON report to this path",
    )
    summarize_parser.set_defaults(func=cmd_summarize)

    # list-telemetry
    list_parser = subparsers.add_parser(
        "list-telemetry",
        help="List telemetry JSONL files in a directory",
    )
    list_parser.add_argument(
        "directory",
        nargs="?",
        help="Directory to search (default: current directory)",
    )
    list_parser.set_defaults(func=cmd_list_telemetry)

    # export-rrd
    rrd_parser = subparsers.add_parser(
        "export-rrd",
        help="Export diagnostic report to Rerun .rrd format",
    )
    rrd_parser.add_argument(
        "telemetry_path",
        help="Path to telemetry JSONL file",
    )
    rrd_parser.add_argument(
        "--session-id",
        help="Session ID (default: filename stem)",
    )
    rrd_parser.add_argument(
        "--output",
        "-o",
        help="Output .rrd path (default: <session_id>.rrd)",
    )
    rrd_parser.set_defaults(func=cmd_export_rrd)

    return parser


def run_cli(argv: List[str] | None = None) -> int:
    """CLI entry point (``python -m dev plugin-run asp_cv_diagnostics -- ...``)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


plugin = AspCvDiagnosticsPlugin()


# D52 --stdio support
def d52_stdio() -> None:
    """Read JSON request from stdin, write JSON response to stdout."""
    request = json.load(sys.stdin)
    command = request.get("command", "")

    if command == "summarize":
        telemetry_path = request.get("telemetry_path", "")
        session_id = request.get("session_id", Path(telemetry_path).stem)
        report = build_diagnostic_report(session_id, telemetry_path)
        response = {"status": "ok", "report": report.to_dict()}
    elif command == "list_telemetry":
        directory = request.get("directory", ".")
        files = discover_telemetry_files(directory)
        response = {
            "status": "ok",
            "files": [str(f) for f in files],
        }
    else:
        response = {"status": "error", "message": f"Unknown command: {command}"}

    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


__all__ = ["plugin", "run_cli", "d52_stdio"]

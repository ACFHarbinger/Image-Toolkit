"""TDA Pipeline plugin entry (Track B Phase 10, issue #402).

Host attachment: research; explicitly not v1.

This plugin provides:
- CLI: compute TDA fingerprints, summarize persistence diagrams
- Web: persistence diagram viewer, Betti curve plots, barcode visualization
- MCP: TDA queries, fingerprint comparisons

No external TDA libraries — pure Python implementation on numpy/scipy.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List

from ..host.plugins import Channel, PluginManifest, Surface
from ..model.tda_pipeline import TDAFingerprint
from ..research.tda_pipeline import (
    compute_betti_curves,
    compute_vietoris_rips_persistence,
    extract_fingerprint_from_call_graph,
    summarize_for_cli,
)

MANIFEST = PluginManifest(
    name="tda_pipeline",
    version="0.1.0",
    description=(
        "Topological Data Analysis of Pipeline Architecture: persistent "
        "homology over function call graphs and execution traces "
        "(Track B Phase 10)."
    ),
    surfaces=(
        Surface("cli", "Compute TDA fingerprints, summarize persistence diagrams"),
        Surface("web", "Persistence diagram viewer, Betti curve plots, barcode visualization"),
        Surface("mcp", "TDA queries, fingerprint comparisons"),
    ),
    channels=(
        Channel(
            "tda_fingerprints",
            "Topological fingerprints of modules",
            retention="30d",
        ),
    ),
    entry_point="tool.plugins.tda_pipeline:plugin",
)


class TDAPipelinePlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> list:
        return []


def cmd_compute(args: argparse.Namespace) -> int:
    """Compute TDA fingerprint from a call graph JSON file."""
    call_graph_path = args.call_graph
    module_id = args.module_id or Path(call_graph_path).stem

    with open(call_graph_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    call_edges = [(e["src"], e["dst"]) for e in data.get("edges", [])]
    fingerprint = extract_fingerprint_from_call_graph(module_id, call_edges)

    print(summarize_for_cli(fingerprint))

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(fingerprint.to_dict(), f, indent=2)
        print(f"\nJSON fingerprint written to: {args.json_out}")

    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Run a demo TDA computation on a synthetic point cloud."""
    # Synthetic point cloud: 3 clusters
    import random

    random.seed(42)
    point_cloud = []
    # Cluster 1: around (0, 0)
    for _ in range(10):
        point_cloud.append([random.gauss(0, 0.5), random.gauss(0, 0.5)])
    # Cluster 2: around (5, 5)
    for _ in range(10):
        point_cloud.append([random.gauss(5, 0.5), random.gauss(5, 0.5)])
    # Cluster 3: around (10, 0)
    for _ in range(10):
        point_cloud.append([random.gauss(10, 0.5), random.gauss(0, 0.5)])

    diagrams = compute_vietoris_rips_persistence(point_cloud, max_dimension=1)
    betti_curves = compute_betti_curves(diagrams)

    fingerprint = TDAFingerprint(
        module_id="demo_point_cloud",
        diagrams=diagrams,
        betti_curves=betti_curves,
    )

    print(summarize_for_cli(fingerprint))

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(fingerprint.to_dict(), f, indent=2)
        print(f"\nJSON fingerprint written to: {args.json_out}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="tda_pipeline",
        description="Topological Data Analysis of Pipeline Architecture (Track B Phase 10)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # compute
    compute_parser = subparsers.add_parser(
        "compute",
        help="Compute TDA fingerprint from a call graph JSON file",
    )
    compute_parser.add_argument(
        "call_graph",
        help="Path to call graph JSON file (with 'edges' array)",
    )
    compute_parser.add_argument(
        "--module-id",
        help="Module ID (default: filename stem)",
    )
    compute_parser.add_argument(
        "--json-out",
        help="Write JSON fingerprint to this path",
    )
    compute_parser.set_defaults(func=cmd_compute)

    # demo
    demo_parser = subparsers.add_parser(
        "demo",
        help="Run demo TDA computation on synthetic point cloud",
    )
    demo_parser.add_argument(
        "--json-out",
        help="Write JSON fingerprint to this path",
    )
    demo_parser.set_defaults(func=cmd_demo)

    return parser


def run_cli(argv: List[str] | None = None) -> int:
    """CLI entry point (``python -m dev plugin-run tda_pipeline -- ...``)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


plugin = TDAPipelinePlugin()


# D52 --stdio support
def d52_stdio() -> None:
    """Read JSON request from stdin, write JSON response to stdout."""
    request = json.load(sys.stdin)
    command = request.get("command", "")

    if command == "compute":
        call_edges = [(e["src"], e["dst"]) for e in request.get("edges", [])]
        module_id = request.get("module_id", "unknown")
        fingerprint = extract_fingerprint_from_call_graph(module_id, call_edges)
        response = {"status": "ok", "fingerprint": fingerprint.to_dict()}
    elif command == "demo":
        import random

        random.seed(42)
        point_cloud = []
        for _ in range(10):
            point_cloud.append([random.gauss(0, 0.5), random.gauss(0, 0.5)])
        for _ in range(10):
            point_cloud.append([random.gauss(5, 0.5), random.gauss(5, 0.5)])

        diagrams = compute_vietoris_rips_persistence(point_cloud, max_dimension=1)
        betti_curves = compute_betti_curves(diagrams)
        fingerprint = TDAFingerprint(
            module_id="demo",
            diagrams=diagrams,
            betti_curves=betti_curves,
        )
        response = {"status": "ok", "fingerprint": fingerprint.to_dict()}
    else:
        response = {"status": "error", "message": f"Unknown command: {command}"}

    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


__all__ = ["plugin", "run_cli", "d52_stdio"]

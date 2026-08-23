"""
backend/benchmark/merge_overmix_report.py
=========================================
Consolidates existing Overmix per-test artifacts (overmix_stitch.png, overmix_variant.json)
into a unified four-way summary JSON/report without requiring expensive pipeline re-runs.

Usage:
    python -m backend.benchmark.merge_overmix_report [--results-dir DIR] [--output-json PATH]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def merge_overmix_results(
    results_dir: Path | str,
    output_json: Path | str | None = None,
) -> Dict[str, Any]:
    """Scan results directory for Overmix test artifacts and merge them into a consolidated report.

    Args:
        results_dir: Path to directory containing per-test benchmark output folders.
        output_json: Optional path to save the consolidated four-way JSON summary.

    Returns:
        Dict containing total tests, found Overmix artifacts, metrics summary, and per-test breakdown.
    """
    results_path = Path(results_dir)
    summary: Dict[str, Any] = {
        "title": "Consolidated Four-Way Stitching Benchmark Summary",
        "engines": ["ASP", "OpenCV", "Hugin", "Overmix"],
        "total_datasets": 0,
        "overmix_datasets_found": 0,
        "datasets": {},
    }

    if not results_path.exists():
        logger.warning(f"Results directory does not exist: {results_path}")
        return summary

    # Iterate over subdirectories representing individual test runs
    for test_dir in sorted(results_path.iterdir()):
        if not test_dir.is_dir():
            continue

        test_name = test_dir.name
        summary["total_datasets"] += 1

        overmix_json_path = test_dir / "overmix_variant.json"
        overmix_img_path = test_dir / "overmix_stitch.png"

        entry: Dict[str, Any] = {
            "overmix_present": False,
            "overmix_img_exists": overmix_img_path.exists(),
            "overmix_meta": None,
        }

        if overmix_json_path.exists():
            try:
                with open(overmix_json_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                entry["overmix_present"] = True
                entry["overmix_meta"] = meta
                summary["overmix_datasets_found"] += 1
            except Exception as exc:
                logger.warning(f"Failed to read {overmix_json_path}: {exc}")

        if overmix_img_path.exists():
            entry["overmix_image_path"] = str(overmix_img_path)
            stat = os.stat(overmix_img_path)
            entry["overmix_image_size_bytes"] = stat.st_size

        summary["datasets"][test_name] = entry

    if output_json:
        out_p = Path(output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Saved consolidated summary to {out_p}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge Overmix per-test artifacts into a consolidated summary report."
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="output",
        help="Directory containing per-test benchmark artifacts (default: output)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="output/consolidated_four_way_summary.json",
        help="Target output JSON path (default: output/consolidated_four_way_summary.json)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    res = merge_overmix_results(args.results_dir, args.output_json)
    print(
        f"Consolidated {res['overmix_datasets_found']}/{res['total_datasets']} Overmix benchmark entries."
    )


if __name__ == "__main__":
    main()

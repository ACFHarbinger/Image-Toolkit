"""Generate M0 relabeled summary data artifact for docs/website."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
ASP_DIR = ROOT_DIR / "submodules" / "ASP"
RELABEL_PY = ASP_DIR / "backend" / "benchmark" / "evaluation" / "other" / "relabel.py"
BENCH_JSON = ASP_DIR / "backend" / "benchmark" / "output" / "anime_stitch_20260807_045552.json"
EVAL_JSON = ASP_DIR / "data" / "benchmarks" / "asp_evaluations_20260810.json"
OUT_JSON = ROOT_DIR / "docs" / "website" / "public" / "data" / "m0_relabeled_summary.json"


def main():
    if not RELABEL_PY.exists():
        print(f"Error: {RELABEL_PY} not found", file=sys.stderr)
        sys.exit(1)
    if not BENCH_JSON.exists():
        print(f"Error: {BENCH_JSON} not found", file=sys.stderr)
        sys.exit(1)
    if not EVAL_JSON.exists():
        print(f"Error: {EVAL_JSON} not found", file=sys.stderr)
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("relabel", str(RELABEL_PY))
    relabel_mod = importlib.util.module_from_spec(spec)
    sys.modules["relabel"] = relabel_mod
    spec.loader.exec_module(relabel_mod)

    relabeled = relabel_mod.relabel_corpus(str(BENCH_JSON), str(EVAL_JSON))
    summary = relabel_mod.summarize(relabeled)
    cases = {name: c.to_dict() for name, c in relabeled.items()}

    out = {
        "summary": summary,
        "cases": cases,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)

    print(f"Wrote M0 relabeled summary to {OUT_JSON}")
    print(f"Total cases: {summary['total_cases']}")
    print(f"True Raw ASP: {summary['true_raw_asp_composites']['count']} (mean score: {summary['true_raw_asp_composites']['mean_human_asp_score']:.3f})")
    print(f"Safety Fallbacks to SCANS: {summary['safety_fallbacks_to_scans']['count']} (mean score: {summary['safety_fallbacks_to_scans']['mean_human_asp_score']:.3f})")


if __name__ == "__main__":
    main()

"""Argument parser for `backend/controllers/bench_eval_dispatch.py`."""

from __future__ import annotations

import argparse
import os


def build_parser(doc: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--data-dir", default=os.path.expanduser("~/Downloads/Data/Dump"),
        help="Root data directory containing asp_testXX subdirectories and output/",
    )
    parser.add_argument(
        "--out", default=None,
        help="Ratings JSON path. Defaults to data/human_evaluations/asp_evaluations_<today>.json "
             "(resumes an existing file for today if present); pass an existing file's "
             "path explicitly to resume a specific prior session.",
    )
    parser.add_argument(
        "--redo", action="store_true",
        help="Re-rate datasets that already have a evaluation (default: skip them).",
    )
    parser.add_argument(
        "--default-view", choices=["display", "pixel"], default="display",
        help="Which display mode the image panels start in (default: display).",
    )
    return parser

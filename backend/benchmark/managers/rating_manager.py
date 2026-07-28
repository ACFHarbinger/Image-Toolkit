#!/usr/bin/env python3
"""
ASP Phase 0.1 — human coherence rating tool.

The ASP roadmap's objective ("at least as good as the OpenCV SCANS simple
stitch, as judged by a human") is defined against structural-coherence
ratings, not any automated metric — no automated metric currently measures
whether a composite has torn anatomy, duplicated strips, or misordered
content (research/ASP_Critical_Evaluation_2026-07-08.md). This script is the
"tiny helper script" the roadmap's Phase 0.1 calls for: it shows each test's
ASP output side by side with the Simple-stitch output (and ground truth, if
available), and records a 0-4 structural-coherence score for each.

Rating scale (0-4):
    4 = keepable — no visible structural defects
    3 = minor flaw — small artifact, still clearly usable
    2 = flawed but parses — visible defect, but anatomy/content still reads
    1 = mostly broken — hard to parse, major tearing/duplication
    0 = incoherent — torn anatomy, duplicated strips, or misordered content

Usage:
    python -m backend.benchmark.managers.rating_manager [--data-dir DIR] [--out PATH] [--redo]

Controls (all keyboard, window must have focus):
    0-4   rate the currently-prompted image (ASP first, then Simple)
    s     skip this dataset (rate later — not saved as 0, just left out)
    b     go back and re-rate the previous dataset
    n     add/edit a free-text note for the current dataset (terminal prompt)
    q     quit and save; resuming later picks up where you left off

Output: {out}/asp_ratings_<YYYYMMDD>.json, schema:
    {"asp_test04": {"asp": 4, "simple": 2, "notes": ""}, ...}
Saved incrementally after every rating — quitting never loses progress.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
from typing import Dict, Optional

import cv2
import numpy as np

_MONTAGE_H = 700  # target row height for each panel in the side-by-side montage
_LABEL_BAR_H = 36


def _load_ground_truth(dataset_name: str, gt_dir: str) -> Optional[np.ndarray]:
    """Same lookup convention as bench_anime_stitch.py's _load_ground_truth."""
    for ext in (".png", ".jpg", ".jpeg"):
        path = os.path.join(gt_dir, f"{dataset_name}{ext}")
        if os.path.exists(path):
            img = cv2.imread(path)
            if img is not None:
                return img
    return None


def _panel(img: np.ndarray, label: str) -> np.ndarray:
    """Resize to the montage row height and stamp a label bar on top."""
    h, w = img.shape[:2]
    scale = _MONTAGE_H / max(h, 1)
    resized = cv2.resize(
        img, (max(1, int(w * scale)), _MONTAGE_H), interpolation=cv2.INTER_AREA
    )
    bar = np.full((_LABEL_BAR_H, resized.shape[1], 3), 24, dtype=np.uint8)
    cv2.putText(
        bar, label, (8, _LABEL_BAR_H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
        (255, 255, 255), 2, cv2.LINE_AA,
    )
    return np.vstack([bar, resized])


def _build_montage(
    asp_img: np.ndarray, simple_img: np.ndarray, gt_img: Optional[np.ndarray]
) -> np.ndarray:
    panels = [_panel(asp_img, "ASP"), _panel(simple_img, "SIMPLE (SCANS)")]
    if gt_img is not None:
        panels.append(_panel(gt_img, "GROUND TRUTH"))
    gap = np.full((panels[0].shape[0], 6, 3), 60, dtype=np.uint8)
    parts = []
    for i, p in enumerate(panels):
        if i > 0:
            parts.append(gap)
        parts.append(p)
    return np.hstack(parts)


def _prompt_bar(text: str, width: int) -> np.ndarray:
    bar = np.full((50, width, 3), (40, 20, 20), dtype=np.uint8)
    cv2.putText(
        bar, text, (10, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
        (255, 255, 255), 2, cv2.LINE_AA,
    )
    return bar


def _discover_datasets(base_dir: str) -> list:
    out_dir = os.path.join(base_dir, "output")
    names = []
    for p in sorted(glob.glob(os.path.join(out_dir, "asp_test*_anime_stitch.png"))):
        name = os.path.basename(p)[: -len("_anime_stitch.png")]
        names.append(name)
    return names


def _wait_for_rating(window: str, montage: np.ndarray, which: str) -> Optional[int]:
    """Show montage + a prompt bar, block for a 0-4 key. Returns None on skip/back/quit
    signals, which are propagated via the special return values below (as negative
    sentinels so the caller can distinguish from a real rating)."""
    prompt = _prompt_bar(
        f"Rate {which} coherence: [0]incoherent [1] [2]flawed-but-parses [3] [4]keepable  "
        "| [s]kip [b]ack [n]ote [q]uit",
        montage.shape[1],
    )
    frame = np.vstack([montage, prompt])
    while True:
        cv2.imshow(window, frame)
        key = cv2.waitKey(50)
        if key == -1:
            continue
        ch = chr(key & 0xFF).lower()
        if ch in "01234":
            return int(ch)
        if ch == "s":
            return -1  # skip
        if ch == "b":
            return -2  # back
        if ch == "n":
            return -3  # note
        if ch == "q":
            return -4  # quit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--data-dir", default=os.path.expanduser("~/Downloads/Data/Dump"),
        help="Root data directory containing asp_testXX subdirectories and output/",
    )
    parser.add_argument(
        "--out", default=None,
        help="Ratings JSON path. Defaults to data/human_ratings/asp_ratings_<today>.json "
             "(resumes an existing file for today if present); pass an existing file's "
             "path explicitly to resume a specific prior session.",
    )
    parser.add_argument(
        "--redo", action="store_true",
        help="Re-rate datasets that already have a rating (default: skip them).",
    )
    args = parser.parse_args()

    base_dir = args.data_dir
    out_path = args.out
    if out_path is None:
        ratings_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "human_ratings",
        )
        os.makedirs(ratings_dir, exist_ok=True)
        today = datetime.datetime.now().strftime("%Y%m%d")
        out_path = os.path.join(ratings_dir, f"asp_ratings_{today}.json")
    else:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    ratings: Dict[str, Dict] = {}
    if os.path.exists(out_path):
        with open(out_path) as fh:
            ratings = json.load(fh)
        print(f"Resuming {out_path} ({len(ratings)} dataset(s) already rated).")

    dataset_names = _discover_datasets(base_dir)
    if not dataset_names:
        print(f"No *_anime_stitch.png outputs found under {base_dir}/output/ "
              "— run the benchmark first.")
        return

    todo = [n for n in dataset_names if args.redo or n not in ratings]
    if not todo:
        print(f"All {len(dataset_names)} datasets already rated in {out_path}.")
        return

    print(f"{len(todo)}/{len(dataset_names)} dataset(s) to rate. Output: {out_path}")

    window = "ASP Coherence Rating (0-4, s=skip, b=back, n=note, q=quit)"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    out_dir = os.path.join(base_dir, "output")
    gt_dir = os.path.join(base_dir, "ground_truth")

    idx = 0
    history: list = []  # for 'back'
    quit_requested = False
    while idx < len(todo) and not quit_requested:
        name = todo[idx]
        asp_path = os.path.join(out_dir, f"{name}_anime_stitch.png")
        simple_path = os.path.join(out_dir, f"{name}_simple_stitch.png")
        asp_img = cv2.imread(asp_path)
        simple_img = cv2.imread(simple_path)
        if asp_img is None or simple_img is None:
            print(f"  [skip] {name}: missing output image(s).")
            idx += 1
            continue
        gt_img = _load_ground_truth(name, gt_dir)
        montage = _build_montage(asp_img, simple_img, gt_img)
        cv2.setWindowTitle(window, f"{window} — {name} ({idx + 1}/{len(todo)})")

        entry = dict(ratings.get(name, {"asp": None, "simple": None, "notes": ""}))
        action = None
        for which, key in (("ASP", "asp"), ("SIMPLE", "simple")):
            r = _wait_for_rating(window, montage, which)
            if r == -4:
                quit_requested = True
                action = "quit"
                break
            if r == -1:
                action = "skip"
                break
            if r == -2:
                action = "back"
                break
            if r == -3:
                cv2.destroyWindow(window)
                note = input(f"Note for {name} (enter to skip): ")
                cv2.namedWindow(window, cv2.WINDOW_NORMAL)
                entry["notes"] = note
                r = _wait_for_rating(window, montage, which)
                if r is not None and r >= 0:
                    entry[key] = r
                continue
            entry[key] = r

        if action == "quit":
            break
        if action == "skip":
            idx += 1
            continue
        if action == "back":
            if history:
                idx = history.pop()
            continue

        ratings[name] = entry
        history.append(idx)
        with open(out_path, "w") as fh:
            json.dump(ratings, fh, indent=2, sort_keys=True)
        print(f"  [{idx + 1}/{len(todo)}] {name}: asp={entry['asp']} simple={entry['simple']}")
        idx += 1

    cv2.destroyAllWindows()
    print(f"\nSaved {len(ratings)} rating(s) to {out_path}.")


if __name__ == "__main__":
    main()

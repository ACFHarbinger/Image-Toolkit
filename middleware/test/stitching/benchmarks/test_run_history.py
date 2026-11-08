"""Bench run history (run_history.py) and the evaluator's previous-run panel."""

from __future__ import annotations

import os

import cv2
import numpy as np
from middleware.benchmark.asp import run_history
from middleware.benchmark.asp.evaluation.constants.schema import (
    IMAGE_ASP,
    IMAGE_ASP_PREV,
    IMAGE_SIMPLE,
)
from middleware.benchmark.asp.evaluation.other import discovery


def _png(path, value):
    cv2.imwrite(str(path), np.full((20, 30, 3), value, np.uint8))
    return str(path)


def _row(tmp, name, asp_value, asp_ssim, cv_ssim=0.8):
    d = tmp / "outputs" / f"{name}-{asp_value}"
    d.mkdir(parents=True)
    return {
        "name": name,
        "anime_path": _png(d / "asp.png", asp_value),
        "simple_path": _png(d / "cv.png", 7),
        "ground_truth": {
            "metrics_asp": {"fair_ssim_vs_gt": asp_ssim},
            "metrics_simple": {"fair_ssim_vs_gt": cv_ssim},
            "metrics_overmix": {},
            "metrics_hugin": {},
        },
    }


def test_archive_list_previous_and_compare(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    monkeypatch.setenv("ASP_BENCH_HISTORY_DIR", str(root))
    r1 = run_history.new_run(["asp_test01", "asp_test02"], label="first")
    run_history.archive_case(r1, _row(tmp_path, "asp_test01", 10, 0.70))
    run_history.archive_case(r1, _row(tmp_path, "asp_test02", 20, 0.75))
    run_history.finish_run(r1)
    # same second would collide on the id; the label keeps them distinct
    r2 = run_history.new_run(["asp_test01"], label="second")
    run_history.archive_case(r2, _row(tmp_path, "asp_test01", 30, 0.85))
    run_history.finish_run(r2)

    runs = run_history.list_runs()
    assert [r.meta["label"] for r in runs] == ["first", "second"]
    latest = run_history.resolve_run("latest")
    assert latest.meta["label"] == "second" and latest.meta["status"] == "done"
    prev = run_history.previous_run("asp_test01", latest)
    assert prev is not None and prev.meta["label"] == "first"
    assert run_history.previous_run("asp_test02", latest).meta["label"] == "first"

    rows = run_history.compare(latest)
    combined = rows[0].pop("combined")
    assert rows == [{
        "case": "asp_test01", "asp": 0.85, "asp_prev": 0.70, "prev_run": prev.run_id,
        "opencv": 0.8, "overmix": None, "hugin": None, "identity": None,
        "registration": None,
    }]
    assert combined["asp"] is None  # no coverage recorded in these rows
    # identical OpenCV outputs are stored once
    blobs = list((root / ".blobs").iterdir())
    assert len(blobs) == 4  # 3 distinct ASP images + 1 shared OpenCV image
    assert os.stat(r1 / "asp_test01" / "opencv.png").st_ino == os.stat(r2 / "asp_test01" / "opencv.png").st_ino


def test_discovery_reads_run_and_previous(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    monkeypatch.setenv("ASP_BENCH_HISTORY_DIR", str(root))
    r1 = run_history.new_run(["asp_test05"], label="a")
    run_history.archive_case(r1, _row(tmp_path, "asp_test05", 40, 0.7))
    r2 = run_history.new_run(["asp_test05"], label="b")
    run_history.archive_case(r2, _row(tmp_path, "asp_test05", 50, 0.8))
    base = tmp_path / "data"
    base.mkdir()
    run = run_history.resolve_run("latest")
    assert discovery.discover_datasets(str(base), run) == ["asp_test05"]
    assets = discovery.load_test_assets(str(base), "asp_test05", str(tmp_path), run=run)
    assert assets.paths[IMAGE_ASP] == str(r2 / "asp_test05" / "asp.png")
    assert assets.paths[IMAGE_ASP_PREV] == str(r1 / "asp_test05" / "asp.png")
    assert assets.paths[IMAGE_SIMPLE] == str(r2 / "asp_test05" / "opencv.png")
    assert assets.metrics["ground_truth"]["metrics_asp"]["fair_ssim_vs_gt"] == 0.8
    assert assets.available()[:2] == [IMAGE_ASP, IMAGE_ASP_PREV]

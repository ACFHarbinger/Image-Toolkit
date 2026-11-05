"""Description, tags, and case deltas on archived ASP runs. No bench, no Qt."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from middleware.benchmark.asp import run_history
from middleware.benchmark.asp.evaluation.other.run_library import (
    annotate_run,
    compare_cases,
    filter_by_tags,
    list_runs,
    snapshot_outputs,
)

_RUN_KEYS = {
    "run_id",
    "label",
    "description",
    "tags",
    "created",
    "status",
    "cases",
    "path",
}


def _png(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), np.full((1, 1, 3), value, np.uint8))


def _stamp_asp(run_path: str, case: str, score: float) -> None:
    path = Path(run_path) / case / "result.json"
    row = json.loads(path.read_text(encoding="utf-8"))
    row.setdefault("ground_truth", {})["metrics_asp"] = {"fair_ssim_vs_gt": score}
    path.write_text(json.dumps(row), encoding="utf-8")


def test_unannotated_run_defaults_and_tag_normalization(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    assert list_runs(root) == []

    plain = run_history.new_run(["alpha"], label="plain", root=root)
    run_history.finish_run(plain, status="done")
    listed = list_runs(root)
    assert len(listed) == 1
    run = listed[0]
    assert set(run) == _RUN_KEYS
    assert run["run_id"] == plain.name
    assert run["label"] == "plain"
    assert run["description"] == ""
    assert run["tags"] == []
    assert run["status"] == "done"
    assert run["cases"] == ["alpha"]
    assert run["path"] == str(plain)
    assert run["created"]

    noted = annotate_run(
        plain.name,
        description="first pass",
        tags=["Seam", "seam", " "],
        root=root,
    )
    assert noted["description"] == "first pass"
    assert noted["tags"] == ["seam"]
    assert noted["cases"] == ["alpha"]
    assert noted["status"] == "done"
    stored = json.loads((plain / "run.json").read_text(encoding="utf-8"))
    assert stored["description"] == "first pass"
    assert stored["tags"] == ["seam"]
    assert list_runs(root)[0]["tags"] == ["seam"]

    ordered = annotate_run(plain.name, description="kept", tags=["Color", "Seam", "color"], root=root)
    assert ordered["tags"] == ["color", "seam"]
    assert ordered["description"] == "kept"

    with pytest.raises(FileNotFoundError):
        annotate_run("missing-run", description="x", tags=["a"], root=root)


def test_snapshot_filter_and_compare_do_not_need_the_bench(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    older = tmp_path / "bench-a"
    newer = tmp_path / "bench-b"
    _png(older / "output" / "alpha_anime_stitch.png", 10)
    _png(older / "output" / "beta_anime_stitch.png", 20)
    _png(newer / "output" / "alpha_anime_stitch.png", 30)
    _png(newer / "output" / "beta_anime_stitch.png", 40)

    first = snapshot_outputs(
        str(older),
        ["alpha", "beta"],
        description="",
        tags=["seam"],
        label="first",
        root=root,
    )
    # gamma has no output file; the run is still saved and annotated.
    second = snapshot_outputs(
        str(newer),
        ["beta", "alpha", "gamma"],
        description="later",
        tags=["Seam", "Color"],
        label="second",
        root=root,
    )

    assert set(first) == _RUN_KEYS
    assert first["description"] == ""
    assert first["tags"] == ["seam"]
    assert first["status"] == "saved"
    assert first["label"] == "first"
    assert first["cases"] == ["alpha", "beta"]
    assert (Path(first["path"]) / "alpha" / "asp.png").is_file()
    assert (Path(first["path"]) / "beta" / "asp.png").is_file()

    assert second["description"] == "later"
    assert second["tags"] == ["seam", "color"]
    assert second["cases"] == ["beta", "alpha", "gamma"]
    assert second["status"] == "saved"
    assert not (Path(second["path"]) / "gamma" / "result.json").exists()

    empty = snapshot_outputs(
        str(tmp_path / "no-outputs"),
        ["nowhere"],
        description="empty save",
        tags=[],
        label="empty",
        root=root,
    )
    assert empty["cases"] == ["nowhere"]
    assert empty["tags"] == []
    assert empty["description"] == "empty save"
    assert empty["status"] == "saved"
    assert list(Path(empty["path"]).glob("*/result.json")) == []

    runs = list_runs(root)
    # Same-second ids sort by label slug, so this follows the archive order,
    # not the order snapshot_outputs was called.
    assert [item["run_id"] for item in runs] == [item.run_id for item in run_history.list_runs(root)]
    assert {item["label"] for item in runs} == {"first", "second", "empty"}
    assert filter_by_tags(runs, []) is runs
    assert [item["label"] for item in filter_by_tags(runs, ["SEAM"])] == [
        item["label"] for item in runs if item["label"] != "empty"
    ]
    assert [item["label"] for item in filter_by_tags(runs, ["COLOR", "seam"])] == ["second"]
    assert filter_by_tags(runs, ["seam", "missing"]) == []

    _stamp_asp(first["path"], "alpha", 0.5)
    _stamp_asp(second["path"], "alpha", 0.8)
    natural = compare_cases(second["run_id"], first["run_id"], root=root)
    assert [row["case"] for row in natural] == ["alpha", "beta"]

    rows = compare_cases(
        second["run_id"],
        first["run_id"],
        cases=["beta", "nope", "alpha", "gamma"],
        root=root,
    )
    assert [row["case"] for row in rows] == ["beta", "alpha"]
    assert rows[0]["delta_asp"] is None
    assert rows[0]["asp"] is None
    assert rows[0]["asp_prev"] is None
    assert rows[1]["asp"] == pytest.approx(0.8)
    assert rows[1]["asp_prev"] == pytest.approx(0.5)
    assert rows[1]["delta_asp"] == pytest.approx(0.3)
    assert rows[1]["prev_run"] == first["run_id"]
    assert "combined" in rows[1]
    assert "opencv" in rows[1]
    assert "overmix" in rows[1]
    assert "hugin" in rows[1]
    assert "identity" in rows[1]
    assert "registration" in rows[1]

    with pytest.raises(FileNotFoundError):
        compare_cases("missing-run", root=root)
    with pytest.raises(FileNotFoundError):
        compare_cases(second["run_id"], "missing-prev", root=root)

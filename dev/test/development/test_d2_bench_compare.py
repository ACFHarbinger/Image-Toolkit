"""D2: git provenance + bench compare (evidence, not a winner)."""

from __future__ import annotations

import json
from pathlib import Path

from tool.cli.track_d import compare_benchmarks, format_compare
from tool.devtool import main
from tool.host.git import git_state, write_session_manifest
from tool.model import Investigation


def _run(path: Path, **summary) -> Path:
    path.write_text(
        json.dumps(
            {
                "metadata": {"timestamp": "2026-08-17", "label": path.stem},
                "config": {"renderer": "median"},
                "summary": summary,
                "output_path": str(path.with_suffix(".png")),
                "human": {"preference": "scans", "notes": "banding"},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_git_state_has_commit():
    state = git_state()
    assert state["commit"]
    assert len(state["commit"]) >= 7
    assert "dirty" in state


def test_session_manifest_records_git(tmp_path):
    session = tmp_path / "telemetry-1.jsonl"
    session.write_text("{}\n")
    dest = write_session_manifest(session)
    data = json.loads(dest.read_text())
    assert data["format"] == "tool.session"
    assert "git" in data
    assert data["session"].endswith("telemetry-1.jsonl")


def test_investigation_attach_git(tmp_path):
    inv = Investigation.create("d2-case", tmp_path)
    stamped = inv.attach_git({"commit": "abc", "branch": "main", "dirty": False, "dirty_hash": None})
    reopened = Investigation.open(inv.root)
    assert reopened.git["commit"] == "abc"
    assert reopened.manifest["git"]["branch"] == "main"
    assert stamped["commit"] == "abc"


def test_compare_retains_ids_images_annotations(tmp_path):
    a = _run(tmp_path / "run_a.json", datasets_passed=10, total_time_sec=20.0, avg_ghosting_asp=5.0)
    b = _run(tmp_path / "run_b.json", datasets_passed=8, total_time_sec=18.0, avg_ghosting_asp=6.0)
    report = compare_benchmarks(a, b)
    assert report["declaration"].startswith("Evidence only")
    assert report["a"]["id"] == "run_a.json"
    assert report["b"]["id"] == "run_b.json"
    assert report["a"]["images"]
    assert report["a"]["annotations"]["preference"] == "scans"
    assert "datasets_passed" in report["metrics"]
    text = format_compare(report)
    assert "not a winner" in text.lower() or "Evidence only" in text
    assert "winner" not in text.lower().replace("not a winner", "")


def test_cli_bench_compare_json(tmp_path, capsys):
    a = _run(tmp_path / "a.json", datasets_passed=1)
    b = _run(tmp_path / "b.json", datasets_passed=2)
    assert main(["bench", "compare", str(a), str(b), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["a"]["id"] == "a.json"
    assert report["b"]["id"] == "b.json"
    assert "winner" not in report["declaration"].lower() or "not a winner" in report["declaration"].lower()

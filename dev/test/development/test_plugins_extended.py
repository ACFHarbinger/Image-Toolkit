"""Unit tests for extended plugins (C5 ASP Evaluator, C6 Benchmarks, C7 Editor Integration)."""

from __future__ import annotations

import io

from rich.console import Console
from tool.host.app import Host
from tool.host.store import WorkspaceStore
from tool.model.investigation import Investigation
from tool.plugins.asp_evaluator import AspEvaluatorPlugin
from tool.plugins.asp_evaluator import plugin as asp_plugin
from tool.plugins.benchmarks import BenchmarksPlugin
from tool.plugins.editor_integration import (
    EditorIntegrationPlugin,
)


def test_asp_evaluator_summary_and_render():
    synthetic_eval = {
        "case_01": {
            "asp": 3,
            "simple": 4,
            "preference": "simple",
            "reviewed": True,
            "defects": ["ghosting", "seam_line"],
        },
        "case_02": {
            "asp": 4,
            "simple": 2,
            "preference": "asp",
            "reviewed": True,
            "defects": ["banding"],
        },
    }
    summary = AspEvaluatorPlugin.summarize(synthetic_eval)
    assert summary["total_cases"] == 2
    assert summary["reviewed_cases"] == 2
    assert summary["asp_mean_score"] == 3.5
    assert summary["simple_mean_score"] == 3.0
    assert summary["preferences"] == {"simple": 1, "asp": 1}
    assert summary["top_defects"]["ghosting"] == 1

    # Render table to console
    panel = AspEvaluatorPlugin.render_summary_table(summary)
    c = Console(file=io.StringIO(), width=100, color_system=None)
    c.print(panel)
    out = c.file.getvalue()
    assert "ASP Evaluation Summary" in out
    assert "3.50 / 4.0" in out
    assert "ghosting" in out


def test_asp_evaluator_artifacts(tmp_path):
    store = WorkspaceStore(root=tmp_path)
    store.repo_root = tmp_path
    eval_file = tmp_path / "docs/website/public/data/asp_evaluations.json"
    eval_file.parent.mkdir(parents=True)
    eval_file.write_text('{"test1": {"asp": 2}}')

    artifacts = asp_plugin.artifacts(store)
    assert len(artifacts) == 1
    assert artifacts[0].name == "asp_evaluations.json"
    assert artifacts[0].kind == "eval_dataset"


def test_asp_evaluator_launch_and_cli(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    import subprocess
    from tool.cli.parser import build_parser, COMMANDS

    # Create dummy eval_dispatch.py
    dispatch = tmp_path / "submodules" / "ASP" / "backend" / "src" / "cli" / "eval_dispatch.py"
    dispatch.parent.mkdir(parents=True)
    dispatch.write_text("#!/usr/bin/env python3\npass\n")

    # Mock subprocess.run for AspEvaluatorPlugin.launch
    mock_run = MagicMock(returncode=0)
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=mock_run))

    # Test AspEvaluatorPlugin.launch
    ret = AspEvaluatorPlugin.launch(repo_root=tmp_path, surface="inspector")
    assert ret == 0
    assert subprocess.run.called
    called_cmd = subprocess.run.call_args[0][0]
    assert "--surface" in called_cmd
    assert "inspector" in called_cmd

    # Test devtool eval asp CLI dispatch
    parser = build_parser()
    args = parser.parse_args(["eval", "asp", "--surface", "summary"])
    assert args.command == "eval"
    assert args.surface == "summary"

    ret_cli = COMMANDS["eval"](args)
    assert ret_cli == 0



def test_benchmarks_compare_and_render():
    run_a = {
        "metadata": {"timestamp": "2026-08-01T00:00:00"},
        "summary": {
            "total_datasets": 10,
            "datasets_passed": 5,
            "datasets_fallback": 5,
            "total_time_sec": 120.0,
            "avg_ghosting_asp": 40.0,
            "avg_coverage_asp": 0.95,
        },
    }
    run_b = {
        "metadata": {"timestamp": "2026-08-02T00:00:00"},
        "summary": {
            "total_datasets": 10,
            "datasets_passed": 8,
            "datasets_fallback": 2,
            "total_time_sec": 90.0,
            "avg_ghosting_asp": 25.0,
            "avg_coverage_asp": 0.99,
        },
    }
    diff = BenchmarksPlugin.compare_runs(run_a, run_b)
    deltas = diff["deltas"]
    assert deltas["datasets_passed"]["delta"] == 3
    assert deltas["datasets_fallback"]["delta"] == -3
    assert deltas["total_time_sec"]["delta"] == -30.0
    assert deltas["avg_ghosting_asp"]["delta"] == -15.0

    # Render comparison panel
    panel = BenchmarksPlugin.render_comparison_table(diff, label_a="Baseline", label_b="Candidate")
    c = Console(file=io.StringIO(), width=100, color_system=None)
    c.print(panel)
    out = c.file.getvalue()
    assert "Benchmark Metric Comparison Engine" in out
    assert "Baseline vs Candidate" in out
    assert "+3" in out
    assert "-30.00" in out


def test_editor_integration_markdown(tmp_path):
    inv = Investigation.create("inv-001", tmp_path)
    inv.append_note("Found race condition in scanner worker.", author="Gemini")
    inv.link_session("/tmp/telemetry-101.jsonl")

    md = EditorIntegrationPlugin.format_investigation_markdown(inv)
    assert "## Investigation `inv-001`" in md
    assert "telemetry-101.jsonl" in md
    assert "Found race condition in scanner worker." in md

    tasks = EditorIntegrationPlugin.generate_vscode_tasks()
    assert tasks["version"] == "2.0.0"
    assert len(tasks["tasks"]) >= 3


def test_host_discovers_all_first_party_plugins(tmp_path):
    store = WorkspaceStore(root=tmp_path)
    host = Host(store=store)
    plugins = host.discover()
    names = [p.manifest.name for p in plugins]
    assert "telemetry_workbench" in names
    assert "asp_evaluator" in names
    assert "benchmarks" in names
    assert "editor_integration" in names

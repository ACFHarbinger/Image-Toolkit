"""Tests for debugtool TUI views and application runner (Phase A3)."""

from __future__ import annotations

import io

import pytest
from conftest import event, write_session
from debugtool import open_session, render_session_view, run_tui
from debugtool.cli.main import main as cli_main
from debugtool.ui.views.concurrency import render_concurrency
from debugtool.ui.views.crash import render_crash
from debugtool.ui.views.flame import render_flame
from debugtool.ui.views.live_tail import render_live_view
from debugtool.ui.views.memory import render_memory
from debugtool.ui.views.timeline import render_timeline
from rich.console import Console


@pytest.fixture
def rich_console():
    return Console(file=io.StringIO(), width=100, color_system=None)


@pytest.fixture
def sample_session(telemetry_dir):
    events = [
        event(0.100, "scanner", "scan_dir.start", panel="primary", img_thread=101),
        event(0.120, "extractor", "process_video.start", panel="secondary", vid_worker=202),
        event(0.150, "scanner", "read_file", path="1.png", tid=101),
        event(0.180, "memory", "gc_collect", alloc_mb=45.2),
        event(0.200, "scanner", "scan_dir.end", panel="primary", img_thread=101),
        event(0.220, "extractor", "process_video.end", panel="secondary", vid_worker=202),
        event(0.250, "converter", "convert_image.start", tid=303),
        # convert_image is left orphaned intentionally
    ]
    path = write_session(telemetry_dir, 8888, events)
    return open_session(path)


def test_render_timeline(sample_session, rich_console):
    renderable = render_timeline(sample_session)
    rich_console.print(renderable)
    output = rich_console.file.getvalue()
    assert "Timeline & Waterfall — PID 8888" in output
    assert "scan_dir" in output
    assert "convert_image" in output
    assert "ORPHAN" in output


def test_render_crash(sample_session, rich_console):
    renderable = render_crash(sample_session, gdb_trace="Thread 1 (Thread 0x7f): #0 0x0 in func ()")
    rich_console.print(renderable)
    output = rich_console.file.getvalue()
    assert "Crash Forensics Splicer" in output
    assert "convert_image" in output
    assert "GDB Backtrace" in output


def test_render_concurrency(sample_session, rich_console):
    renderable = render_concurrency(sample_session)
    rich_console.print(renderable)
    output = rich_console.file.getvalue()
    assert "Concurrency & Overlap Inspector" in output
    assert "Observed Thread Inventory" in output
    assert "Dangerous Worker Window Overlaps" in output


def test_render_memory(sample_session, rich_console):
    renderable = render_memory(sample_session)
    rich_console.print(renderable)
    output = rich_console.file.getvalue()
    assert "Memory & RSS Profiler" in output
    assert "Category Activity Footprint" in output


def test_render_flame(sample_session, rich_console):
    renderable = render_flame(sample_session)
    rich_console.print(renderable)
    output = rich_console.file.getvalue()
    assert "Pipeline Flamegraph Breakdown" in output
    assert "Category Flame Tree" in output


def test_render_live_view(sample_session, rich_console):
    renderable = render_live_view(sample_session)
    rich_console.print(renderable)
    output = rich_console.file.getvalue()
    assert "btop Live Watch" in output
    assert "Active In-Flight Spans" in output
    assert "Recent Event Stream" in output


@pytest.mark.parametrize("view", ["timeline", "crash", "concurrency", "memory", "flame", "live"])
def test_render_session_view_dispatch(sample_session, rich_console, view):
    renderable = render_session_view(sample_session, view_name=view)
    rich_console.print(renderable)
    output = rich_console.file.getvalue()
    assert len(output) > 0


def test_run_tui_function(sample_session, rich_console):
    res = run_tui(sample_session, initial_view="timeline", console=rich_console)
    assert res == 0
    assert "Timeline & Waterfall" in rich_console.file.getvalue()


def test_cli_tui_command(sample_session, monkeypatch, capsys):
    ret = cli_main(["tui", str(sample_session.path), "--view", "timeline"])
    assert ret == 0
    out, err = capsys.readouterr()
    assert "Timeline & Waterfall — PID 8888" in out

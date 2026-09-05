"""Unit contracts for the isolated #517 libmpv harness."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).parents[2] / "scripts" / "libmpv_smoke.py"
_SPEC = importlib.util.spec_from_file_location("libmpv_smoke", _SCRIPT)
assert _SPEC and _SPEC.loader
smoke = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(smoke)


def test_missing_library_is_a_clean_skip(monkeypatch, capsys):
    monkeypatch.setattr(smoke, "_library_path", lambda: None)

    assert smoke._worker("offscreen") == 77
    assert "SKIP" in capsys.readouterr().out


def test_supervisor_reports_native_signal(monkeypatch, capsys):
    class Completed:
        returncode = -11

    monkeypatch.setattr(smoke.subprocess, "run", lambda *_args, **_kwargs: Completed())

    assert smoke._supervise("offscreen") == 1
    assert "signal 11" in capsys.readouterr().out

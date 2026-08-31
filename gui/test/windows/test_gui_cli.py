"""#475: frozen entry ``--version`` / ``--help`` must exit before the GUI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from backend.src._version import __version__
from gui._cli import handle_cli_flags

_REPO = Path(__file__).resolve().parents[3]
_MAIN = _REPO / "gui" / "__main__.py"


def test_help_flag_prints_usage_and_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        handle_cli_flags(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: ImageToolkit")
    assert "-v, --version" in out


def test_short_help_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        handle_cli_flags(["-h"])
    assert exc.value.code == 0
    assert "usage: ImageToolkit" in capsys.readouterr().out


def test_version_flag_prints_runtime_version(capsys):
    with pytest.raises(SystemExit) as exc:
        handle_cli_flags(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out == f"Image Toolkit {__version__}\n"


def test_short_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        handle_cli_flags(["-v"])
    assert exc.value.code == 0
    assert capsys.readouterr().out == f"Image Toolkit {__version__}\n"


def test_no_flags_is_a_no_op():
    handle_cli_flags([])
    handle_cli_flags(["--no_dropdown"])


def test_entry_script_version_exits_without_launching_gui():
    """Subprocess of gui/__main__.py --version must return before launch_app."""
    result = subprocess.run(
        [sys.executable, str(_MAIN), "--version"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == f"Image Toolkit {__version__}\n"


def test_entry_script_help_exits_without_launching_gui():
    result = subprocess.run(
        [sys.executable, str(_MAIN), "--help"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.startswith("usage: ImageToolkit")

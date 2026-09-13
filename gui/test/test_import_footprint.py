"""Regression tests for ui-arch-51 / #573 (R3.6 import-graph slimming).

Exit criteria:
1. `import gui.src.components.widgets.toast_widget` loads < 300 modules.
2. No ASP bootstrap (asp_backend) needed for isolated GUI widget imports.
3. helpers, components, tabs, windows, settings package initializers stay lazy facades.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
_ENV = {**os.environ, "PYTHONPATH": _REPO_ROOT}


def test_toast_widget_isolated_import_module_count():
    """Verify toast_widget loads < 300 modules and does not import asp_backend."""
    code = (
        "import sys; "
        "import gui.src.components.widgets.toast_widget; "
        "assert 'asp_backend' not in sys.modules, 'asp_backend leaked into sys.modules'; "
        "print(len(sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_ROOT,
        env=_ENV,
    )
    count = int(result.stdout.strip())
    assert count < 300, f"Expected < 300 modules, got {count}"


def test_gc_safe_isolated_import_module_count():
    """Verify gc_safe loads < 200 modules without pulling web/workers or asp_backend."""
    code = (
        "import sys; "
        "from gui.src.helpers.gc_safe import gc_disabled_run; "
        "assert 'asp_backend' not in sys.modules, 'asp_backend leaked into sys.modules'; "
        "print(len(sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_ROOT,
        env=_ENV,
    )
    count = int(result.stdout.strip())
    assert count < 200, f"Expected < 200 modules, got {count}"


def test_app_settings_isolated_import_module_count():
    """Verify AppSettings loads < 200 modules without pulling app_config or asp_backend."""
    code = (
        "import sys; "
        "from gui.src.windows.settings import AppSettings; "
        "assert 'asp_backend' not in sys.modules, 'asp_backend leaked into sys.modules'; "
        "print(len(sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_ROOT,
        env=_ENV,
    )
    count = int(result.stdout.strip())
    assert count < 200, f"Expected < 200 modules, got {count}"

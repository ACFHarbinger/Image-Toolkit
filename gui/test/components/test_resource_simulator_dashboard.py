"""#483: the parallel-extraction resource simulator must not green-light an
OOM configuration.

Loaded via importlib to sidestep the `gui.src.components` package __init__
circular import (unrelated to this widget).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.gui

_GIB = 1024**3
_MOD_PATH = (
    Path(__file__).resolve().parents[2]
    / "src/components/widgets/resource_simulator_dashboard.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("_rsd_under_test", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def RSD(q_app):
    return _load().ResourceSimulatorDashboard


def test_per_worker_estimate_is_realistic(RSD):
    # Real extraction workers measured ~4 GiB; the old hardcoded 1 GiB is the bug.
    assert RSD.PER_WORKER_RAM_MIB >= 3072


def test_four_workers_over_ram_is_not_optimal(RSD):
    d = RSD()
    # 12 GiB available, 2 GiB swap — 4 × ~4 GiB clearly overcommits.
    d.update_simulation(
        enabled=True, workers=4,
        ram_available=12 * _GIB, ram_total=31 * _GIB,
        swap_total=2 * _GIB, swap_free=1 * _GIB,
    )
    assert "Optimal" not in d.status_badge.text()
    assert "Freeze" in d.status_badge.text() or "Warning" in d.status_badge.text()


def test_low_swap_escalates_to_freeze_risk(RSD):
    d = RSD()
    d.update_simulation(
        enabled=True, workers=8,
        ram_available=20 * _GIB, ram_total=31 * _GIB,
        swap_total=2 * _GIB, swap_free=1 * _GIB,
    )
    assert "Freeze" in d.status_badge.text()


def test_headroom_reserve_applied(RSD):
    d = RSD()
    d.update_simulation(
        enabled=True, workers=1,
        ram_available=8 * _GIB, ram_total=32 * _GIB,
        swap_total=16 * _GIB, swap_free=16 * _GIB,
    )
    # usable = 8 - max(2, 0.12*32=3.84) = ~4.16 GiB, not the full 8.
    assert "4." in d.card_sys_ram.value_label.text()


def test_single_worker_with_ample_ram_is_ok(RSD):
    d = RSD()
    d.update_simulation(
        enabled=True, workers=1,
        ram_available=40 * _GIB, ram_total=64 * _GIB,
        swap_total=16 * _GIB, swap_free=16 * _GIB,
    )
    assert "Optimal" in d.status_badge.text()

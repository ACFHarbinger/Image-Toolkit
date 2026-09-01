"""Regression coverage for the startup-probe race guard (issue #81).

See .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md (Addenda 10-11):
deferring MainWindow construction by a fixed 400ms wasn't a reliable
enough margin against Qt Multimedia's async startup device probe, and
neither was a flat 1.5s elapsed-time floor -- the crash recurred with the
same offset three times running. gui/src/utils/guard/startup_probe_guard.py now
tracks both the probe's real start time (a fallback ceiling) AND positive
confirmation that it actually finished (QMediaDevices' device-changed
signals, wired up in app.py), so any scanner-thread call site can defer
itself precisely instead of guessing a bigger number.
"""

import time

import pytest

from gui.src.utils.guard import startup_probe_guard

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _reset_probe_guard_state(monkeypatch):
    # The guard's state is deliberately process-global (a single "when did
    # the app start / has the probe settled" fact) -- reset it around each
    # test so tests don't leak state into each other.
    monkeypatch.setattr(startup_probe_guard, "_probe_start_monotonic", None)
    monkeypatch.setattr(startup_probe_guard, "_probe_settled", False)
    monkeypatch.setattr(startup_probe_guard, "_probe_settled_at_elapsed_s", None)


class TestStartupProbeGuard:
    def test_remaining_is_zero_before_probe_marked_started(self):
        assert startup_probe_guard.startup_settle_remaining_ms() == 0

    def test_remaining_is_positive_immediately_after_marking(self):
        startup_probe_guard.mark_startup_probe_started()
        remaining = startup_probe_guard.startup_settle_remaining_ms()
        assert (
            0
            < remaining
            <= startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS * 1000
        )

    def test_remaining_decreases_and_settles_to_zero_at_ceiling(self, monkeypatch):
        fake_now = [1000.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])

        startup_probe_guard.mark_startup_probe_started()
        assert startup_probe_guard.startup_settle_remaining_ms() == int(
            startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS * 1000
        )

        # Halfway through the ceiling: still waiting, roughly half the
        # original margin left.
        fake_now[0] += startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS / 2
        remaining_mid = startup_probe_guard.startup_settle_remaining_ms()
        assert (
            0
            < remaining_mid
            < int(startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS * 1000)
        )

        # Past the ceiling entirely: safe to proceed even without a
        # positive confirmation.
        fake_now[0] += startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS
        assert startup_probe_guard.startup_settle_remaining_ms() == 0

    def test_never_returns_negative_past_the_ceiling(self, monkeypatch):
        fake_now = [1000.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])
        startup_probe_guard.mark_startup_probe_started()
        fake_now[0] += startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS * 10
        assert startup_probe_guard.startup_settle_remaining_ms() == 0

    def test_positive_confirmation_short_circuits_the_ceiling(self, monkeypatch):
        fake_now = [1000.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])

        startup_probe_guard.mark_startup_probe_started()
        fake_now[0] += 0.1  # well within the ceiling
        assert startup_probe_guard.startup_settle_remaining_ms() > 0

        startup_probe_guard.mark_startup_probe_settled(source="test")
        assert startup_probe_guard.startup_settle_remaining_ms() == 0

    def test_settled_before_started_records_negative_sentinel_elapsed(self):
        # Guards against a signal firing before mark_startup_probe_started()
        # has ever run (e.g. a test or alternate entry point) -- must not
        # raise, and should still flip the settled flag.
        startup_probe_guard.mark_startup_probe_settled(source="test")
        assert startup_probe_guard.startup_settle_remaining_ms() == 0


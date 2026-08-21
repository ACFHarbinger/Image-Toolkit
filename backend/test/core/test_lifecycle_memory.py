"""Tests for backend/src/core/lifecycle_memory.py (roadmap
development_tool.md §12.5, issue #70).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.src.core import lifecycle_memory


@pytest.fixture(autouse=True)
def _reset_history():
    lifecycle_memory.reset()
    yield
    lifecycle_memory.reset()


def _mock_rss(mb: float):
    proc = MagicMock()
    proc.memory_info.return_value.rss = mb * 1024 * 1024
    return proc


class TestSnapshot:
    def test_first_snapshot_has_no_delta(self):
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(500)):
            entry = lifecycle_memory.snapshot("phase1")
        assert entry["phase"] == "phase1"
        assert entry["rss_mb"] == 500.0
        assert entry["delta_mb"] is None

    def test_second_snapshot_computes_delta(self):
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(500)):
            lifecycle_memory.snapshot("phase1")
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(560)):
            entry = lifecycle_memory.snapshot("phase2")
        assert entry["delta_mb"] == 60.0

    def test_history_accumulates_in_order(self):
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(100)):
            lifecycle_memory.snapshot("a")
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(110)):
            lifecycle_memory.snapshot("b")
        phases = [e["phase"] for e in lifecycle_memory.history()]
        assert phases == ["a", "b"]

    def test_find_returns_matching_phase(self):
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(100)):
            lifecycle_memory.snapshot("qt_init")
        assert lifecycle_memory.find("qt_init")["rss_mb"] == 100.0
        assert lifecycle_memory.find("nonexistent") is None


class TestAlertThreshold:
    def test_delta_under_threshold_not_flagged(self):
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(500)):
            lifecycle_memory.snapshot("phase1")
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(650)):
            lifecycle_memory.snapshot("phase2")  # +150MB, under default 200MB
        assert lifecycle_memory.alerts() == []

    def test_delta_over_threshold_flagged(self):
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(500)):
            lifecycle_memory.snapshot("phase1")
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(750)):
            lifecycle_memory.snapshot("phase2")  # +250MB, over default 200MB
        flagged = lifecycle_memory.alerts()
        assert len(flagged) == 1
        assert flagged[0]["phase"] == "phase2"

    def test_negative_delta_never_flagged(self):
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(800)):
            lifecycle_memory.snapshot("phase1")
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(500)):
            lifecycle_memory.snapshot("phase2")  # RSS dropped
        assert lifecycle_memory.alerts() == []

    def test_custom_threshold_via_env_var(self):
        with patch.object(lifecycle_memory, "LIFECYCLE_RSS_ALERT_MB", 50.0):
            with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(500)):
                lifecycle_memory.snapshot("phase1")
            with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(560)):
                lifecycle_memory.snapshot("phase2")  # +60MB, over the patched 50MB threshold
            assert len(lifecycle_memory.alerts()) == 1


class TestReset:
    def test_reset_clears_history(self):
        with patch("backend.src.core.lifecycle_memory.psutil.Process", return_value=_mock_rss(500)):
            lifecycle_memory.snapshot("phase1")
        assert lifecycle_memory.history() != []
        lifecycle_memory.reset()
        assert lifecycle_memory.history() == []

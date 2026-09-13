"""Regressions for session-recovery's explicit lifecycle state
(ui-arch-43 / R2.d, issue #565, session-recovery half).

Covers ``_restore_when_ready``'s replacement of the old
``QTimer.singleShot(150, do_restore)`` guess: it must poll a real
observable precondition (not sleep blindly), retry only while under
pytest is short-circuited to run synchronously, and never silently drop
the restore action once its retry budget is exhausted.
"""

from __future__ import annotations

import logging
import os
import time
from unittest.mock import patch

import pytest
from gui.src.windows.main._session_recovery_state import (
    SessionRecoveryState,
    _SessionRecoveryStateMixin,
)
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.gui


class _Host(_SessionRecoveryStateMixin):
    pass


def test_starts_not_loaded():
    host = _Host()
    assert host._session_recovery_state is SessionRecoveryState.NOT_LOADED


def test_set_state_logs_transition(caplog):
    host = _Host()
    with caplog.at_level(logging.INFO, logger="gui.src.windows.main._session_recovery_state"):
        host._set_session_recovery_state(SessionRecoveryState.CATEGORY_READY)
    assert any("not_loaded -> category_ready" in r.message for r in caplog.records)


def test_same_state_transition_is_a_noop(caplog):
    host = _Host()
    host._set_session_recovery_state(SessionRecoveryState.CATEGORY_READY)
    with caplog.at_level(logging.INFO, logger="gui.src.windows.main._session_recovery_state"):
        host._set_session_recovery_state(SessionRecoveryState.CATEGORY_READY)
    assert not any("category_ready -> category_ready" in r.message for r in caplog.records)


def test_restore_when_ready_runs_synchronously_under_pytest():
    """The existing "PYTEST_CURRENT_TEST" fast-path must still apply --
    tests must not depend on draining the real Qt event loop."""
    host = _Host()
    calls = []
    host._restore_when_ready(lambda: False, lambda: calls.append(1))
    assert calls == [1]
    assert host._session_recovery_state is SessionRecoveryState.CATEGORY_READY


def test_restore_when_ready_polls_until_the_precondition_is_true(q_app):
    """Outside pytest's fast-path, a not-yet-ready precondition must be
    retried on the real event loop rather than either blocking or
    guessing a fixed delay."""
    host = _Host()
    state = {"ready_after": 3, "attempts": 0}

    def is_ready():
        state["attempts"] += 1
        return state["attempts"] > state["ready_after"]

    calls = []
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        host._restore_when_ready(is_ready, lambda: calls.append(1), retry_ms=1, max_retries=10)
        for _ in range(200):
            if calls:
                break
            time.sleep(0.005)
            QApplication.processEvents()
    assert calls == [1]
    assert state["attempts"] > state["ready_after"]
    assert host._session_recovery_state is SessionRecoveryState.CATEGORY_READY


def test_restore_when_ready_gives_up_after_max_retries_but_still_restores(q_app):
    """A layout that never reports ready (e.g. a hidden/minimized window)
    must not permanently skip the restore -- a late-settling layout is a
    cosmetic risk, a dropped restore is a data-loss risk."""
    host = _Host()
    calls = []
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        host._restore_when_ready(lambda: False, lambda: calls.append(1), retry_ms=1, max_retries=3)
        for _ in range(200):
            if calls:
                break
            time.sleep(0.005)
            QApplication.processEvents()
    assert calls == [1]
    assert host._session_recovery_state is SessionRecoveryState.CATEGORY_READY

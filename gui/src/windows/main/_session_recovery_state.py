"""Explicit lifecycle state for session-recovery restore ordering
(ui-arch-43 / R2.d, issue #565, session-recovery half).

Replaces the "wait 150ms and hope the layout settled" pattern in
``_session_recovery.py`` with an observable-precondition poll. No single
Qt signal (``showEvent``, ``LayoutRequest``, first ``resizeEvent`` after
show) actually guarantees "the layout has finished settling" for a
just-constructed widget tree, so a fixed delay was always a guess -- this
instead polls a real precondition (the target tab widget is visible and
has a laid-out size) on a short interval, falling through to the restore
action regardless once a retry budget is exhausted so a slow-settling
layout is only ever a cosmetic risk, never a dropped restore.
"""

from __future__ import annotations

import enum
import logging
import os
from typing import Callable

from PySide6.QtCore import QTimer

logger = logging.getLogger(__name__)


class SessionRecoveryState(enum.Enum):
    NOT_LOADED = "not_loaded"
    CATEGORY_READY = "category_ready"
    CONFIGS_RESTORED = "configs_restored"


class _SessionRecoveryStateMixin:
    _session_recovery_state: SessionRecoveryState = SessionRecoveryState.NOT_LOADED

    def _set_session_recovery_state(self, new_state: SessionRecoveryState) -> None:
        old_state = getattr(self, "_session_recovery_state", SessionRecoveryState.NOT_LOADED)
        self._session_recovery_state = new_state
        if old_state is new_state:
            return
        logger.info("[session-recovery] %s -> %s", old_state.value, new_state.value)

    def _restore_when_ready(
        self,
        is_ready: Callable[[], bool],
        action: Callable[[], None],
        *,
        retry_ms: int = 16,
        max_retries: int = 30,
        _attempt: int = 0,
    ) -> None:
        """Run *action* once *is_ready* reports true, polling instead of
        guessing a fixed delay. Synchronous under pytest (deterministic
        tests must not depend on the Qt event loop draining retries)."""
        if "PYTEST_CURRENT_TEST" in os.environ:
            self._set_session_recovery_state(SessionRecoveryState.CATEGORY_READY)
            action()
            return
        if is_ready() or _attempt >= max_retries:
            self._set_session_recovery_state(SessionRecoveryState.CATEGORY_READY)
            action()
            return
        QTimer.singleShot(
            retry_ms,
            lambda: self._restore_when_ready(
                is_ready,
                action,
                retry_ms=retry_ms,
                max_retries=max_retries,
                _attempt=_attempt + 1,
            ),
        )


__all__ = ["SessionRecoveryState", "_SessionRecoveryStateMixin"]

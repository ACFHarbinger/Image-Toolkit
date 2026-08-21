"""Host-side sidecar restart policy (locks 3, 4, 12).

This is the *policy* for the process supervisor the Tauri host owns (the
spawn/kill wiring lands with #407). It is written as a pure, testable state
machine so the Rust side can port it one-to-one (and so the locked rules have
an executable reference in-tree).

Rules:
- Lifetime is the window (lock 3): spawn on window open, kill on close.
- A crash BEFORE a successful ``initialize`` is a visible hard failure with NO
  restart (lock 12: the restart counter starts only after a successful
  initialize; crash-before-handshake is not a free restart).
- After a successful ``initialize``, exactly ONE automatic restart is allowed
  (lock 4). No loop-restart, ever.
- A clean exit (expected shutdown, e.g. window closed) never restarts,
  regardless of initialize state.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_AUTO_RESTARTS = 1


@dataclass(frozen=True)
class RestartDecision:
    restart: bool
    reason: str


class SidecarRestartPolicy:
    """Tracks initialize state and consumed restarts for one window lifetime."""

    def __init__(self) -> None:
        self._initialized = False
        self._restarts = 0

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def restarts_used(self) -> int:
        return self._restarts

    def on_initialize_success(self) -> None:
        self._initialized = True

    def on_initialize_failure(self) -> None:
        self._initialized = False

    def on_exit(self, *, clean: bool) -> RestartDecision:
        """Decide what the host should do when the sidecar process exits."""
        if clean:
            return RestartDecision(False, "clean exit (window closed); no restart")
        if not self._initialized:
            return RestartDecision(
                False,
                "crash before successful initialize: visible hard failure, no restart (lock 12)",
            )
        if self._restarts >= MAX_AUTO_RESTARTS:
            return RestartDecision(
                False,
                "crashed after the one allowed restart: visible hard failure, no loop (lock 4)",
            )
        self._restarts += 1
        return RestartDecision(True, "crash after successful initialize: one automatic restart (lock 4)")


__all__ = ["MAX_AUTO_RESTARTS", "RestartDecision", "SidecarRestartPolicy"]
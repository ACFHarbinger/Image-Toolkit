"""Monitor-layout refresh and worker/timer/window teardown overrides.

Qt ``super()`` overrides live on ``SystemDisplaySubTab`` (a QWidget). This
controller exists so the composed tab still has a lifecycle owner.
"""

from __future__ import annotations

from ._tab_bound import TabBoundController


class SystemDisplayLifecycleController(TabBoundController):
    """Composed holder; Qt ``super()`` overrides live on ``SystemDisplaySubTab``."""


__all__ = ["SystemDisplayLifecycleController"]

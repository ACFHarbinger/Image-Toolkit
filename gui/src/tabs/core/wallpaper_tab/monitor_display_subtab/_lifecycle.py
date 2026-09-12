"""Widget-close cleanup for ``MonitorDisplaySubTab``.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

from ._tab_bound import TabBoundController


class MonitorDisplayLifecycleController(TabBoundController):
    """Composed holder; ``closeEvent`` lives on ``MonitorDisplaySubTab``."""


__all__ = ["MonitorDisplayLifecycleController"]


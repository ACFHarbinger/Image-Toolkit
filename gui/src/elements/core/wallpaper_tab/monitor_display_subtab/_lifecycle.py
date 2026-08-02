"""Widget-close cleanup for ``MonitorDisplaySubTab``.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

import os
import shutil


class _LifecycleMixin:
    """Stop the in-app slideshow / status timer and clean up preview temp files."""

    def closeEvent(self, event):
        # In-app slideshows only make sense "while the user remains in-app",
        # so stop the native scheduler here. The background daemon is
        # intentionally left running -- that is its whole point.
        if self._inapp_active_monitor_id is not None:
            self._stop_inapp_slideshow()

        if hasattr(self, "_status_timer") and self._status_timer.isActive():
            self._status_timer.stop()

        if self._preview_tmp_dir and os.path.isdir(self._preview_tmp_dir):
            shutil.rmtree(self._preview_tmp_dir, ignore_errors=True)
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]

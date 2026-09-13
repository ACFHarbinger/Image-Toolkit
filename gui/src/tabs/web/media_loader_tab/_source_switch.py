"""Source combo -> settings-stack page switching."""

from __future__ import annotations

from PySide6.QtCore import Slot

from ._tab_bound import TabBoundController
from ._ui_builder import SOURCE_NHENTAI


class MediaLoaderSourceController(TabBoundController):
    """Keeps ``settings_stack`` in sync with ``source_combo``."""

    @Slot(int)
    def on_source_changed(self, index: int) -> None:
        if index == SOURCE_NHENTAI:
            self.settings_stack.setCurrentWidget(self.page_nhentai)
        else:
            self.settings_stack.setCurrentWidget(self.page_reddit)


_SourceSwitchMixin = MediaLoaderSourceController  # COMPAT(ui-arch-23): remove after callers drop the mixin name

__all__ = ["MediaLoaderSourceController", "_SourceSwitchMixin"]

"""Source combo -> settings-stack page switching."""

from __future__ import annotations

from PySide6.QtCore import Slot

from ._ui_builder import SOURCE_NHENTAI


class _SourceSwitchMixin:
    """Keeps ``settings_stack`` in sync with ``source_combo``."""

    @Slot(int)
    def on_source_changed(self, index: int) -> None:
        if index == SOURCE_NHENTAI:
            self.settings_stack.setCurrentWidget(self.page_nhentai)
        else:
            self.settings_stack.setCurrentWidget(self.page_reddit)


__all__ = ["_SourceSwitchMixin"]

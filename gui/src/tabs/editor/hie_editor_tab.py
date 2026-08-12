"""PySide6 Image Editor tab wrapping the HIE submodule UI."""

from __future__ import annotations

from hie_gui.hie_tab import HieTab


class HieEditorTab(HieTab):
    """Hybrid Image Editor tab component integrated into Image-Toolkit's desktop app UI."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent=parent)


__all__ = ["HieEditorTab"]

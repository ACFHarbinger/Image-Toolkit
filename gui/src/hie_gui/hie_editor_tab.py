"""Embeddable Hybrid Editor tab exported for Image-Toolkit hosts."""

from __future__ import annotations

from .hie_tab import HieTab


class HieEditorTab(HieTab):
    """Hybrid Image Editor tab component for host applications.

    Identical behaviour to :class:`HieTab`; named for host tab registries
    (Image-Toolkit desktop, settings relaunch lists, etc.).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent=parent)


__all__ = ["HieEditorTab"]

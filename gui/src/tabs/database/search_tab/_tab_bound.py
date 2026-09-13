"""Attribute proxy so SearchTab controllers keep mixin-style ``self.foo`` access."""

from __future__ import annotations


class TabBoundController:
    """Forwards unknown attributes to the owning ``SearchTab``.

    Widget-parent arguments must still use ``self.tab`` — a controller is
    not a QWidget.
    """

    __slots__ = ("tab",)

    def __init__(self, tab) -> None:
        object.__setattr__(self, "tab", tab)

    def __getattr__(self, name: str):
        return getattr(object.__getattribute__(self, "tab"), name)

    def __setattr__(self, name: str, value) -> None:
        if name == "tab":
            object.__setattr__(self, name, value)
            return
        setattr(object.__getattribute__(self, "tab"), name, value)


__all__ = ["TabBoundController"]

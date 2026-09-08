"""Attribute proxy so VideoExtractorSubTab controllers keep mixin-style ``self.foo`` access."""

from __future__ import annotations


class TabBoundController:
    """Forwards unknown attributes to the owning ``VideoExtractorSubTab``.

    Widget-parent arguments must still use ``self.tab`` — a controller is
    not a QWidget.

    Instance attributes (including ``unittest.mock.patch.object`` replacements)
    on the tab take precedence over the controller's own methods so existing
    tests that patch the subtab keep working.
    """

    __slots__ = ("tab",)

    def __init__(self, tab) -> None:
        object.__setattr__(self, "tab", tab)

    def __getattribute__(self, name: str):
        if name == "tab" or name.startswith("__"):
            return object.__getattribute__(self, name)
        tab = object.__getattribute__(self, "tab")
        tab_dict = object.__getattribute__(tab, "__dict__")
        if name in tab_dict:
            return tab_dict[name]
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return getattr(tab, name)

    def __setattr__(self, name: str, value) -> None:
        if name == "tab":
            object.__setattr__(self, name, value)
            return
        setattr(object.__getattribute__(self, "tab"), name, value)


__all__ = ["TabBoundController"]

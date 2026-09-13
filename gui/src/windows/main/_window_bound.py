"""Attribute proxy so MainWindow controllers keep mixin-style ``self.foo`` access.

``tab`` is the host ``MainWindow`` (a QWidget), matching TabBoundController's
API so existing mixin code keeps working via ``__getattr__``. Widget-parent
arguments must still use ``self.tab`` — a controller is not a QWidget.
"""

from __future__ import annotations


class WindowBoundController:
    """Forwards unknown attributes to the owning ``MainWindow``.

    The host attribute is named ``tab`` (the MainWindow QWidget) for
    consistency with Search/Scan ``TabBoundController``.
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


__all__ = ["WindowBoundController"]

"""Process-wide window registry — replaces ``topLevelWidgets``/``allWidgets`` discovery.

Phase 1.4 (#528). Windows register on construction and drop out on destroy;
callers ask the registry instead of walking the Qt widget tree. That removes
the "first of N MainWindows wins" ambiguity and the O(N) ``allWidgets()``
walk used for background-hide.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable, Iterator
from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QWidget

Predicate = Callable[[QWidget], bool]


class WindowManager:
    """Singleton registry of application windows."""

    _instance: ClassVar[WindowManager | None] = None

    def __init__(self) -> None:
        self._windows: dict[int, weakref.ref[QWidget]] = {}
        self._roles: dict[str, int] = {}

    @classmethod
    def instance(cls) -> WindowManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear the singleton (tests only)."""
        cls._instance = None

    def register(self, window: QWidget, *, role: str | None = None) -> None:
        """Track *window*; optional *role* (e.g. ``\"main\"``) for named lookup."""
        wid = id(window)
        if wid not in self._windows:
            self._windows[wid] = weakref.ref(window, lambda _ref, i=wid: self._drop(i))
            # Qt may delete before the weakref callback runs; keep both paths.
            window.destroyed.connect(lambda *_args, i=wid: self._drop(i))
        if role is not None:
            self._roles[role] = wid

    def deregister(self, window: QWidget) -> None:
        self._drop(id(window))

    def _drop(self, wid: int) -> None:
        self._windows.pop(wid, None)
        self._roles = {role: i for role, i in self._roles.items() if i != wid}

    def get_by_role(self, role: str) -> QWidget | None:
        wid = self._roles.get(role)
        if wid is None:
            return None
        ref = self._windows.get(wid)
        return self._alive(ref) if ref is not None else None

    def main_window(self) -> QWidget | None:
        return self.get_by_role("main")

    def find(self, predicate: Predicate) -> QWidget | None:
        for window in self.iter_windows():
            if predicate(window):
                return window
        return None

    def iter_windows(self) -> Iterator[QWidget]:
        dead: list[int] = []
        for wid, ref in tuple(self._windows.items()):
            window = self._alive(ref)
            if window is None:
                dead.append(wid)
            else:
                yield window
        for wid in dead:
            self._drop(wid)

    def visible_taskbar_windows(self, *, exclude: QWidget | None = None) -> list[QWidget]:
        """Visible real windows that keep a taskbar entry (for background-hide)."""
        windows: list[QWidget] = []
        seen: set[int] = set()
        for window in self.iter_windows():
            if window is exclude or id(window) in seen:
                continue
            seen.add(id(window))
            if not window.isWindow() or not window.isVisible() or isinstance(window, QMenu):
                continue
            if window.windowType() in (Qt.WindowType.Popup, Qt.WindowType.ToolTip):
                continue
            windows.append(window)
        return windows

    @staticmethod
    def _alive(ref: weakref.ref[QWidget]) -> QWidget | None:
        window = ref()
        if window is None:
            return None
        try:
            # Touch a Qt property so a deleted C++ object raises RuntimeError.
            window.isWindow()
        except RuntimeError:
            return None
        return window


def register_window(window: QWidget, *, role: str | None = None) -> None:
    """Convenience wrapper used from window ``__init__`` methods."""
    WindowManager.instance().register(window, role=role)


__all__ = ["WindowManager", "register_window"]

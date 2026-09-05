"""Directory navigation back/forward history (GUI/UX §2.21A).

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..protos.abstract_class_single_gallery import AbstractClassSingleGalleryHostProtocol


class _DirHistoryMixin:
    """Back/forward stacks for directory navigation."""

    def _push_dir_history(self: "AbstractClassSingleGalleryHostProtocol", path: str) -> None:
        if not path:
            return
        current = self.last_browsed_scan_dir
        if current and (not self._dir_back_stack or self._dir_back_stack[-1] != current):
            self._dir_back_stack.append(current)
        self._dir_forward_stack.clear()
        self._update_nav_history_buttons()

    def _dir_go_back(self: "AbstractClassSingleGalleryHostProtocol") -> Optional[str]:
        if not self._dir_back_stack:
            return None
        prev = self._dir_back_stack.pop()
        self._dir_forward_stack.append(self.last_browsed_scan_dir)
        self._update_nav_history_buttons()
        return prev

    def _dir_go_forward(self: "AbstractClassSingleGalleryHostProtocol") -> Optional[str]:
        if not self._dir_forward_stack:
            return None
        nxt = self._dir_forward_stack.pop()
        self._dir_back_stack.append(self.last_browsed_scan_dir)
        self._update_nav_history_buttons()
        return nxt


__all__ = ["_DirHistoryMixin"]

"""gui/src/services/preview_service.py
===================================
PreviewContext value object and unified PreviewService for launching and
managing image and video previews across GUI tabs (ui-arch-40 / #562).
"""

from __future__ import annotations

import contextlib
import os
import platform
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget

from gui.src.qt_object_guard import deleted_qobject_guard


def launch_external_player(file_path: str, parent: Optional[QWidget] = None) -> bool:
    """Launch the platform external video player for a given file path.

    Returns True if launched successfully, False otherwise.
    """
    if not os.path.exists(file_path):
        return False
    try:
        sys_name = platform.system()
        if sys_name == "Windows":
            os.startfile(file_path)  # pyrefly: ignore [missing-attribute]
        elif sys_name == "Linux":
            subprocess.Popen(
                ["xdg-open", file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["open", file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return True
    except Exception as e:
        if parent is not None:
            QMessageBox.warning(
                parent, "Video Error", f"Could not launch video player: {e}"
            )
        return False


@dataclass
class PreviewContext:
    """Value object capturing all parameters required to open a media preview."""

    path: str
    items: list[str] = field(default_factory=list)
    start_index: Optional[int] = None
    database_service: Any = None
    resolution: Optional[tuple[int, int]] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    parent: Optional[QWidget] = None
    on_path_changed: Optional[Callable[[str, str], None]] = None

    def __post_init__(self) -> None:
        if not self.items:
            self.items = [self.path]
        elif self.path not in self.items:
            self.items.append(self.path)

        if self.start_index is None:
            try:
                self.start_index = self.items.index(self.path)
            except ValueError:
                self.start_index = 0

    @property
    def is_video(self) -> bool:
        """Check if the media path represents a supported video file."""
        return self.path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))


class PreviewService:
    """Coordinates opening, reusing, and tracking image and video previews."""

    def __init__(self) -> None:
        self._open_windows: list[Any] = []

    def open_preview(self, context: PreviewContext) -> Any:
        """Open a media preview given a PreviewContext.

        - If path does not exist, returns None.
        - If path is a video, delegates to external player and returns None.
        - If preview window already open for path, activates and brings to front.
        - Otherwise instantiates ImagePreviewWindow, connects change callback,
          shows it, and tracks it.
        """
        if not os.path.exists(context.path):
            return None

        if context.is_video:
            launch_external_player(context.path, parent=context.parent)
            return None

        self._prune_dead_windows()

        # Check if already open
        for win in self._open_windows:
            try:
                if getattr(win, "image_path", None) == context.path:
                    win.activateWindow()
                    win.raise_()
                    return win
            except (RuntimeError, ReferenceError):
                continue

        from ..windows.image_preview_window import ImagePreviewWindow

        preview = ImagePreviewWindow(
            image_path=context.path,
            database_service=context.database_service,
            parent=context.parent,
            all_paths=context.items,
            start_index=context.start_index if context.start_index is not None else 0,
        )
        if context.on_path_changed is not None and hasattr(preview, "path_changed"):
            preview.path_changed.connect(context.on_path_changed)

        preview.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        preview.show()
        self._open_windows.append(preview)
        return preview

    def close_preview(self, path: str) -> None:
        """Close any open preview window for the specified file path."""
        self._prune_dead_windows()
        for win in list(self._open_windows):
            try:
                if getattr(win, "image_path", None) == path:
                    win.close()
                    if win in self._open_windows:
                        self._open_windows.remove(win)
            except (RuntimeError, ReferenceError) as exc:
                deleted_qobject_guard(exc, "PreviewService.close_preview")

    def close_all(self) -> None:
        """Close all tracked preview windows."""
        self._prune_dead_windows()
        for win in list(self._open_windows):
            with contextlib.suppress(Exception):
                win.close()
        self._open_windows.clear()

    def _prune_dead_windows(self) -> None:
        valid = []
        for win in self._open_windows:
            try:
                _ = win.windowTitle()
                valid.append(win)
            except (RuntimeError, ReferenceError) as exc:
                deleted_qobject_guard(exc, "PreviewService._prune_dead_windows")
        self._open_windows = valid

    @property
    def open_windows(self) -> list[Any]:
        self._prune_dead_windows()
        return list(self._open_windows)


_preview_service: Optional[PreviewService] = None


def get_preview_service() -> PreviewService:
    """Return the global default PreviewService instance."""
    global _preview_service
    if _preview_service is None:
        _preview_service = PreviewService()
    return _preview_service


def open_preview(
    path: str,
    items: Optional[list[str]] = None,
    start_index: Optional[int] = None,
    database_service: Any = None,
    resolution: Optional[tuple[int, int]] = None,
    metadata: Optional[dict[str, Any]] = None,
    parent: Optional[QWidget] = None,
    on_path_changed: Optional[Callable[[str, str], None]] = None,
) -> Any:
    """Convenience helper to construct a PreviewContext and open preview."""
    context = PreviewContext(
        path=path,
        items=items if items is not None else [],
        start_index=start_index,
        database_service=database_service,
        resolution=resolution,
        metadata=metadata if metadata is not None else {},
        parent=parent,
        on_path_changed=on_path_changed,
    )
    return get_preview_service().open_preview(context)


__all__ = [
    "PreviewContext",
    "PreviewService",
    "get_preview_service",
    "launch_external_player",
    "open_preview",
]

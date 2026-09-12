"""``MediaLoaderTab`` -- composed controllers over ``QWidget`` (#544)."""

from __future__ import annotations

from typing import Any, Optional

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget

from ._directory_browse import MediaLoaderDirectoryController
from ._download_worker import MediaLoaderWorkerController
from ._source_switch import MediaLoaderSourceController
from ._ui_builder import MediaLoaderUIBuilder


class MediaLoaderTab(QWidget):
    """GUI tab for downloading media (images/video) from the web.

    First two source integrations: Reddit (via ``asyncpraw``) and nhentai
    (gallery-page scrape) -- see ``backend/src/web/downloaders``.

    Phase 2 (ui-arch-23/#544): mixins collapsed into composed controllers.
    """

    def __init__(self):
        super().__init__()
        self.worker: Optional[Any] = None
        self.saved_count = 0
        self.last_browsed_download_dir = LOCAL_SOURCE_PATH

        self.ui_builder = MediaLoaderUIBuilder(self)
        self.source_controller = MediaLoaderSourceController(self)
        self.directory_controller = MediaLoaderDirectoryController(self)
        self.worker_controller = MediaLoaderWorkerController(self)

        self.ui_builder._build_ui()

    # ------------------------------------------------------------------
    # Directory browse facade
    # ------------------------------------------------------------------
    @Slot()
    def browse_download_directory(self):
        return self.directory_controller.browse_download_directory()

    # ------------------------------------------------------------------
    # Source switch facade
    # ------------------------------------------------------------------
    @Slot(int)
    def on_source_changed(self, index: int) -> None:
        return self.source_controller.on_source_changed(index)

    # ------------------------------------------------------------------
    # Download worker facade
    # ------------------------------------------------------------------
    @Slot()
    def start_download(self):
        return self.worker_controller.start_download()

    @Slot()
    def cancel_download(self):
        return self.worker_controller.cancel_download()

    def _on_media_saved(self, path: str) -> None:
        return self.worker_controller._on_media_saved(path)

    def _on_download_finished(self, count: int, message: str) -> None:
        return self.worker_controller._on_download_finished(count, message)

    def _on_download_error(self, message: str) -> None:
        return self.worker_controller._on_download_error(message)

    # ------------------------------------------------------------------
    # UI builder facade
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        return self.ui_builder._build_ui()

    def _setup_reddit_page(self) -> None:
        return self.ui_builder._setup_reddit_page()

    def _setup_nhentai_page(self) -> None:
        return self.ui_builder._setup_nhentai_page()


__all__ = ["MediaLoaderTab"]

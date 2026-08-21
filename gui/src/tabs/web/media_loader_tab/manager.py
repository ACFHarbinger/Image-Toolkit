"""``MediaLoaderTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Any, Optional

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtWidgets import QWidget

from ._directory_browse import _DirectoryBrowseMixin
from ._download_worker import _DownloadWorkerMixin
from ._source_switch import _SourceSwitchMixin
from ._ui_builder import _UIBuilderMixin


class MediaLoaderTab(
    _UIBuilderMixin,
    _SourceSwitchMixin,
    _DirectoryBrowseMixin,
    _DownloadWorkerMixin,
    QWidget,
):
    """GUI tab for downloading media (images/video) from the web.

    First two source integrations: Reddit (via ``asyncpraw``) and nhentai
    (gallery-page scrape) -- see ``backend/src/web/downloaders``.
    """

    def __init__(self):
        super().__init__()
        self.worker: Optional[Any] = None
        self.saved_count = 0
        self.last_browsed_download_dir = LOCAL_SOURCE_PATH

        self._build_ui()


__all__ = ["MediaLoaderTab"]

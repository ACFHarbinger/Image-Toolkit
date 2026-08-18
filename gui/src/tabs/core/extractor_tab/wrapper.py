"""Outer Extractor tab: Video + Image subtabs, with attribute delegation to
the Video subtab.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ..image_extractor_subtab import ImageExtractorSubTab
from .manager import VideoExtractorSubTab


class ExtractorTab(QWidget):
    """Outer Extractor tab containing Video and Image subtabs (mirrors the
    Convert/Wallpaper tab pattern).

    The Video subtab is the pre-existing video frame extractor
    (`VideoExtractorSubTab`); the Image subtab cuts multi-frame image files
    (strips/grids) into individual frames.

    Attribute access is transparently delegated to the Video subtab: the
    main window configures the extractor by duck-typed attribute
    reads/writes keyed on ``type(tab).__name__ == "ExtractorTab"`` (e.g.
    ``extraction_dir``, ``wheel_seek_ms``, ``time_display_format``,
    ``_initial_pixmap_cache``), and the GUI tests drive video-extractor
    internals directly on the tab instance. Delegation keeps every one of
    those call sites working unchanged.
    """

    # Signals for QML (re-emitted from the Video subtab)
    qml_source_path_changed = Signal(str)
    qml_extraction_status = Signal(str)

    def __init__(self):
        super().__init__()
        self.video_subtab = VideoExtractorSubTab()
        self.image_subtab = ImageExtractorSubTab()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._subtabs = QTabWidget()
        self._subtabs.setDocumentMode(True)
        self._subtabs.addTab(self.video_subtab, "Video")
        self._subtabs.addTab(self.image_subtab, "Image")
        layout.addWidget(self._subtabs)

        self.video_subtab.qml_source_path_changed.connect(
            self.qml_source_path_changed
        )
        self.video_subtab.qml_extraction_status.connect(self.qml_extraction_status)

    # --- Transparent delegation to the Video subtab ---

    def __getattr__(self, name):
        # Only reached when normal lookup fails; forward to the video
        # subtab so duck-typed hasattr()/getattr() call sites (main window
        # settings application, session recovery, tests) see the video
        # extractor's full surface.
        video = self.__dict__.get("video_subtab")
        if video is None:
            raise AttributeError(name)
        return getattr(video, name)

    def __setattr__(self, name, value):
        # Writes to attributes that exist on the video subtab (and not on
        # the wrapper itself) are forwarded, so e.g.
        # ``tab.extraction_dir = ...`` from the main window lands where the
        # extraction logic reads it.
        video = self.__dict__.get("video_subtab")
        if (
            video is not None
            and name not in self.__dict__
            and not hasattr(type(self), name)
            and hasattr(video, name)
        ):
            setattr(video, name, value)
        else:
            super().__setattr__(name, value)

    # --- Session recovery / tab configs ---

    def collect(self) -> Dict[str, Any]:
        config = self.video_subtab.collect()
        config["image_extractor"] = self.image_subtab.collect()
        return config

    def set_config(self, config: Dict[str, Any], quiet: bool = False):
        image_config = config.get("image_extractor")
        if isinstance(image_config, dict):
            self.image_subtab.set_config(image_config)
        self.video_subtab.set_config(config, quiet=quiet)

    def cancel_loading(self):
        self.video_subtab.cancel_loading()
        self.image_subtab.cancel_loading()

    def has_active_extractions(self) -> bool:
        return self.video_subtab.has_active_extractions()

    def set_close_when_finished(self, callback) -> None:
        self.video_subtab.set_close_when_finished(callback)

    def set_close_progress_dialog(self, dialog) -> None:
        self._close_progress_dialog = dialog
        self.video_subtab.set_close_progress_dialog(dialog)

    def get_tasks_progress(self) -> tuple[int, int, str]:
        return self.video_subtab.get_tasks_progress()

    def cancel_queue(self) -> None:
        self.video_subtab.cancel_queue()

    def cancel_extraction(self) -> None:
        self.video_subtab.cancel_extraction()

    def closeEvent(self, event):
        self.video_subtab.close()
        self.image_subtab.close()
        super().closeEvent(event)

    # --- QML slots (must be real Slots on this class so the QML bridge
    # sees them through the meta-object system) ---

    @Slot(str)
    def browse_source_qml(self, current_path=""):
        return self.video_subtab.browse_source_qml(current_path)

    @Slot(str, int)
    def extract_single_frame_qml(self, video_path, timestamp_ms):
        return self.video_subtab.extract_single_frame_qml(video_path, timestamp_ms)

    @Slot(str, int, int, int)
    def extract_range_qml(self, video_path, start_ms, end_ms, fps):
        return self.video_subtab.extract_range_qml(video_path, start_ms, end_ms, fps)


__all__ = ["ExtractorTab"]

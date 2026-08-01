"""Simple settings sections with no dedicated logic beyond widget construction.

Extracted from ``settings_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from backend.src.web.clients.mal_dispatcher import MAL_FETCH_METHODS
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QWidget,
)


class _MiscSectionsMixin:
    """Builds the Gallery/Display, Media/Extractor, MAL Auto-Fill, and Slideshow sections."""

    def _build_gallery_section(self) -> QGroupBox:
        gallery_groupbox = QGroupBox("Gallery and Display")
        gallery_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        gallery_layout = QFormLayout(gallery_groupbox)
        gallery_layout.setContentsMargins(10, 10, 10, 10)

        self.thumbnail_size_spinbox = QSpinBox()
        self.thumbnail_size_spinbox.setRange(48, 512)
        self.thumbnail_size_spinbox.setSingleStep(16)
        self.thumbnail_size_spinbox.setValue(self.pref_thumbnail_size)
        self.thumbnail_size_spinbox.setToolTip(
            "Default thumbnail pixel size used across all gallery tabs (restart required)"
        )
        gallery_layout.addRow("Default Thumbnail Size (px):", self.thumbnail_size_spinbox)

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["50", "100", "150", "200", "300"])
        self.page_size_combo.setCurrentText(str(self.pref_page_size))
        self.page_size_combo.setToolTip("Default number of images loaded per gallery page (restart required)")
        gallery_layout.addRow("Default Gallery Page Size:", self.page_size_combo)

        self.confirm_deletions_check = QCheckBox("Require confirmation before deleting files")
        self.confirm_deletions_check.setChecked(self.pref_confirm_deletions)
        gallery_layout.addRow(self.confirm_deletions_check)

        self.send_to_trash_check = QCheckBox("Send deleted files to system trash instead of permanent removal")
        self.send_to_trash_check.setChecked(self.pref_send_to_trash)
        gallery_layout.addRow(self.send_to_trash_check)

        self.recursive_scan_check = QCheckBox("Enable recursive directory scanning")
        self.recursive_scan_check.setChecked(self.pref_recursive_scan)
        self.recursive_scan_check.setToolTip("When enabled, directory searches will walk through all subdirectories")
        gallery_layout.addRow(self.recursive_scan_check)

        return gallery_groupbox

    def _build_media_section(self) -> QGroupBox:
        media_groupbox = QGroupBox("Media Player and Extractor")
        media_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        media_layout = QFormLayout(media_groupbox)
        media_layout.setContentsMargins(10, 10, 10, 10)

        self.extractor_seek_spinbox = QSpinBox()
        self.extractor_seek_spinbox.setRange(10, 5000)
        self.extractor_seek_spinbox.setSingleStep(10)
        self.extractor_seek_spinbox.setSuffix(" ms")
        self.extractor_seek_spinbox.setValue(self.pref_extractor_seek_ms)
        self.extractor_seek_spinbox.setToolTip(
            "Time interval to seek when using the mouse wheel or arrow keys in the Extractor tab"
        )
        media_layout.addRow("Extractor Seek Interval:", self.extractor_seek_spinbox)

        self.recent_extractions_spinbox = QSpinBox()
        self.recent_extractions_spinbox.setRange(1, 100)
        self.recent_extractions_spinbox.setValue(self.pref_recent_extractions_count)
        self.recent_extractions_spinbox.setToolTip("Number of most recent extraction configurations/parameters to save")
        media_layout.addRow("Recent Extractions Limit:", self.recent_extractions_spinbox)

        self.enable_queue_check = QCheckBox("Enable Extraction Queue")
        self.enable_queue_check.setToolTip(
            "Queue extraction requests sequentially instead of executing them immediately"
        )
        self.enable_queue_check.setChecked(self.pref_enable_extraction_queue)
        media_layout.addRow(self.enable_queue_check)

        self.extractor_time_format_combo = QComboBox()
        self.extractor_time_format_combo.addItems(["h:m:s", "m:s:ms", "microseconds", "milliseconds"])
        self.extractor_time_format_combo.setCurrentText(self.pref_extractor_time_format)
        self.extractor_time_format_combo.setToolTip(
            "Change how the video time in the extractor tab is displayed (e.g. h:m:s, m:s:ms, microseconds)"
        )
        media_layout.addRow("Extractor Time Display Format:", self.extractor_time_format_combo)

        return media_groupbox

    def _build_mal_section(self) -> QGroupBox:
        mal_groupbox = QGroupBox("MyAnimeList Auto-Fill")
        mal_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        mal_layout = QFormLayout(mal_groupbox)
        mal_layout.setContentsMargins(10, 10, 10, 10)

        self.mal_fetch_method_combo = QComboBox()
        for _key, _label in MAL_FETCH_METHODS:
            self.mal_fetch_method_combo.addItem(_label, _key)
        _current_mal_index = self.mal_fetch_method_combo.findData(self.pref_mal_fetch_method)
        self.mal_fetch_method_combo.setCurrentIndex(max(_current_mal_index, 0))
        self.mal_fetch_method_combo.setToolTip(
            "How 'Auto-Fill from MAL' in the Listings tab fetches anime data.\n"
            "Jikan API: default, richest data, but a third-party MAL proxy that\n"
            "  can fail (504) independently of MAL itself for uncached titles.\n"
            "Official MyAnimeList API: hits MAL directly, needs a free client ID\n"
            "  (backend/config/api_keys.yaml [myanimelist] or MAL_CLIENT_ID),\n"
            "  no character/staff data available.\n"
            "Direct Website Scraping: scrapes myanimelist.net directly, no key\n"
            "  needed, full data, but slower (2-3 page loads) and more fragile."
        )
        mal_layout.addRow("Auto-Fill Method:", self.mal_fetch_method_combo)

        return mal_groupbox

    def _build_slideshow_section(self) -> QGroupBox:
        slideshow_groupbox = QGroupBox("Slideshow Defaults")
        slideshow_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        slideshow_def_layout = QFormLayout(slideshow_groupbox)
        slideshow_def_layout.setContentsMargins(10, 10, 10, 10)

        interval_widget = QWidget()
        interval_layout = QHBoxLayout(interval_widget)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        self.slideshow_default_min_spinbox = QSpinBox()
        self.slideshow_default_min_spinbox.setRange(0, 60)
        self.slideshow_default_min_spinbox.setValue(self.pref_slideshow_min)
        self.slideshow_default_min_spinbox.setFixedWidth(60)
        self.slideshow_default_sec_spinbox = QSpinBox()
        self.slideshow_default_sec_spinbox.setRange(0, 59)
        self.slideshow_default_sec_spinbox.setValue(self.pref_slideshow_sec)
        self.slideshow_default_sec_spinbox.setFixedWidth(60)
        interval_layout.addWidget(self.slideshow_default_min_spinbox)
        interval_layout.addWidget(QLabel("min"))
        interval_layout.addWidget(self.slideshow_default_sec_spinbox)
        interval_layout.addWidget(QLabel("sec"))
        interval_layout.addStretch(1)
        slideshow_def_layout.addRow("Default Interval:", interval_widget)

        self.slideshow_default_order_combo = QComboBox()
        self.slideshow_default_order_combo.addItems(["Sequential", "Reverse Sequential", "Random"])
        self.slideshow_default_order_combo.setCurrentText(self.pref_slideshow_order)
        slideshow_def_layout.addRow("Default Playback Order:", self.slideshow_default_order_combo)

        return slideshow_groupbox


__all__ = ["_MiscSectionsMixin"]

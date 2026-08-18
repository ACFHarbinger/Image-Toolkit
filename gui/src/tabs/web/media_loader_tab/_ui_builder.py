"""Widget construction for ``MediaLoaderTab`` (source picker, per-source
settings pages, shared download/run controls)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.constants.elements import SOURCE_REDDIT

from ....styles import apply_shadow_effect

SOURCE_NHENTAI = 1


class _UIBuilderMixin:
    """Builds the source-type stack, output settings, and run controls."""

    def _get_group_style(self):
        return """
            QGroupBox { border: 1px solid #4f545c; border-radius: 8px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 4px 10px; color: white; border-radius: 4px; }
        """

    def _get_run_btn_style(self):
        return """
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2); color: white; font-weight: bold; padding: 14px; border-radius: 10px; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #764ba2, stop:1 #667eea); }
        """

    def _get_cancel_btn_style(self):
        return """
            QPushButton { background-color: #cc3333; color: white; font-weight: bold; padding: 14px; border-radius: 10px; }
            QPushButton:hover { background-color: #ff4444; }
        """

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # --- 1. Source Selection ---
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("<b>Source:</b>"))

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Reddit", "nhentai"])
        self.source_combo.currentIndexChanged.connect(self.on_source_changed)
        source_layout.addWidget(self.source_combo, 1)

        main_layout.addLayout(source_layout)

        # --- 2. Stacked Widget for Source-Specific Settings ---
        self.settings_stack = QStackedWidget()

        self.page_reddit = QWidget()
        self._setup_reddit_page()
        self.settings_stack.addWidget(self.page_reddit)

        self.page_nhentai = QWidget()
        self._setup_nhentai_page()
        self.settings_stack.addWidget(self.page_nhentai)

        main_layout.addWidget(self.settings_stack)

        # --- 3. Shared Output Settings ---
        output_group = QGroupBox("Output Configuration")
        output_group.setStyleSheet(self._get_group_style())
        output_layout = QFormLayout(output_group)
        output_layout.setContentsMargins(10, 20, 10, 10)

        download_dir_layout = QHBoxLayout()
        self.download_dir_path = QLineEdit()
        self.download_dir_path.setText(self.last_browsed_download_dir)
        btn_browse_download = QPushButton("Browse...")
        btn_browse_download.clicked.connect(self.browse_download_directory)
        apply_shadow_effect(
            btn_browse_download, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        download_dir_layout.addWidget(self.download_dir_path)
        download_dir_layout.addWidget(btn_browse_download)
        output_layout.addRow("Download Dir:", download_dir_layout)

        self.on_exists_combo = QComboBox()
        self.on_exists_combo.addItem("Overwrite existing", "overwrite")
        self.on_exists_combo.addItem("Skip existing", "skip")
        self.on_exists_combo.addItem("Rename (name(1).ext)", "rename")
        output_layout.addRow("If file exists:", self.on_exists_combo)

        main_layout.addWidget(output_group)

        # --- 4. Run Controls ---
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #aaa; font-style: italic; padding: 8px;"
        )
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        self.run_button = QPushButton("Download")
        self.run_button.setStyleSheet(self._get_run_btn_style())
        apply_shadow_effect(
            self.run_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.run_button.clicked.connect(self.start_download)
        main_layout.addWidget(self.run_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet(self._get_cancel_btn_style())
        apply_shadow_effect(
            self.cancel_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.cancel_button.clicked.connect(self.cancel_download)
        self.cancel_button.hide()
        main_layout.addWidget(self.cancel_button)

        main_layout.addStretch(1)

        self.on_source_changed(self.source_combo.currentIndex())

    def _setup_reddit_page(self) -> None:
        layout = QVBoxLayout(self.page_reddit)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Reddit Settings")
        group.setStyleSheet(self._get_group_style())
        form = QFormLayout(group)
        form.setContentsMargins(10, 20, 10, 10)

        self.reddit_mode_combo = QComboBox()
        self.reddit_mode_combo.addItems(["Subreddit", "User", "Single Post"])
        form.addRow("Mode:", self.reddit_mode_combo)

        self.reddit_source_input = QLineEdit()
        self.reddit_source_input.setPlaceholderText(
            "e.g. EarthPorn, u/someuser, or a full post URL"
        )
        form.addRow("Subreddit / User / URL:", self.reddit_source_input)

        self.reddit_sort_combo = QComboBox()
        self.reddit_sort_combo.addItems(["hot", "new", "top"])
        form.addRow("Sort:", self.reddit_sort_combo)

        self.reddit_limit_spin = QSpinBox()
        self.reddit_limit_spin.setRange(1, 1000)
        self.reddit_limit_spin.setValue(50)
        form.addRow("Post Limit:", self.reddit_limit_spin)

        self.reddit_download_images_chk = QCheckBox("Images / galleries")
        self.reddit_download_images_chk.setChecked(True)
        form.addRow("", self.reddit_download_images_chk)

        self.reddit_download_videos_chk = QCheckBox(
            "Videos (v.redd.it, video-only stream — no audio)"
        )
        self.reddit_download_videos_chk.setChecked(True)
        form.addRow("", self.reddit_download_videos_chk)

        layout.addWidget(group)
        layout.addStretch(1)

    def _setup_nhentai_page(self) -> None:
        layout = QVBoxLayout(self.page_nhentai)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("nhentai Settings")
        group.setStyleSheet(self._get_group_style())
        form = QFormLayout(group)
        form.setContentsMargins(10, 20, 10, 10)

        self.nhentai_gallery_input = QLineEdit()
        self.nhentai_gallery_input.setPlaceholderText(
            "Gallery id (177013) or full URL (https://nhentai.net/g/177013/)"
        )
        form.addRow("Gallery:", self.nhentai_gallery_input)

        layout.addWidget(group)
        layout.addStretch(1)


__all__ = ["_UIBuilderMixin", "SOURCE_REDDIT", "SOURCE_NHENTAI"]

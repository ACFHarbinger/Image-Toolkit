"""Widget construction for ``MediaLoaderTab`` (source picker, per-source
settings pages, shared download/run controls)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from ....components import FormSection
from ....styles import apply_shadow_effect, set_button_role
from ....theming.theme_api import color, qss
from ._tab_bound import TabBoundController

SOURCE_NHENTAI = 1


class MediaLoaderUIBuilder(TabBoundController):
    """Builds the source-type stack, output settings, and run controls (§5 R2.f, #567)."""

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self.tab)
        self._build_source_selection(main_layout)
        self._build_stacked_settings(main_layout)
        self._build_output_settings(main_layout)
        self._build_run_controls(main_layout)
        main_layout.addStretch(1)
        self.on_source_changed(self.source_combo.currentIndex())

    def _build_source_selection(self, main_layout: QVBoxLayout) -> None:
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("<b>Source:</b>"))

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Reddit", "nhentai"])
        self.source_combo.currentIndexChanged.connect(self.on_source_changed)
        source_layout.addWidget(self.source_combo, 1)
        main_layout.addLayout(source_layout)

    def _build_stacked_settings(self, main_layout: QVBoxLayout) -> None:
        self.settings_stack = QStackedWidget()

        self.page_reddit = QWidget()
        self._setup_reddit_page()
        self.settings_stack.addWidget(self.page_reddit)

        self.page_nhentai = QWidget()
        self._setup_nhentai_page()
        self.settings_stack.addWidget(self.page_nhentai)

        main_layout.addWidget(self.settings_stack)

    def _build_output_settings(self, main_layout: QVBoxLayout) -> None:
        sec = FormSection("Output Configuration", layout_type="form")

        self.download_dir_path = QLineEdit()
        self.download_dir_path.setText(self.last_browsed_download_dir)
        btn_browse_download = QPushButton("Browse...")
        btn_browse_download.clicked.connect(self.browse_download_directory)
        sec.add_path_picker(self.download_dir_path, btn_browse_download, label="Download Dir:")

        self.on_exists_combo = QComboBox()
        self.on_exists_combo.addItem("Overwrite existing", "overwrite")
        self.on_exists_combo.addItem("Skip existing", "skip")
        self.on_exists_combo.addItem("Rename (name(1).ext)", "rename")
        sec.add_row("If file exists:", self.on_exists_combo)

        main_layout.addWidget(sec.group_box)

    def _build_run_controls(self, main_layout: QVBoxLayout) -> None:
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(qss("status_label_padded"))
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        self.run_button = QPushButton("Download")
        set_button_role(self.run_button, "success")
        apply_shadow_effect(self.run_button, color_hex=color("window_bg"), radius=8, x_offset=0, y_offset=3)
        self.run_button.clicked.connect(self.start_download)
        main_layout.addWidget(self.run_button)

        self.cancel_button = QPushButton("Cancel")
        set_button_role(self.cancel_button, "danger")
        apply_shadow_effect(self.cancel_button, color_hex=color("window_bg"), radius=8, x_offset=0, y_offset=3)
        self.cancel_button.clicked.connect(self.cancel_download)
        self.cancel_button.hide()
        main_layout.addWidget(self.cancel_button)

    def _setup_reddit_page(self) -> None:
        layout = QVBoxLayout(self.page_reddit)
        layout.setContentsMargins(0, 0, 0, 0)

        sec = FormSection("Reddit Settings", layout_type="form")

        self.reddit_mode_combo = QComboBox()
        self.reddit_mode_combo.addItems(["Subreddit", "User", "Single Post"])
        sec.add_row("Mode:", self.reddit_mode_combo)

        self.reddit_source_input = QLineEdit()
        self.reddit_source_input.setPlaceholderText("e.g. EarthPorn, u/someuser, or a full post URL")
        sec.add_row("Subreddit / User / URL:", self.reddit_source_input)

        self.reddit_sort_combo = QComboBox()
        self.reddit_sort_combo.addItems(["hot", "new", "top"])
        sec.add_row("Sort:", self.reddit_sort_combo)

        self.reddit_limit_spin = QSpinBox()
        self.reddit_limit_spin.setRange(1, 1000)
        self.reddit_limit_spin.setValue(50)
        sec.add_row("Post Limit:", self.reddit_limit_spin)

        self.reddit_download_images_chk = QCheckBox("Images / galleries")
        self.reddit_download_images_chk.setChecked(True)
        sec.add_row("", self.reddit_download_images_chk)

        self.reddit_download_videos_chk = QCheckBox("Videos (v.redd.it, video-only stream — no audio)")
        self.reddit_download_videos_chk.setChecked(True)
        sec.add_row("", self.reddit_download_videos_chk)

        layout.addWidget(sec.group_box)
        layout.addStretch(1)

    def _setup_nhentai_page(self) -> None:
        layout = QVBoxLayout(self.page_nhentai)
        layout.setContentsMargins(0, 0, 0, 0)

        sec = FormSection("nhentai Settings", layout_type="form")

        self.nhentai_gallery_input = QLineEdit()
        self.nhentai_gallery_input.setPlaceholderText("Gallery id (177013) or full URL (https://nhentai.net/g/177013/)")
        sec.add_row("Gallery:", self.nhentai_gallery_input)

        layout.addWidget(sec.group_box)
        layout.addStretch(1)


__all__ = ["MediaLoaderUIBuilder", "SOURCE_REDDIT", "SOURCE_NHENTAI"]

"""Widget construction for ``_DetailPanel`` (``_build_ui``).

Extracted from ``detail_panel.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from gui.src.constants.listings import ENTRY_STATUS, ENTRY_TYPES
from gui.src.styles import SHARED_BUTTON_STYLE, apply_shadow_effect
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)


class _UIBuilderMixin:
    """Builds the image preview, form fields, episode list, and action buttons."""

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Image preview setup from BaseDetailPanel
        self.img_preview.setFixedSize(160, 160)
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet("border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;")

        img_row = QHBoxLayout()
        img_row.addWidget(self.img_preview)

        img_btns_layout = QVBoxLayout()
        img_btns_layout.setSpacing(6)
        img_btns_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse_image)
        browse_btn.setFixedWidth(140)
        img_btns_layout.addWidget(browse_btn)

        self.btn_gen_thumb = QPushButton("⚡ Gen Thumbnail")
        self.btn_gen_thumb.setToolTip("Extract thumbnail/cover from the associated Local File")
        self.btn_gen_thumb.clicked.connect(self._generate_thumbnail)
        self.btn_gen_thumb.setFixedWidth(140)
        img_btns_layout.addWidget(self.btn_gen_thumb)

        self.btn_mal = QPushButton("Auto-Fill from MAL")
        self.btn_mal.setToolTip("Fetch metadata from MyAnimeList via Jikan API (Anime only)")
        self.btn_mal.setFixedWidth(140)
        self.btn_mal.setStyleSheet(
            "QPushButton { background-color:#1565c0; color:white; font-weight:bold;"
            " padding:6px 8px; border-radius:6px; border:none; }"
            "QPushButton:hover { background-color:#1976d2; }"
            "QPushButton:pressed { background-color:#0d47a1; }"
            "QPushButton:disabled { background-color:#37474f; color:#78909c; }"
        )
        self.btn_mal.clicked.connect(self._on_fetch_mal_clicked)
        img_btns_layout.addWidget(self.btn_mal)

        img_row.addLayout(img_btns_layout)
        img_row.addStretch()
        layout.addLayout(img_row)

        # Form
        form = QFormLayout()
        form.setSpacing(8)

        self.f_title = QLineEdit()
        self.f_title.setPlaceholderText("e.g. Cowboy Bebop")
        self.f_type = QComboBox()
        self.f_type.addItems(ENTRY_TYPES)
        self.btn_mal.setEnabled(self.f_type.currentText() == "Anime")
        self.f_type.currentTextChanged.connect(lambda text: self.btn_mal.setEnabled(text == "Anime"))
        self.f_status = QComboBox()
        self.f_status.addItems(ENTRY_STATUS)
        self.f_personal_rating = QSpinBox()
        self.f_personal_rating.setRange(0, 10)
        self.f_personal_rating.setSpecialValueText("No rating")
        self.f_community_rating = QDoubleSpinBox()
        self.f_community_rating.setRange(0.0, 10.0)
        self.f_community_rating.setSingleStep(0.01)
        self.f_community_rating.setDecimals(2)
        self.f_community_rating.setSpecialValueText("No rating")
        self.f_year = QSpinBox()
        self.f_year.setRange(0, 2100)
        self.f_year.setValue(0)
        self.f_year.setSpecialValueText("Unknown")
        self.f_episodes = QSpinBox()
        self.f_episodes.setRange(1, 99999)
        self.f_current_episode = QSpinBox()
        self.f_current_episode.setRange(0, 99999)
        self.f_episodes.valueChanged.connect(lambda val: self.f_current_episode.setRange(0, max(0, val)))
        self.f_genres = QLineEdit()
        self.f_genres.setPlaceholderText("e.g. Action, Drama")

        self.f_tags = QLineEdit()
        self.f_tags.setPlaceholderText("e.g. Space Cowboy, Sci-Fi")

        # Associated Entities selection row
        self.assoc_entities_ids = []
        # QTextEdit (not QLabel) so the field can scroll instead of clipping
        # once the associated-entity list grows past its fixed height.
        self.f_assoc_entities_display = QTextEdit()
        self.f_assoc_entities_display.setReadOnly(True)
        self.f_assoc_entities_display.setPlaceholderText("None selected")
        self.f_assoc_entities_display.setFixedHeight(56)  # ~2 lines of wrapped text
        self.f_assoc_entities_display.setStyleSheet(
            "background:#23272a; border:1px solid #4f545c; border-radius:4px;padding:4px 6px; color:white;"
        )

        self.btn_select_entities = QPushButton("🔗 Select Entities")
        self.btn_select_entities.clicked.connect(self._select_associated_entities)

        assoc_row = QHBoxLayout()
        assoc_row.addWidget(self.f_assoc_entities_display, 1)
        assoc_row.addWidget(self.btn_select_entities)

        # DB.8a: Linked Image Groups row
        self.f_linked_groups_display = QTextEdit()
        self.f_linked_groups_display.setReadOnly(True)
        self.f_linked_groups_display.setPlaceholderText("None linked")
        self.f_linked_groups_display.setFixedHeight(40)
        self.f_linked_groups_display.setStyleSheet(
            "background:#23272a; border:1px solid #4f545c; border-radius:4px;padding:4px 6px; color:white;"
        )
        self.btn_select_linked_groups = QPushButton("🖼️ Link Image Groups")
        self.btn_select_linked_groups.clicked.connect(self._select_linked_groups)

        linked_groups_row = QHBoxLayout()
        linked_groups_row.addWidget(self.f_linked_groups_display, 1)
        linked_groups_row.addWidget(self.btn_select_linked_groups)

        # Local File and Web Link rows
        self.f_local_file = QLineEdit()
        self.f_local_file.setPlaceholderText("Select/paste local file path…")
        self.btn_browse_local_file = QPushButton("📁 Browse")
        self.btn_browse_local_file.clicked.connect(self._browse_local_file)
        self.btn_open_local_file = QPushButton("🚀 Open Location")
        self.btn_open_local_file.clicked.connect(self._open_local_file)

        local_file_row = QHBoxLayout()
        local_file_row.addWidget(self.f_local_file, 1)
        local_file_row.addWidget(self.btn_browse_local_file)
        local_file_row.addWidget(self.btn_open_local_file)

        self.f_web_link = QLineEdit()
        self.f_web_link.setPlaceholderText("Enter web URL (e.g. mal.net/anime/1)…")
        self.btn_open_web_link = QPushButton("🌐 Open Link")
        self.btn_open_web_link.clicked.connect(self._open_web_link)

        web_link_row = QHBoxLayout()
        web_link_row.addWidget(self.f_web_link, 1)
        web_link_row.addWidget(self.btn_open_web_link)

        # Summary
        self.f_summary = QTextEdit()
        self.f_summary.setPlaceholderText("Synopsis / Summary (auto-filled from web, or write your own)…")
        self.f_summary.setFixedHeight(75)

        # Personal review / notes
        self.f_review = QTextEdit()
        self.f_review.setPlaceholderText("Personal review or notes…")
        self.f_review.setFixedHeight(80)

        form.addRow("Title *", self.f_title)
        form.addRow("Type", self.f_type)
        form.addRow("Status", self.f_status)
        form.addRow("My Rating (0-10)", self.f_personal_rating)
        form.addRow("Community Rating", self.f_community_rating)
        form.addRow("Year", self.f_year)
        form.addRow("Episodes / Pages", self.f_episodes)
        form.addRow("Current Episode / Page", self.f_current_episode)
        form.addRow("Genres", self.f_genres)
        form.addRow("Tags", self.f_tags)
        form.addRow("Associated Entities", assoc_row)
        form.addRow("Linked Image Groups", linked_groups_row)
        form.addRow("Local File", local_file_row)
        form.addRow("Web Link", web_link_row)
        form.addRow("Summary", self.f_summary)
        form.addRow("Review / Notes", self.f_review)
        layout.addLayout(form)

        # --- Episode List Section ---
        self.episode_group = QGroupBox("Episodes / Chapters / Parts")
        self.episode_group.setStyleSheet("QGroupBox{font-weight:bold; color:#00bcd4;}")
        eg_layout = QVBoxLayout(self.episode_group)

        self.ep_list_layout = QVBoxLayout()
        self.ep_list_layout.setSpacing(4)
        eg_layout.addLayout(self.ep_list_layout)

        add_ep_btn = QPushButton("＋ Add Episode Entry")
        add_ep_btn.clicked.connect(self._add_episode)
        eg_layout.addWidget(add_ep_btn)
        layout.addWidget(self.episode_group)

        # Action buttons
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        self.save_btn.clicked.connect(self._on_save)
        apply_shadow_effect(self.save_btn)

        self.del_btn = QPushButton("🗑 Delete")
        self.del_btn.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;font-weight:bold;"
            "padding:10px;border-radius:8px;}"
            "QPushButton:hover{background:#e74c3c;}"
        )
        self.del_btn.clicked.connect(self._on_delete)
        apply_shadow_effect(self.del_btn)

        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.del_btn)
        layout.addLayout(btn_row)
        layout.addStretch()


__all__ = ["_UIBuilderMixin"]

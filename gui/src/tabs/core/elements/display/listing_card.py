from typing import Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QMenu, QPushButton

from gui.src.constants.listings import (
    CARD_SIZE,
    PLACEHOLDER,
    TYPE_COLORS,
    STATUS_COLORS,
)
from gui.src.tabs.core.elements.common.listings_common import (
    _badge,
    open_file_location,
    open_web_link,
)
from gui.src.tabs.core.elements.display.common.base_card import BaseCard


class _ListingCard(BaseCard):
    def __init__(self, entry: Dict[str, Any], parent=None):
        super().__init__(
            item_id=entry["id"],
            image_path=entry.get("image_path", ""),
            placeholder=PLACEHOLDER,
            parent=parent,
        )
        self.entry = entry
        self.setObjectName("listing_card")
        self.setStyleSheet(
            "QWidget#listing_card{background:#2c2f33;border:2px solid #4f545c;"
            "border-radius:8px;}"
            "QWidget#listing_card:hover{border:2px solid #00bcd4;}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail
        layout.addWidget(self.thumb_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Title
        title_lbl = QLabel(entry.get("title", "Untitled"))
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setWordWrap(False)
        title_lbl.setStyleSheet(
            "color:#ffffff;font-weight:bold;font-size:11px;border:none;"
        )
        title_lbl.setFixedWidth(CARD_SIZE - 4)
        fm = title_lbl.fontMetrics()
        title_lbl.setText(
            fm.elidedText(
                entry.get("title", "Untitled"),
                Qt.TextElideMode.ElideRight,
                CARD_SIZE - 10,
            )
        )
        title_lbl.setToolTip(entry.get("title", ""))
        layout.addWidget(title_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Badges row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        t = entry.get("type", "Other")
        s = entry.get("status", "Plan to Watch")
        badge_row.addWidget(_badge(t, TYPE_COLORS.get(t, "#607d8b")))
        badge_row.addWidget(_badge(s[:9], STATUS_COLORS.get(s, "#95a5a6")))
        layout.addLayout(badge_row)

        # Progress info
        current_ep = entry.get("current_episode", 0)
        total_eps = entry.get("episodes", 1)
        prog_lbl = QLabel(f"Prog: {current_ep} / {total_eps}")
        prog_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prog_lbl.setStyleSheet("color:#888; font-size:10px; border:none;")
        layout.addWidget(prog_lbl)

        # Personal rating stars (supports old "rating" key for backwards compat)
        personal_rating = entry.get("personal_rating", entry.get("rating", 0))
        community_rating = entry.get("community_rating", 0.0)
        if personal_rating:
            stars = "★" * personal_rating + "☆" * (10 - personal_rating)
            r_lbl = QLabel(stars[:10])
            r_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            r_lbl.setStyleSheet("color:#f1c40f;font-size:9px;border:none;")
            layout.addWidget(r_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        if community_rating:
            cr_lbl = QLabel(f"Community {community_rating:.2f}")
            cr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cr_lbl.setStyleSheet("color:#f1c40f;font-size:9px;border:none;")
            layout.addWidget(cr_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Quick Actions row
        local_file_path = entry.get("local_file", "")
        web_link_url = entry.get("web_link", "")

        if local_file_path or web_link_url:
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(6)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if local_file_path:
                file_btn = QPushButton("📁 File")
                file_btn.setToolTip(f"Open location: {local_file_path}")
                file_btn.setStyleSheet(
                    "QPushButton { background:#2f3136; color:#00bcd4; border:1px solid #00bcd4; "
                    "border-radius:4px; padding:2px 6px; font-size:10px; font-weight:bold; }"
                    "QPushButton:hover { background:#00bcd4; color:black; }"
                )
                file_btn.clicked.connect(
                    lambda _, path=local_file_path: open_file_location(path)
                )
                actions_layout.addWidget(file_btn)

            if web_link_url:
                link_btn = QPushButton("🌐 Link")
                link_btn.setToolTip(f"Open link: {web_link_url}")
                link_btn.setStyleSheet(
                    "QPushButton { background:#2f3136; color:#9b59b6; border:1px solid #9b59b6; "
                    "border-radius:4px; padding:2px 6px; font-size:10px; font-weight:bold; }"
                    "QPushButton:hover { background:#9b59b6; color:white; }"
                )
                link_btn.clicked.connect(lambda _, url=web_link_url: open_web_link(url))
                actions_layout.addWidget(link_btn)

            layout.addLayout(actions_layout)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )

        edit_act = QAction("✎ Edit Details", self)
        edit_act.triggered.connect(lambda: self.clicked.emit(self._id))
        menu.addAction(edit_act)

        add_act = QAction("＋ Add New Content", self)
        add_act.triggered.connect(lambda: self.add_requested.emit())
        menu.addAction(add_act)

        local_file = self.entry.get("local_file", "")
        web_link = self.entry.get("web_link", "")
        if local_file or web_link:
            menu.addSeparator()
            if local_file:
                file_act = QAction("📁 Open File Location", self)
                file_act.triggered.connect(
                    lambda _, path=local_file: open_file_location(path)
                )
                menu.addAction(file_act)
            if web_link:
                link_act = QAction("🌐 Open Web Link", self)
                link_act.triggered.connect(lambda _, url=web_link: open_web_link(url))
                menu.addAction(link_act)

        img_path = self.entry.get("image_path", "")
        if img_path:
            menu.addSeparator()
            open_img_loc_act = QAction("📂 Open Image Location", self)
            open_img_loc_act.triggered.connect(
                lambda _, path=img_path: open_file_location(path)
            )
            menu.addAction(open_img_loc_act)

            remove_img_act = QAction("🖼 Delete / Remove Image", self)
            remove_img_act.triggered.connect(
                lambda: self.image_remove_requested.emit(self._id)
            )
            menu.addAction(remove_img_act)

        menu.addSeparator()

        del_act = QAction("🗑 Remove Content", self)
        del_act.triggered.connect(lambda: self.delete_requested.emit(self._id))
        menu.addAction(del_act)

        menu.exec(self.mapToGlobal(pos))

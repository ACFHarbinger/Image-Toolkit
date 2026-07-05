from typing import Any, Dict

from gui.src.constants.listings import (
    CARD_SIZE,
    ENTITY_PLACEHOLDER,
    ENTITY_ROLE_COLORS,
    ENTITY_TYPE_COLORS,
)
from gui.src.tabs.core.elements.common.listings_common import (
    _badge,
    open_file_location,
)
from gui.src.tabs.core.elements.display.common.base_card import BaseCard
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QVBoxLayout


class _EntityCard(BaseCard):
    def __init__(self, entity: Dict[str, Any], parent=None):
        super().__init__(
            item_id=entity["id"],
            image_path=entity.get("image_path", ""),
            placeholder=ENTITY_PLACEHOLDER,
            parent=parent,
        )
        self.entity = entity
        self.setObjectName("entity_card")
        self.setStyleSheet(
            "QWidget#entity_card{background:#2c2f33;border:2px solid #4f545c;"
            "border-radius:8px;}"
            "QWidget#entity_card:hover{border:2px solid #00bcd4;}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail
        layout.addWidget(self.thumb_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Name
        name_lbl = QLabel(entity.get("name", "Unnamed"))
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setWordWrap(False)
        name_lbl.setStyleSheet(
            "color:#ffffff;font-weight:bold;font-size:11px;border:none;"
        )
        name_lbl.setFixedWidth(CARD_SIZE - 4)
        fm = name_lbl.fontMetrics()
        name_lbl.setText(
            fm.elidedText(
                entity.get("name", "Unnamed"),
                Qt.TextElideMode.ElideRight,
                CARD_SIZE - 10,
            )
        )
        name_lbl.setToolTip(entity.get("name", ""))
        layout.addWidget(name_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Badges row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        t = entity.get("type", "Other")
        r = entity.get("role", "Other")
        badge_row.addWidget(_badge(t, ENTITY_TYPE_COLORS.get(t, "#607d8b")))
        badge_row.addWidget(_badge(r[:9], ENTITY_ROLE_COLORS.get(r, "#607d8b")))
        layout.addLayout(badge_row)

        # Associated content or credits count
        credits = entity.get("credit_list", [])
        assoc = entity.get("associated_content", [])
        assoc_count = len(assoc) if isinstance(assoc, list) else (1 if assoc else 0)
        if credits:
            info_text = f"Credits: {len(credits)}"
        elif assoc_count:
            info_text = f"Content: {assoc_count}"
        else:
            info_text = ""

        if info_text:
            info_lbl = QLabel(info_text)
            info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_lbl.setStyleSheet("color:#888; font-size:10px; border:none;")
            info_lbl.setFixedWidth(CARD_SIZE - 10)
            info_lbl.setText(
                fm.elidedText(info_text, Qt.TextElideMode.ElideRight, CARD_SIZE - 10)
            )
            layout.addWidget(info_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Rating stars
        rating = entity.get("rating", 0)
        if rating:
            stars = "★" * rating + "☆" * (10 - rating)
            r_lbl = QLabel(stars[:10])
            r_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            r_lbl.setStyleSheet("color:#f1c40f;font-size:9px;border:none;")
            layout.addWidget(r_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )

        edit_act = QAction("✎ Edit Details", self)
        edit_act.triggered.connect(lambda: self.clicked.emit(self._id))
        menu.addAction(edit_act)

        add_act = QAction("＋ Add New Entity", self)
        add_act.triggered.connect(lambda: self.add_requested.emit())
        menu.addAction(add_act)

        img_path = self.entity.get("image_path", "")
        if img_path:
            menu.addSeparator()
            open_img_loc_act = QAction("📂 Open Image Location", self)
            open_img_loc_act.triggered.connect(
                lambda _, path=img_path: open_file_location(path)
            )
            menu.addAction(open_img_loc_act)

        menu.addSeparator()

        del_act = QAction("🗑 Remove Entity", self)
        del_act.triggered.connect(lambda: self.delete_requested.emit(self._id))
        menu.addAction(del_act)

        menu.exec(self.mapToGlobal(pos))

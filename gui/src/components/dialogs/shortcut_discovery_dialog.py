"""
Keyboard Shortcut Discovery Overlay Dialog (GUI/UX §2.25).

A modern, searchable cheatsheet overlay presenting all registered application
shortcuts grouped by scope with stylized keycap badges and live filtering.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...utils.manager.shortcut_manager import get_registry


class KeycapBadgeDelegate(QStyledItemDelegate):
    """Renders shortcut key combinations as modern keycap chips."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background selection highlight
        if option.state & QStyleOptionViewItem.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        val: str = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if not val or val == "(none)":
            painter.setPen(QColor(140, 140, 140))
            painter.drawText(option.rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "—")
            painter.restore()
            return

        # Split combinations like "Ctrl+Z" or multiple "Ctrl+=, Ctrl++"
        x = option.rect.x() + 4
        y_mid = option.rect.center().y()
        badge_h = 22
        y = y_mid - badge_h // 2

        combos = [c.strip() for c in val.split(",")]
        for combo_idx, combo in enumerate(combos):
            if combo_idx > 0:
                painter.setPen(QColor(160, 160, 160))
                painter.drawText(x, y + 15, "or")
                x += 20

            keys = combo.split("+")
            for k in keys:
                key_text = k.strip()
                if not key_text:
                    continue
                # Measure text width
                text_w = painter.fontMetrics().horizontalAdvance(key_text)
                badge_w = max(26, text_w + 14)

                if x + badge_w > option.rect.right() - 4:
                    break

                # Draw keycap capsule
                rect_path = QPainterPath()
                rect_path.addRoundedRect(x, y, badge_w, badge_h, 4, 4)

                is_dark = option.palette.window().color().lightness() < 128
                bg_color = QColor(48, 52, 64) if is_dark else QColor(230, 234, 240)
                border_color = QColor(76, 86, 106) if is_dark else QColor(190, 196, 206)
                text_color = QColor(236, 239, 244) if is_dark else QColor(46, 52, 64)

                painter.fillPath(rect_path, bg_color)
                painter.setPen(border_color)
                painter.drawPath(rect_path)

                # Keycap text
                font = painter.font()
                font.setBold(True)
                font.setPointSize(max(8, font.pointSize() - 1))
                painter.setFont(font)
                painter.setPen(text_color)
                painter.drawText(
                    x,
                    y,
                    badge_w,
                    badge_h,
                    Qt.AlignmentFlag.AlignCenter,
                    key_text,
                )

                x += badge_w + 4

        painter.restore()


class ScopeBadgeDelegate(QStyledItemDelegate):
    """Renders the scope name with an accent pill badge."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if option.state & QStyleOptionViewItem.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        val: str = index.data(Qt.ItemDataRole.DisplayRole) or ""
        badge_colors = {
            "General": QColor(94, 129, 172),     # Blue
            "Gallery": QColor(163, 190, 140),    # Green
            "Preview": QColor(180, 142, 173),    # Purple
            "Stitch": QColor(208, 135, 112),     # Orange
            "Convert": QColor(235, 203, 139),    # Yellow
            "Merge": QColor(136, 192, 208),      # Cyan
        }
        color = badge_colors.get(val, QColor(120, 120, 120))

        x = option.rect.x() + 6
        text_w = painter.fontMetrics().horizontalAdvance(val)
        badge_w = text_w + 14
        badge_h = 20
        y = option.rect.center().y() - badge_h // 2

        path = QPainterPath()
        path.addRoundedRect(x, y, badge_w, badge_h, 10, 10)

        # Semi-transparent background
        fill_color = QColor(color.red(), color.green(), color.blue(), 45)
        painter.fillPath(path, fill_color)
        painter.setPen(color)
        painter.drawPath(path)

        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(8, font.pointSize() - 1))
        painter.setFont(font)
        painter.drawText(x, y, badge_w, badge_h, Qt.AlignmentFlag.AlignCenter, val)

        painter.restore()


class ShortcutDiscoveryDialog(QDialog):
    """Searchable keyboard shortcuts overlay dialog with scope filtering and keycaps."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts (Ctrl+/ or F1)")
        self.resize(680, 520)
        self.setMinimumSize(560, 400)

        self._active_scope: str = "All"
        self._init_ui()
        self._populate()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # --- Header ---
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        title = QLabel("Keyboard Shortcuts Cheat Sheet")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel("Quick reference for global and context-sensitive keyboard commands.")
        subtitle.setStyleSheet("color: #888888;")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        # --- Search Filter Bar ---
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search shortcuts by action, key, or scope…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._populate)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # --- Scope Filter Pills ---
        scope_layout = QHBoxLayout()
        scope_layout.setSpacing(6)
        self._scope_group = QButtonGroup(self)
        self._scope_group.setExclusive(True)

        scopes = ["All", "General", "Gallery", "Preview", "Stitch", "Convert", "Merge"]
        for idx, sc in enumerate(scopes):
            btn = QPushButton(sc)
            btn.setCheckable(True)
            if sc == "All":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, s=sc: self._set_scope(s))
            self._scope_group.addButton(btn, idx)
            scope_layout.addWidget(btn)
        scope_layout.addStretch()
        layout.addLayout(scope_layout)

        # --- Table Widget ---
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Scope", "Action", "Shortcut"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)

        self.table.setItemDelegateForColumn(0, ScopeBadgeDelegate(self.table))
        self.table.setItemDelegateForColumn(2, KeycapBadgeDelegate(self.table))
        layout.addWidget(self.table)

        # --- Footer ---
        footer_layout = QHBoxLayout()
        self.status_label = QLabel("Showing shortcuts…")
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()

        hint_label = QLabel("Press Esc to close")
        hint_label.setStyleSheet("color: #888888; font-size: 11px;")
        footer_layout.addWidget(hint_label)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)
        layout.addLayout(footer_layout)

    def _set_scope(self, scope: str) -> None:
        self._active_scope = scope
        self._populate()

    def _populate(self) -> None:
        reg = get_registry()
        all_actions = reg.get_all()
        q = self.search_input.text().strip().lower()
        scope_filter = self._active_scope

        self.table.setRowCount(0)
        matching = 0

        for entry in all_actions:
            scope = entry.get("scope", "General")
            desc = entry.get("description", "")
            key = entry.get("current", "")

            # Scope filtering
            if scope_filter != "All" and scope.lower() != scope_filter.lower():
                continue

            # Text query filtering
            if q and (
                q not in desc.lower()
                and q not in key.lower()
                and q not in scope.lower()
            ):
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            item_scope = QTableWidgetItem(scope)
            item_desc = QTableWidgetItem(desc)
            item_key = QTableWidgetItem(key)

            item_scope.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_desc.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_key.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            self.table.setItem(row, 0, item_scope)
            self.table.setItem(row, 1, item_desc)
            self.table.setItem(row, 2, item_key)
            matching += 1

        total = len(all_actions)
        self.status_label.setText(f"Showing {matching} of {total} shortcuts")


__all__ = ["ShortcutDiscoveryDialog", "KeycapBadgeDelegate", "ScopeBadgeDelegate"]

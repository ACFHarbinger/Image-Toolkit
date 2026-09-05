"""
Command Palette / Quick Launcher Dialog (GUI/UX §2.16).

A floating, keyboard-first command launcher with real-time filtering,
categorized actions, tab navigation, and shortcut hints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)


@dataclass
class CommandItem:
    """A single executable action or route in the command palette."""
    id: str
    title: str
    category: str  # "Navigation", "Action", "Tool", "View", "Setting"
    callback: Callable[[], None]
    shortcut: Optional[str] = None
    keywords: Optional[Sequence[str]] = None


class CommandItemDelegate(QStyledItemDelegate):
    """Renders command palette entries with title, category badge, and shortcut keycap."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background
        is_selected = option.state & QStyleOptionViewItem.StateFlag.State_Selected
        is_dark = option.palette.window().color().lightness() < 128

        if is_selected:
            bg_color = QColor(88, 101, 242, 60) if is_dark else QColor(88, 101, 242, 40)
            painter.fillRect(option.rect, bg_color)
            # Left selection accent bar
            accent_bar = QPainterPath()
            accent_bar.addRoundedRect(option.rect.x() + 2, option.rect.y() + 4, 3, option.rect.height() - 8, 1.5, 1.5)
            painter.fillPath(accent_bar, QColor("#5865f2"))

        item_data: Optional[CommandItem] = index.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            painter.restore()
            return

        rect = option.rect
        y_mid = rect.center().y()

        # Category Badge
        badge_w = 74
        badge_h = 20
        badge_x = rect.x() + 12
        badge_y = y_mid - badge_h // 2

        cat_colors = {
            "Navigation": QColor(94, 129, 172),
            "Action": QColor(163, 190, 140),
            "Tool": QColor(208, 135, 112),
            "View": QColor(180, 142, 173),
            "Setting": QColor(235, 203, 139),
        }
        color = cat_colors.get(item_data.category, QColor(136, 192, 208))

        cat_path = QPainterPath()
        cat_path.addRoundedRect(badge_x, badge_y, badge_w, badge_h, 4, 4)
        painter.fillPath(cat_path, QColor(color.red(), color.green(), color.blue(), 40))
        painter.setPen(color)
        font_cat = QFont(painter.font())
        font_cat.setPointSize(max(7, font_cat.pointSize() - 2))
        font_cat.setBold(True)
        painter.setFont(font_cat)
        painter.drawText(badge_x, badge_y, badge_w, badge_h, Qt.AlignmentFlag.AlignCenter, item_data.category)

        # Title
        title_x = badge_x + badge_w + 12
        title_w = rect.width() - badge_w - 30 - (90 if item_data.shortcut else 0)
        painter.setPen(QColor(236, 239, 244) if is_dark else QColor(46, 52, 64))
        font_title = QFont(painter.font())
        font_title.setPointSize(max(9, font_title.pointSize() + 1))
        font_title.setBold(is_selected)
        painter.setFont(font_title)
        painter.drawText(
            title_x,
            rect.y(),
            title_w,
            rect.height(),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            item_data.title,
        )

        # Shortcut keycap
        if item_data.shortcut:
            key_text = item_data.shortcut
            text_w = painter.fontMetrics().horizontalAdvance(key_text)
            key_w = max(32, text_w + 12)
            key_h = 20
            key_x = rect.right() - key_w - 12
            key_y = y_mid - key_h // 2

            key_path = QPainterPath()
            key_path.addRoundedRect(key_x, key_y, key_w, key_h, 3, 3)
            key_bg = QColor(48, 52, 64) if is_dark else QColor(225, 229, 235)
            key_border = QColor(76, 86, 106) if is_dark else QColor(190, 196, 206)
            painter.fillPath(key_path, key_bg)
            painter.setPen(key_border)
            painter.drawPath(key_path)

            painter.setPen(QColor(216, 222, 233) if is_dark else QColor(76, 86, 106))
            font_key = QFont(painter.font())
            font_key.setPointSize(max(8, font_key.pointSize() - 1))
            painter.setFont(font_key)
            painter.drawText(key_x, key_y, key_w, key_h, Qt.AlignmentFlag.AlignCenter, key_text)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return option.rect.size().expandedTo(QSize(400, 36))


class CommandPaletteDialog(QDialog):
    """Floating quick-launcher modal palette."""

    def __init__(self, commands: Sequence[CommandItem], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.commands = list(commands)
        self.resize(560, 380)
        self.setMinimumWidth(480)

        self._init_ui()
        self._populate("")

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a command or search tabs…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._populate)
        self.search_input.returnPressed.connect(self._activate_current)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Command List
        self.list_widget = QListWidget()
        self.list_widget.setItemDelegate(CommandItemDelegate(self.list_widget))
        self.list_widget.itemActivated.connect(self._activate_item)
        self.list_widget.itemDoubleClicked.connect(self._activate_item)
        layout.addWidget(self.list_widget)

        # Footer
        footer = QHBoxLayout()
        self.status_label = QLabel("Showing commands…")
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        footer.addWidget(self.status_label)
        footer.addStretch()

        hint = QLabel("↑/↓ Navigate • ↵ Execute • Esc Close")
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        footer.addWidget(hint)
        layout.addLayout(footer)

    def _populate(self, text: str) -> None:
        q = text.strip().lower()
        self.list_widget.clear()

        matches: list[CommandItem] = []
        for cmd in self.commands:
            if not q:
                matches.append(cmd)
                continue

            # Query matching
            if (
                q in cmd.title.lower()
                or q in cmd.category.lower()
                or (cmd.shortcut and q in cmd.shortcut.lower())
                or (cmd.keywords and any(q in kw.lower() for kw in cmd.keywords))
            ):
                matches.append(cmd)

        for cmd in matches:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            item.setSizeHint(QSize(400, 36))
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

        self.status_label.setText(f"{len(matches)} of {len(self.commands)} commands")

    def _activate_current(self) -> None:
        current_item = self.list_widget.currentItem()
        if current_item:
            self._activate_item(current_item)

    def _activate_item(self, item: QListWidgetItem) -> None:
        cmd: Optional[CommandItem] = item.data(Qt.ItemDataRole.UserRole)
        if cmd and cmd.callback:
            self.accept()
            cmd.callback()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Down:
            curr = self.list_widget.currentRow()
            if curr < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(curr + 1)
            event.accept()
        elif event.key() == Qt.Key.Key_Up:
            curr = self.list_widget.currentRow()
            if curr > 0:
                self.list_widget.setCurrentRow(curr - 1)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
        else:
            super().keyPressEvent(event)


__all__ = ["CommandItem", "CommandPaletteDialog", "CommandItemDelegate"]

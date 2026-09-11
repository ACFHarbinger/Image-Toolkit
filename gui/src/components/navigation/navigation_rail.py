"""Vertical Navigation Rail for the experimental runtime shell (§2.36, #536)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui.src.modules.catalog import ModuleCatalog
from gui.src.modules.descriptor import ModuleCategory
from gui.src.theming.theme_api import color, qss

CATEGORY_ICONS: dict[ModuleCategory, str] = {
    ModuleCategory.SYSTEM: "⚙️",
    ModuleCategory.LIBRARY: "📚",
    ModuleCategory.WEB: "🌐",
    ModuleCategory.DEEP_LEARNING: "⚡",
    ModuleCategory.STITCHING: "✂️",
    ModuleCategory.MANGA: "🎨",
    ModuleCategory.EDITOR: "🖌️",
    ModuleCategory.DEVELOPER: "🛠️",
}


class NavigationRailWidget(QWidget):
    """Left vertical navigation rail with collapsible category drawer.

    Category selection only repaints the drawer. It never activates a module —
    activation is an explicit user click or shell ``activate_module`` call.
    """

    module_selected = Signal(str)  # module_id

    def __init__(self, catalog: ModuleCatalog, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.active_category: Optional[ModuleCategory] = None
        self.active_module_id: Optional[str] = None
        self._drawer_expanded: bool = True
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("navigation_rail")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.icon_rail = QWidget()
        self.icon_rail.setObjectName("icon_rail")
        self.icon_rail.setFixedWidth(56)
        rail_layout = QVBoxLayout(self.icon_rail)
        rail_layout.setContentsMargins(4, 8, 4, 8)
        rail_layout.setSpacing(6)

        self.cat_group = QButtonGroup(self)
        self.cat_buttons: dict[ModuleCategory, QToolButton] = {}

        for cat in self.catalog.categories():
            btn = QToolButton()
            btn.setText(CATEGORY_ICONS.get(cat, "📦"))
            btn.setCheckable(True)
            btn.setFixedSize(48, 44)
            btn.setToolTip(cat.value)
            btn.setObjectName(f"rail_cat_{cat.name.lower()}")
            btn.clicked.connect(lambda _=False, c=cat: self.select_category(c))
            self.cat_group.addButton(btn)
            self.cat_buttons[cat] = btn
            rail_layout.addWidget(btn)

        rail_layout.addStretch()

        self.toggle_btn = QToolButton()
        self.toggle_btn.setText("◀" if self._drawer_expanded else "▶")
        self.toggle_btn.setFixedSize(48, 32)
        self.toggle_btn.setToolTip("Toggle Navigation Drawer (Ctrl+B)")
        self.toggle_btn.clicked.connect(self.toggle_drawer)
        rail_layout.addWidget(self.toggle_btn)

        layout.addWidget(self.icon_rail)

        self.drawer_widget = QWidget()
        self.drawer_widget.setObjectName("rail_drawer")
        self.drawer_widget.setFixedWidth(200)
        self.drawer_layout = QVBoxLayout(self.drawer_widget)
        self.drawer_layout.setContentsMargins(8, 8, 8, 8)
        self.drawer_layout.setSpacing(4)

        self.drawer_header = QLabel("")
        self.drawer_header.setObjectName("drawer_header")
        self.drawer_header.setStyleSheet(qss("nav_drawer_header"))
        self.drawer_layout.addWidget(self.drawer_header)

        self.module_scroll = QScrollArea()
        self.module_scroll.setWidgetResizable(True)
        self.module_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.module_container = QWidget()
        self.module_list_layout = QVBoxLayout(self.module_container)
        self.module_list_layout.setContentsMargins(0, 0, 0, 0)
        self.module_list_layout.setSpacing(2)
        self.module_scroll.setWidget(self.module_container)
        self.drawer_layout.addWidget(self.module_scroll)

        layout.addWidget(self.drawer_widget)

        cats = self.catalog.categories()
        if cats:
            self.select_category(cats[0])

    def toggle_drawer(self) -> None:
        self._drawer_expanded = not self._drawer_expanded
        self.drawer_widget.setVisible(self._drawer_expanded)
        self.toggle_btn.setText("◀" if self._drawer_expanded else "▶")

    def apply_category_accents(self, overrides: dict[str, str]) -> None:
        """Apply category-specific accent overrides (§2.41, #518)."""
        self._category_accent_overrides = {k.lower(): v for k, v in overrides.items()}
        for cat, btn in self.cat_buttons.items():
            cat_key = cat.name.lower()
            if cat_key in self._category_accent_overrides:
                accent = self._category_accent_overrides[cat_key]
                btn.setStyleSheet(
                    qss("nav_category_checked", ACCENT=accent)
                )
        if self.active_category:
            self.select_category(self.active_category)

    def select_category(self, category: ModuleCategory) -> None:
        """Paint the drawer for *category* without activating any module."""
        self.active_category = category
        if category in self.cat_buttons:
            self.cat_buttons[category].setChecked(True)

        jp_text = {
            ModuleCategory.SYSTEM: "システム",
            ModuleCategory.LIBRARY: "ライブラリ",
            ModuleCategory.WEB: "ウェブ",
            ModuleCategory.DEEP_LEARNING: "深層学習",
            ModuleCategory.STITCHING: "ステッチ",
            ModuleCategory.MANGA: "マンガ",
            ModuleCategory.EDITOR: "エディタ",
            ModuleCategory.DEVELOPER: "開発ツール",
        }.get(category, "")
        cat_key = category.name.lower()
        accent = getattr(self, "_category_accent_overrides", {}).get(cat_key, color("accent"))
        self.drawer_header.setStyleSheet(
            qss("nav_drawer_header_accent", ACCENT=accent)
        )
        self.drawer_header.setText(f"{category.value.upper()}\n{jp_text}" if jp_text else category.value.upper())

        while self.module_list_layout.count():
            item = self.module_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for mod in self.catalog.navigable_by_category(category):
            btn = QPushButton(mod.title)
            btn.setObjectName(f"module_btn_{mod.module_id}")
            btn.setCheckable(True)
            btn.setStyleSheet(qss("nav_module_btn"))
            if mod.module_id == self.active_module_id:
                btn.setChecked(True)
            btn.clicked.connect(lambda _=False, m=mod.module_id: self._on_module_clicked(m))
            self.module_list_layout.addWidget(btn)

        self.module_list_layout.addStretch()

    def _on_module_clicked(self, module_id: str) -> None:
        self.active_module_id = module_id
        for i in range(self.module_list_layout.count()):
            item = self.module_list_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, QPushButton):
                widget.setChecked(widget.objectName() == f"module_btn_{module_id}")
        self.module_selected.emit(module_id)

    def set_active_module(self, module_id: str) -> None:
        """Sync rail highlight to an already-activated module (no re-emit)."""
        mod = self.catalog.get(module_id)
        if mod is None:
            return
        if mod.category != self.active_category:
            self.select_category(mod.category)
        self.active_module_id = module_id
        for i in range(self.module_list_layout.count()):
            item = self.module_list_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, QPushButton):
                widget.setChecked(widget.objectName() == f"module_btn_{module_id}")


__all__ = ["NavigationRailWidget"]

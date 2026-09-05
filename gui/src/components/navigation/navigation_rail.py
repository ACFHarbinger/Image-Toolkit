"""Vertical Navigation Rail component for modern creative suite layout (§2.36, #513)."""

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

CATEGORY_ICONS: dict[ModuleCategory, str] = {
    ModuleCategory.SYSTEM: "⚙️",
    ModuleCategory.LIBRARY: "📚",
    ModuleCategory.WEB: "🌐",
    ModuleCategory.DEEP_LEARNING: "⚡",
    ModuleCategory.STITCHING: "✂️",
    ModuleCategory.MANGA: "🎨",
    ModuleCategory.EDITOR: "🖌️",
}


class NavigationRailWidget(QWidget):
    """Left vertical navigation rail with collapsible category drawer."""

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

        # 1. Left Icon Rail (slim vertical strip)
        self.icon_rail = QWidget()
        self.icon_rail.setObjectName("icon_rail")
        self.icon_rail.setFixedWidth(56)
        rail_layout = QVBoxLayout(self.icon_rail)
        rail_layout.setContentsMargins(4, 8, 4, 8)
        rail_layout.setSpacing(6)

        # Category Buttons
        self.cat_group = QButtonGroup(self)
        self.cat_buttons: dict[ModuleCategory, QToolButton] = {}

        for cat in self.catalog.categories():
            icon_char = CATEGORY_ICONS.get(cat, "📦")
            btn = QToolButton()
            btn.setText(icon_char)
            btn.setCheckable(True)
            btn.setFixedSize(48, 44)
            btn.setToolTip(f"{cat.value}")
            btn.setObjectName(f"rail_cat_{cat.name.lower()}")
            btn.clicked.connect(lambda _=False, c=cat: self.select_category(c))
            self.cat_group.addButton(btn)
            self.cat_buttons[cat] = btn
            rail_layout.addWidget(btn)

        rail_layout.addStretch()

        # Drawer toggle button at bottom
        self.toggle_btn = QToolButton()
        self.toggle_btn.setText("◀" if self._drawer_expanded else "▶")
        self.toggle_btn.setFixedSize(48, 32)
        self.toggle_btn.setToolTip("Toggle Navigation Drawer (Ctrl+B)")
        self.toggle_btn.clicked.connect(self.toggle_drawer)
        rail_layout.addWidget(self.toggle_btn)

        layout.addWidget(self.icon_rail)

        # 2. Drawer Panel (tool list for active category)
        self.drawer_widget = QWidget()
        self.drawer_widget.setObjectName("rail_drawer")
        self.drawer_widget.setFixedWidth(200)
        self.drawer_layout = QVBoxLayout(self.drawer_widget)
        self.drawer_layout.setContentsMargins(8, 8, 8, 8)
        self.drawer_layout.setSpacing(4)

        self.drawer_header = QLabel("")
        self.drawer_header.setObjectName("drawer_header")
        self.drawer_header.setStyleSheet("font-weight: bold; font-size: 11pt; padding: 4px;")
        self.drawer_layout.addWidget(self.drawer_header)

        # Scrollable module button list
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

        # Initial selection
        cats = self.catalog.categories()
        if cats:
            self.select_category(cats[0])

    def toggle_drawer(self) -> None:
        self._drawer_expanded = not self._drawer_expanded
        self.toggle_btn.setText("◀" if self._drawer_expanded else "▶")
        start_w = 0 if self._drawer_expanded else 200
        end_w = 200 if self._drawer_expanded else 0
        try:
            from gui.src.styles.motion_kit import MotionKit
            MotionKit.slide_width(self.drawer_widget, start_w, end_w, duration_ms=MotionKit.BASE_MS)
        except Exception:
            self.drawer_widget.setVisible(self._drawer_expanded)

    def select_category(self, category: ModuleCategory) -> None:
        self.active_category = category
        if category in self.cat_buttons:
            self.cat_buttons[category].setChecked(True)

        jp_text = {
            ModuleCategory.SYSTEM: "システム",
            ModuleCategory.LIBRARY: "ライブラリ",
            ModuleCategory.WEB: "ウェブ統合",
            ModuleCategory.DEEP_LEARNING: "深層学習",
            ModuleCategory.STITCHING: "画像結合",
            ModuleCategory.MANGA: "マンガ",
            ModuleCategory.EDITOR: "エディタ",
        }.get(category, "")
        self.drawer_header.setText(f"{category.value.upper()}\n{jp_text}" if jp_text else category.value.upper())

        # Clear existing tool buttons
        while self.module_list_layout.count():
            item = self.module_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Add buttons for modules in this category
        modules = self.catalog.navigable_by_category(category)
        for mod in modules:
            sub = f" // {mod.japanese_subtext}" if getattr(mod, 'japanese_subtext', None) else ""
            btn = QPushButton(f"{mod.title}{sub}")
            btn.setObjectName(f"module_btn_{mod.module_id}")
            btn.setCheckable(True)
            btn.setStyleSheet("text-align: left; padding: 6px 10px; font-size: 9pt;")
            if mod.module_id == self.active_module_id:
                btn.setChecked(True)
            btn.clicked.connect(lambda _=False, m=mod.module_id: self._on_module_clicked(m))
            self.module_list_layout.addWidget(btn)

        self.module_list_layout.addStretch()

        # Select first module if active not in this category
        if modules and (not self.active_module_id or self.catalog.require(self.active_module_id).category != category):
            self._on_module_clicked(modules[0].module_id)

    def _on_module_clicked(self, module_id: str) -> None:
        self.active_module_id = module_id
        for i in range(self.module_list_layout.count()):
            item = self.module_list_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, QPushButton):
                widget.setChecked(widget.objectName() == f"module_btn_{module_id}")
        self.module_selected.emit(module_id)

    def set_active_module(self, module_id: str) -> None:
        mod = self.catalog.get(module_id)
        if mod:
            if mod.category != self.active_category:
                self.select_category(mod.category)
            self._on_module_clicked(module_id)


__all__ = ["NavigationRailWidget"]

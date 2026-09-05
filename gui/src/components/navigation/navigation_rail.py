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

    # Width of icon_rail (56) + drawer_widget (200) -- the collapsible
    # "sidebar" content, not counting the always-visible toggle strip.
    _SIDEBAR_WIDTH = 256

    def __init__(self, catalog: ModuleCatalog, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.active_category: Optional[ModuleCategory] = None
        self.active_module_id: Optional[str] = None
        # Whether the *drawer* (per-category module list) is expanded --
        # independent of _sidebar_expanded below.
        self._drawer_expanded: bool = True
        # Whether the whole sidebar (icon rail + drawer) is expanded at all.
        # Collapsing this gives the tab content the full window width; only
        # the slim always-visible toggle strip remains, so it stays
        # re-expandable without needing the keyboard shortcut.
        self._sidebar_expanded: bool = True
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("navigation_rail")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 0. Always-visible toggle strip -- lives outside the collapsible
        # sidebar_content so it stays clickable/discoverable when collapsed.
        self.toggle_strip = QWidget()
        self.toggle_strip.setObjectName("rail_toggle_strip")
        self.toggle_strip.setFixedWidth(22)
        strip_layout = QVBoxLayout(self.toggle_strip)
        strip_layout.setContentsMargins(2, 8, 2, 8)
        strip_layout.setSpacing(0)

        self.toggle_btn = QToolButton()
        self.toggle_btn.setText("◀")
        self.toggle_btn.setFixedSize(18, 32)
        self.toggle_btn.setToolTip("Collapse/Expand Sidebar (Ctrl+B)")
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        strip_layout.addWidget(self.toggle_btn)
        strip_layout.addStretch()
        layout.addWidget(self.toggle_strip)

        # 1. Collapsible sidebar content (icon rail + drawer together).
        self.sidebar_content = QWidget()
        self.sidebar_content.setObjectName("rail_sidebar_content")
        sidebar_layout = QHBoxLayout(self.sidebar_content)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # 1a. Left Icon Rail (slim vertical strip)
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
        self.drawer_toggle_btn = QToolButton()
        self.drawer_toggle_btn.setText("◀" if self._drawer_expanded else "▶")
        self.drawer_toggle_btn.setFixedSize(48, 32)
        self.drawer_toggle_btn.setToolTip("Toggle Navigation Drawer")
        self.drawer_toggle_btn.clicked.connect(self.toggle_drawer)
        rail_layout.addWidget(self.drawer_toggle_btn)

        sidebar_layout.addWidget(self.icon_rail)

        # 1b. Drawer Panel (tool list for active category)
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

        sidebar_layout.addWidget(self.drawer_widget)
        layout.addWidget(self.sidebar_content)

        # Initial selection
        cats = self.catalog.categories()
        if cats:
            self.select_category(cats[0])

    def toggle_sidebar(self) -> None:
        """Collapse/expand the entire sidebar (icon rail + drawer), giving
        the active tab's content the full window width when collapsed. The
        toggle strip itself stays visible so it's always re-expandable."""
        self._sidebar_expanded = not self._sidebar_expanded
        self.toggle_btn.setText("◀" if self._sidebar_expanded else "▶")
        # self._sidebar_expanded now holds the *target* state -- animate
        # toward it (0 -> full width when expanding, full width -> 0 when
        # collapsing).
        end_w = self._SIDEBAR_WIDTH if self._sidebar_expanded else 0
        start_w = 0 if self._sidebar_expanded else self._SIDEBAR_WIDTH
        try:
            from gui.src.styles.motion_kit import MotionKit
            MotionKit.slide_width(self.sidebar_content, start_w, end_w, duration_ms=MotionKit.BASE_MS)
        except Exception:
            self.sidebar_content.setVisible(self._sidebar_expanded)

    def toggle_drawer(self) -> None:
        self._drawer_expanded = not self._drawer_expanded
        self.drawer_toggle_btn.setText("◀" if self._drawer_expanded else "▶")
        start_w = 0 if self._drawer_expanded else 200
        end_w = 200 if self._drawer_expanded else 0
        try:
            from gui.src.styles.motion_kit import MotionKit
            MotionKit.slide_width(self.drawer_widget, start_w, end_w, duration_ms=MotionKit.BASE_MS)
        except Exception:
            self.drawer_widget.setVisible(self._drawer_expanded)

    def apply_category_accents(self, overrides: dict[str, str]) -> None:
        """Apply category-specific accent overrides (§2.41, #518)."""
        self._category_accent_overrides = {k.lower(): v for k, v in overrides.items()}
        for cat, btn in self.cat_buttons.items():
            cat_key = cat.name.lower()
            if cat_key in self._category_accent_overrides:
                accent = self._category_accent_overrides[cat_key]
                btn.setStyleSheet(f"QToolButton:checked {{ border-left: 3px solid {accent}; background: rgba(255,255,255,0.08); }}")
        if self.active_category:
            self.select_category(self.active_category)

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
        cat_key = category.name.lower()
        accent = getattr(self, "_category_accent_overrides", {}).get(cat_key, "#00bcd4")
        self.drawer_header.setStyleSheet(f"font-weight: bold; font-size: 11pt; padding: 4px; color: {accent};")
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

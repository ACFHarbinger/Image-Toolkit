"""Top Segmented Ribbon navigation component for compact/laptop view (§2.36, #513)."""

from __future__ import annotations

import contextlib
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from gui.src.modules.catalog import ModuleCatalog
from gui.src.modules.descriptor import ModuleCategory


class TopSegmentedRibbonWidget(QWidget):
    """Top segmented pill navigation with category dropdown."""

    module_selected = Signal(str)  # module_id

    def __init__(self, catalog: ModuleCatalog, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.active_category: Optional[ModuleCategory] = None
        self.active_module_id: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("segmented_ribbon")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        # Category Selector
        cat_label = QLabel("Hub // ハブ:")
        cat_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(cat_label)

        self.cat_combo = QComboBox()
        for cat in self.catalog.categories():
            self.cat_combo.addItem(cat.value, cat)
        self.cat_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.cat_combo.currentIndexChanged.connect(self._on_cat_combo_changed)
        layout.addWidget(self.cat_combo)

        # Separator line / label
        sep = QLabel("|")
        sep.setStyleSheet("color: #555;")
        layout.addWidget(sep)

        # Scrollable pill strip
        self.pills_container = QWidget()
        self.pills_layout = QHBoxLayout(self.pills_container)
        self.pills_layout.setContentsMargins(0, 0, 0, 0)
        self.pills_layout.setSpacing(4)

        layout.addWidget(self.pills_container)
        layout.addStretch()

        # Initialize
        cats = self.catalog.categories()
        if cats:
            self._populate_category(cats[0])

    def _on_cat_combo_changed(self, idx: int) -> None:
        cat = self.cat_combo.itemData(idx)
        if isinstance(cat, str):
            with contextlib.suppress(ValueError):
                cat = ModuleCategory(cat)
        if isinstance(cat, ModuleCategory):
            self._populate_category(cat)

    def apply_category_accents(self, overrides: dict[str, str]) -> None:
        """Apply category-specific accent overrides (§2.41, #518)."""
        self._category_accent_overrides = {k.lower(): v for k, v in overrides.items()}
        if self.active_category:
            self._populate_category(self.active_category)

    def _populate_category(self, category: ModuleCategory) -> None:
        self.active_category = category
        while self.pills_layout.count():
            item = self.pills_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cat_key = category.name.lower()
        accent = getattr(self, "_category_accent_overrides", {}).get(cat_key, "#00bcd4")
        modules = self.catalog.navigable_by_category(category)
        for mod in modules:
            btn = QPushButton(mod.title)
            btn.setObjectName(f"ribbon_btn_{mod.module_id}")
            btn.setCheckable(True)
            btn.setStyleSheet(
                f"QPushButton {{ padding: 6px 14px; border-radius: 12px; font-weight: 500; }}"
                f"QPushButton:checked {{ background: {accent}; color: white; }}"
            )
            if mod.module_id == self.active_module_id:
                btn.setChecked(True)
            btn.clicked.connect(lambda _=False, m=mod.module_id: self._on_pill_clicked(m))
            self.pills_layout.addWidget(btn)

        if modules and (not self.active_module_id or self.catalog.require(self.active_module_id).category != category):
            self._on_pill_clicked(modules[0].module_id)

    def _on_pill_clicked(self, module_id: str) -> None:
        self.active_module_id = module_id
        for i in range(self.pills_layout.count()):
            item = self.pills_layout.itemAt(i)
            w = item.widget()
            if isinstance(w, QPushButton):
                w.setChecked(w.objectName() == f"ribbon_btn_{module_id}")
        self.module_selected.emit(module_id)

    def set_active_module(self, module_id: str) -> None:
        mod = self.catalog.get(module_id)
        if mod:
            if mod.category != self.active_category:
                for i in range(self.cat_combo.count()):
                    if self.cat_combo.itemData(i) == mod.category:
                        self.cat_combo.setCurrentIndex(i)
                        break
            self._on_pill_clicked(module_id)


__all__ = ["TopSegmentedRibbonWidget"]

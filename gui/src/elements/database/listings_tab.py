from backend.src.core.vault_manager import VaultManager  # noqa: F401
from PySide6.QtWidgets import (
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...constants.listings import (
    ENTITIES_FILE,  # noqa: F401
    LISTINGS_FILE,  # noqa: F401
)

# ---------------------------------------------------------------------------
from .series_listings_subtab import SeriesListingsSubTab
from .entity_listings_subtab import EntityListingsSubTab


class ListingsTab(QWidget):
    """Media tracking and entity listing tab."""

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager

        # ---- Root layout ----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(
            "QTabWidget::pane { border: none; background: #2c2f33; }"
            "QTabBar::tab { background: #23272a; color: #888; padding: 10px 20px; font-weight: bold; border-top-left-radius: 6px; border-top-right-radius: 6px; }"
            "QTabBar::tab:selected { background: #2c2f33; color: #00bcd4; border-bottom: 2px solid #00bcd4; }"
        )

        self.series_listings = SeriesListingsSubTab(vault_manager=vault_manager)
        self.entity_listings = EntityListingsSubTab(vault_manager=vault_manager)

        # Bidirectional cross-sync: saving/deleting on one side reloads the other
        self.series_listings.entities_changed.connect(
            self.entity_listings._on_external_reload
        )
        self.entity_listings.listings_changed.connect(
            self.series_listings._on_external_reload
        )

        self.tab_widget.addTab(self.series_listings, "🎬 Series Listings")
        self.tab_widget.addTab(self.entity_listings, "👥 Entity Listings")
        layout.addWidget(self.tab_widget)

    # DB.8a cross-tab navigation: MainWindow assigns this post-construction
    # (mirrors search_tab_ref/merge_tab_ref in _tab_registry.py); forwarded
    # to series_listings, which forwards it to its detail panel.
    @property
    def main_window_ref(self):
        return self.series_listings.main_window_ref

    @main_window_ref.setter
    def main_window_ref(self, value):
        self.series_listings.main_window_ref = value

    def collect(self) -> dict:
        return {"active_subtab_index": self.tab_widget.currentIndex()}

    def set_config(self, config: dict):
        idx = config.get("active_subtab_index", 0)
        if isinstance(idx, int) and 0 <= idx < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(idx)

    def get_default_config(self) -> dict:
        return {"active_subtab_index": 0}

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTabWidget,
)

from backend.src.core.vault_manager import VaultManager  # noqa: F401
from ...constants.listings import (
    LISTINGS_FILE,  # noqa: F401
    ENTITIES_FILE,  # noqa: F401
)


# ---------------------------------------------------------------------------

from .common.content_listings_subtab import ContentListingsSubTab
from .common.entity_listings_subtab import EntityListingsSubTab


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

        self.content_listings = ContentListingsSubTab(vault_manager=vault_manager)
        self.entity_listings = EntityListingsSubTab(vault_manager=vault_manager)

        # Bidirectional cross-sync: saving/deleting on one side reloads the other
        self.content_listings.entities_changed.connect(
            self.entity_listings._on_external_reload
        )
        self.entity_listings.listings_changed.connect(
            self.content_listings._on_external_reload
        )

        self.tab_widget.addTab(self.content_listings, "🎬 Content Listings")
        self.tab_widget.addTab(self.entity_listings, "👥 Entity Listings")
        layout.addWidget(self.tab_widget)

    def collect(self) -> dict:
        return {"active_subtab_index": self.tab_widget.currentIndex()}

    def set_config(self, config: dict):
        idx = config.get("active_subtab_index", 0)
        if isinstance(idx, int) and 0 <= idx < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(idx)

    def get_default_config(self) -> dict:
        return {"active_subtab_index": 0}

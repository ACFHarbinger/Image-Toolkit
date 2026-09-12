"""Tests for listings subtab mixin-to-composition migration (ui-arch-23, #544)."""

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.elements.database.display.common.listing_gallery_base import (
    ListingGalleryBase,
)
from gui.src.tabs.database.listings_subtab import EntityListingsSubTab, SeriesListingsSubTab
from gui.src.tabs.database.listings_subtab._backup_sync import (
    ListingsBackupSyncController,
)
from gui.src.tabs.database.listings_subtab._entity_card_actions import (
    EntityListingsCardActionsController,
)
from gui.src.tabs.database.listings_subtab._entity_directory_import import (
    EntityListingsDirectoryImportController,
)
from gui.src.tabs.database.listings_subtab._entity_filters import (
    EntityListingsFiltersController,
)
from gui.src.tabs.database.listings_subtab._entity_gallery import (
    EntityListingsGalleryController,
)
from gui.src.tabs.database.listings_subtab._entity_persistence import (
    EntityListingsPersistenceController,
)
from gui.src.tabs.database.listings_subtab._entity_semantic_search import (
    EntityListingsSemanticController,
)
from gui.src.tabs.database.listings_subtab._entity_ui_builder import (
    EntityListingsUIBuilder,
)
from gui.src.tabs.database.listings_subtab._series_card_actions import (
    SeriesListingsCardActionsController,
)
from gui.src.tabs.database.listings_subtab._series_directory_import import (
    SeriesListingsDirectoryImportController,
)
from gui.src.tabs.database.listings_subtab._series_filters import (
    SeriesListingsFiltersController,
)
from gui.src.tabs.database.listings_subtab._series_gallery import (
    SeriesListingsGalleryController,
)
from gui.src.tabs.database.listings_subtab._series_persistence import (
    SeriesListingsPersistenceController,
)
from gui.src.tabs.database.listings_subtab._series_recommendation import (
    SeriesListingsRecommendationController,
)
from gui.src.tabs.database.listings_subtab._series_semantic_search import (
    SeriesListingsSemanticController,
)
from gui.src.tabs.database.listings_subtab._series_ui_builder import (
    SeriesListingsUIBuilder,
)

pytestmark = pytest.mark.gui


class TestEntityListingsComposition:
    def test_direct_bases_have_no_mixins(self, q_app):
        bases = EntityListingsSubTab.__bases__
        assert bases == (ListingGalleryBase,)
        for cls in bases:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(EntityListingsSubTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        tab = EntityListingsSubTab(vault_manager=None)
        assert isinstance(tab.ui_builder, EntityListingsUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.persistence, EntityListingsPersistenceController)
        assert isinstance(tab.gallery, EntityListingsGalleryController)
        assert isinstance(tab.card_actions, EntityListingsCardActionsController)
        assert isinstance(tab.filters, EntityListingsFiltersController)
        assert isinstance(tab.semantic, EntityListingsSemanticController)
        assert isinstance(tab.backup_sync, ListingsBackupSyncController)
        assert isinstance(tab.directory_import, EntityListingsDirectoryImportController)
        tab.close()

    def test_tab_bound_controller_attribute_proxy(self, q_app):
        tab = EntityListingsSubTab(vault_manager=None)
        tab.custom_test_attr = 42
        assert tab.gallery.custom_test_attr == 42
        tab.close()


class TestSeriesListingsComposition:
    def test_direct_bases_have_no_mixins(self, q_app):
        bases = SeriesListingsSubTab.__bases__
        assert bases == (ListingGalleryBase,)
        for cls in bases:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(SeriesListingsSubTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        tab = SeriesListingsSubTab(vault_manager=None)
        assert isinstance(tab.ui_builder, SeriesListingsUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.persistence, SeriesListingsPersistenceController)
        assert isinstance(tab.gallery, SeriesListingsGalleryController)
        assert isinstance(tab.card_actions, SeriesListingsCardActionsController)
        assert isinstance(tab.recommendation, SeriesListingsRecommendationController)
        assert isinstance(tab.filters, SeriesListingsFiltersController)
        assert isinstance(tab.semantic, SeriesListingsSemanticController)
        assert isinstance(tab.backup_sync, ListingsBackupSyncController)
        assert isinstance(tab.directory_import, SeriesListingsDirectoryImportController)
        tab.close()


def test_no_compat_mixin_aliases():
    """#544 closure: COMPAT mixin-name aliases must not remain (PR #609)."""
    import importlib
    import pkgutil

    pkg = importlib.import_module("gui.src.tabs.database.listings_subtab")
    leftover = []
    modules = [pkg]
    for info in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        modules.append(importlib.import_module(info.name))
    for mod in modules:
        leftover.extend(name for name in dir(mod) if name.endswith("Mixin") and not name.startswith("__"))
        leftover.extend(name for name in getattr(mod, "__all__", []) if str(name).endswith("Mixin"))
    assert leftover == []

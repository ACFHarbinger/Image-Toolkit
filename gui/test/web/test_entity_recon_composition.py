"""Tests for EntityReconTab mixin-to-composition migration (ui-arch-23, #544)."""

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QWidget

from gui.src.tabs.web.entity_recon_tab import EntityReconTab
from gui.src.tabs.web.entity_recon_tab._batch_builder import EntityReconBatchController
from gui.src.tabs.web.entity_recon_tab._config import EntityReconConfigController
from gui.src.tabs.web.entity_recon_tab._dataset_indexing import EntityReconDatasetController
from gui.src.tabs.web.entity_recon_tab._identity_resolution import EntityReconIdentityController
from gui.src.tabs.web.entity_recon_tab._library_link import EntityReconLibraryLinkController
from gui.src.tabs.web.entity_recon_tab._lifecycle import EntityReconLifecycleController
from gui.src.tabs.web.entity_recon_tab._provenance_export import EntityReconExportController
from gui.src.tabs.web.entity_recon_tab._source_image import EntityReconSourceController
from gui.src.tabs.web.entity_recon_tab._status_helpers import EntityReconStatusController
from gui.src.tabs.web.entity_recon_tab._ui_builder import EntityReconUIBuilder
from gui.src.tabs.web.entity_recon_tab._worker_plumbing import EntityReconWorkerController

pytestmark = pytest.mark.gui


class TestEntityReconComposition:
    def test_entity_recon_tab_direct_bases_have_no_mixins(self, q_app):
        bases = EntityReconTab.__bases__
        assert bases == (QWidget,)
        for cls in bases:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(EntityReconTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        tab = EntityReconTab()
        assert isinstance(tab.ui_builder, EntityReconUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.status_controller, EntityReconStatusController)
        assert tab.status_controller.tab is tab
        assert isinstance(tab.config_controller, EntityReconConfigController)
        assert tab.config_controller.tab is tab
        assert isinstance(tab.dataset_controller, EntityReconDatasetController)
        assert tab.dataset_controller.tab is tab
        assert isinstance(tab.source_controller, EntityReconSourceController)
        assert tab.source_controller.tab is tab
        assert isinstance(tab.identity_controller, EntityReconIdentityController)
        assert tab.identity_controller.tab is tab
        assert isinstance(tab.library_link_controller, EntityReconLibraryLinkController)
        assert tab.library_link_controller.tab is tab
        assert isinstance(tab.export_controller, EntityReconExportController)
        assert tab.export_controller.tab is tab
        assert isinstance(tab.batch_controller, EntityReconBatchController)
        assert tab.batch_controller.tab is tab
        assert isinstance(tab.worker_controller, EntityReconWorkerController)
        assert tab.worker_controller.tab is tab
        assert isinstance(tab.lifecycle_controller, EntityReconLifecycleController)
        assert tab.lifecycle_controller.tab is tab
        tab.close()

    def test_tab_bound_controller_attribute_proxy(self, q_app):
        tab = EntityReconTab()
        tab.custom_proxy_attr = "entity_recon_test"
        assert tab.config_controller.custom_proxy_attr == "entity_recon_test"
        tab.close()

    def test_close_event_and_cancel_loading(self, q_app):
        tab = EntityReconTab()
        tab.cancel_loading()
        event = QCloseEvent()
        tab.closeEvent(event)
        assert event.isAccepted()

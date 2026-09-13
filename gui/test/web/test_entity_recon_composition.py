"""Tests for EntityReconTab mixin-to-composition migration (ui-arch-23, #544)."""

import pytest
from backend.src.web.recon.config import EMBED_CLIP, EMBED_FACE, SCOPE_LOCAL, SCOPE_WEB
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

    def test_no_compat_mixin_aliases(self):
        """#544 closure: COMPAT mixin-name aliases must not remain (mirrors PR #609)."""
        import importlib
        import pkgutil

        pkg = importlib.import_module("gui.src.tabs.web.entity_recon_tab")
        leftover = []
        modules = [pkg]
        for info in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
            modules.append(importlib.import_module(info.name))
        for mod in modules:
            leftover.extend(name for name in dir(mod) if name.endswith("Mixin") and not name.startswith("__"))
            leftover.extend(name for name in getattr(mod, "__all__", []) if str(name).endswith("Mixin"))
        assert leftover == []


class TestEntityReconTabConfig:
    def test_config_facade_roundtrip(self, q_app):
        tab = EntityReconTab()
        cfg = tab.get_default_config()
        assert cfg == {
            "dataset_root": "",
            "embed_mode": EMBED_FACE,
            "search_scope": SCOPE_LOCAL,
            "batch_target_dir": "",
        }
        cfg["dataset_root"] = "/tmp/recon_dataset"
        cfg["embed_mode"] = EMBED_CLIP
        cfg["search_scope"] = SCOPE_WEB
        cfg["batch_target_dir"] = "/tmp/recon_target"
        tab.set_config(cfg)
        collected = tab.collect()
        assert collected["dataset_root"] == "/tmp/recon_dataset"
        assert collected["embed_mode"] == EMBED_CLIP
        assert collected["search_scope"] == SCOPE_WEB
        assert collected["batch_target_dir"] == "/tmp/recon_target"
        # The combo change handlers pushed the restored values onto the ReconConfig.
        assert tab._config.embed_mode == EMBED_CLIP
        assert tab._config.search_scope == SCOPE_WEB
        assert tab._config.privacy_mode is False
        tab.close()

    def test_set_config_ignores_unknown_values(self, q_app):
        tab = EntityReconTab()
        tab.set_config({"embed_mode": "nonexistent", "search_scope": None})
        assert tab.embed_combo.currentData() == EMBED_FACE
        assert tab.scope_combo.currentData() == SCOPE_LOCAL
        tab.close()

"""Tests for CBIRTrainTab mixin-to-composition migration (ui-arch-23, #544)."""

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.tabs.models.delta.cbir_train_tab import CBIRTrainTab
from gui.src.tabs.models.delta.cbir_train_tab._browsers import (
    CBIRTrainBrowsersController,
    _BrowsersMixin,
)
from gui.src.tabs.models.delta.cbir_train_tab._config import (
    CBIRTrainConfigController,
    _ConfigMixin,
)
from gui.src.tabs.models.delta.cbir_train_tab._index_builder import (
    CBIRTrainIndexController,
    _IndexBuilderMixin,
)
from gui.src.tabs.models.delta.cbir_train_tab._loss_toggle import (
    CBIRTrainLossToggleController,
    _LossToggleMixin,
)
from gui.src.tabs.models.delta.cbir_train_tab._telemetry_slots import (
    CBIRTrainTelemetryController,
    _TelemetrySlotsMixin,
)
from gui.src.tabs.models.delta.cbir_train_tab._training_worker import (
    CBIRTrainWorkerController,
    _TrainingWorkerMixin,
)
from gui.src.tabs.models.delta.cbir_train_tab._ui_builder import (
    CBIRTrainUIBuilder,
    _UIBuilderMixin,
)

pytestmark = pytest.mark.gui


class TestCBIRTrainComposition:
    def test_cbir_train_tab_direct_bases_have_no_mixins(self, q_app):
        bases = CBIRTrainTab.__bases__
        assert bases == (QWidget,)
        for cls in bases:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(CBIRTrainTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        tab = CBIRTrainTab()
        assert isinstance(tab.ui_builder, CBIRTrainUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.telemetry_controller, CBIRTrainTelemetryController)
        assert tab.telemetry_controller.tab is tab
        assert isinstance(tab.loss_controller, CBIRTrainLossToggleController)
        assert tab.loss_controller.tab is tab
        assert isinstance(tab.browsers_controller, CBIRTrainBrowsersController)
        assert tab.browsers_controller.tab is tab
        assert isinstance(tab.training_controller, CBIRTrainWorkerController)
        assert tab.training_controller.tab is tab
        assert isinstance(tab.index_controller, CBIRTrainIndexController)
        assert tab.index_controller.tab is tab
        assert isinstance(tab.config_controller, CBIRTrainConfigController)
        assert tab.config_controller.tab is tab
        tab.close()

    def test_compat_mixin_aliases(self):
        assert _BrowsersMixin is CBIRTrainBrowsersController
        assert _ConfigMixin is CBIRTrainConfigController
        assert _IndexBuilderMixin is CBIRTrainIndexController
        assert _LossToggleMixin is CBIRTrainLossToggleController
        assert _TelemetrySlotsMixin is CBIRTrainTelemetryController
        assert _TrainingWorkerMixin is CBIRTrainWorkerController
        assert _UIBuilderMixin is CBIRTrainUIBuilder

    def test_tab_bound_controller_attribute_proxy(self, q_app):
        tab = CBIRTrainTab()
        tab.custom_proxy_test = "cbir_test_value"
        assert tab.browsers_controller.custom_proxy_test == "cbir_test_value"
        tab.close()

    def test_config_facade_roundtrip(self, q_app):
        tab = CBIRTrainTab()
        cfg = tab.get_default_config()
        assert isinstance(cfg, dict)
        assert cfg["loss_fn"] == "infonce"
        cfg["output_dir"] = "/tmp/cbir_out_test"
        cfg["epochs"] = 42
        tab.set_config(cfg)
        collected = tab.collect()
        assert collected["output_dir"] == "/tmp/cbir_out_test"
        assert collected["epochs"] == 42
        tab.close()

    def test_loss_toggle(self, q_app):
        tab = CBIRTrainTab()
        # Initial InfoNCE
        assert tab._temperature.isEnabled()
        assert not tab._margin.isEnabled()

        # Switch to Triplet
        tab._loss_fn.setCurrentIndex(1)
        assert not tab._temperature.isEnabled()
        assert tab._margin.isEnabled()
        tab.close()

    def test_telemetry_signal_flow(self, q_app):
        tab = CBIRTrainTab()
        tab.sig_log.emit("Test log line")
        assert "Test log line" in tab._log_box.toPlainText()

        tab.sig_epoch.emit(3, {"recall_at_1": 0.85, "recall_at_5": 0.95, "recall_at_10": 0.99, "total": 0.1234})
        assert tab._epoch_progress.value() == 3
        assert "0.850" in tab._recall_label.text()
        tab.close()

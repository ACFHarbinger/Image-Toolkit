"""Tests for SamplerSubTab mixin-to-composition migration (ui-arch-23, #544)."""

import pytest

from gui.src.classes import AbstractClassTwoGalleries
from gui.src.tabs.core.sampler_subtab import SamplerSubTab
from gui.src.tabs.core.sampler_subtab._config import (
    SamplerConfigController,
    _ConfigMixin,
)
from gui.src.tabs.core.sampler_subtab._directory_browse import (
    SamplerDirectoryController,
    _DirectoryBrowseMixin,
)
from gui.src.tabs.core.sampler_subtab._gallery_cards import (
    SamplerGalleryCardsController,
    _GalleryCardsMixin,
)
from gui.src.tabs.core.sampler_subtab._lifecycle import (
    SamplerLifecycleController,
    _LifecycleMixin,
)
from gui.src.tabs.core.sampler_subtab._preview_context import (
    SamplerPreviewController,
    _PreviewContextMixin,
)
from gui.src.tabs.core.sampler_subtab._resample_worker import (
    SamplerWorkerController,
    _ResampleWorkerMixin,
)
from gui.src.tabs.core.sampler_subtab._scale_mode import (
    SamplerScaleModeController,
    _ScaleModeMixin,
)
from gui.src.tabs.core.sampler_subtab._ui_builder import (
    SamplerUIBuilder,
    _UIBuilderMixin,
)

pytestmark = pytest.mark.gui


class TestSamplerComposition:
    def test_sampler_tab_direct_bases_have_no_mixins(self, q_app):
        bases = SamplerSubTab.__bases__
        assert bases == (AbstractClassTwoGalleries,)
        for cls in bases:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(SamplerSubTab, AbstractClassTwoGalleries)

    def test_controllers_are_composed(self, q_app):
        tab = SamplerSubTab()
        assert isinstance(tab.ui_builder, SamplerUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.scale_mode_controller, SamplerScaleModeController)
        assert tab.scale_mode_controller.tab is tab
        assert isinstance(tab.directory_controller, SamplerDirectoryController)
        assert tab.directory_controller.tab is tab
        assert isinstance(tab.gallery_cards_controller, SamplerGalleryCardsController)
        assert tab.gallery_cards_controller.tab is tab
        assert isinstance(tab.preview_controller, SamplerPreviewController)
        assert tab.preview_controller.tab is tab
        assert isinstance(tab.worker_controller, SamplerWorkerController)
        assert tab.worker_controller.tab is tab
        assert isinstance(tab.config_controller, SamplerConfigController)
        assert tab.config_controller.tab is tab
        assert isinstance(tab.lifecycle_controller, SamplerLifecycleController)
        assert tab.lifecycle_controller.tab is tab
        tab.close()

    def test_compat_mixin_aliases(self):
        assert _ConfigMixin is SamplerConfigController
        assert _DirectoryBrowseMixin is SamplerDirectoryController
        assert _GalleryCardsMixin is SamplerGalleryCardsController
        assert _LifecycleMixin is SamplerLifecycleController
        assert _PreviewContextMixin is SamplerPreviewController
        assert _ResampleWorkerMixin is SamplerWorkerController
        assert _ScaleModeMixin is SamplerScaleModeController
        assert _UIBuilderMixin is SamplerUIBuilder

    def test_tab_bound_controller_attribute_proxy(self, q_app):
        tab = SamplerSubTab()
        tab.custom_sampler_test = "sampler_val_42"
        assert tab.directory_controller.custom_sampler_test == "sampler_val_42"
        tab.close()

    def test_config_facade_roundtrip(self, q_app):
        tab = SamplerSubTab()
        cfg = tab.get_default_config()
        assert isinstance(cfg, dict)
        assert cfg["scale_factor"] == 2.0
        cfg["scale_factor"] = 4.0
        cfg["output_filename_prefix"] = "prefix_test_"
        tab.set_config(cfg)
        assert tab.scale_factor_spin.value() == 4.0
        assert tab.prefix_edit.text() == "prefix_test_"
        tab.close()

    def test_scale_mode_toggle(self, q_app):
        tab = SamplerSubTab()
        assert not tab._factor_widget.isHidden()
        assert tab._dims_widget.isHidden()

        tab._radio_dims.setChecked(True)
        assert tab._factor_widget.isHidden()
        assert not tab._dims_widget.isHidden()
        tab.close()

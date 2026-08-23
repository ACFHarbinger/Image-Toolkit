"""Tests for AspAdvancedConfigDialog (M2 20-flag primary profile & 73-flag advanced schema)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QSpinBox

from gui.src.components.dialogs.asp_advanced_config_dialog import (
    PRIMARY_CURATED_KEYS,
    AspAdvancedConfigDialog,
    get_active_schema,
)

pytestmark = pytest.mark.gui


class TestAspAdvancedConfigDialog:
    def test_schema_loaded_and_complete(self):
        schema = get_active_schema()
        assert len(schema) >= 65
        for key in PRIMARY_CURATED_KEYS:
            assert key in schema

    def test_dialog_creation_and_widget_mapping(self, q_app):
        dlg = AspAdvancedConfigDialog()
        assert len(dlg.widgets) == len(dlg.schema)
        assert dlg.tab_widget.count() == 2

    def test_primary_curated_keys_in_primary_tab(self, q_app):
        dlg = AspAdvancedConfigDialog()
        for key in PRIMARY_CURATED_KEYS:
            assert key in dlg.widgets
            widget = dlg.widgets[key]
            entry = dlg.schema[key]
            expected_type = entry[0]

            if isinstance(expected_type, int) and entry[1] == 0 and entry[2] == 1:
                assert isinstance(widget, QCheckBox)
            elif isinstance(expected_type, float):
                assert isinstance(widget, QDoubleSpinBox)
            elif isinstance(expected_type, int):
                assert isinstance(widget, QSpinBox)

    def test_preset_profile_switching(self, q_app):
        dlg = AspAdvancedConfigDialog()
        dlg._on_profile_preset_changed("Default (Laptop Balanced)")
        cfg = dlg.get_config()
        assert cfg.get("ASP_HOLD_THRESHOLD") == 0.05
        assert cfg.get("ASP_LOFTR_BG_RATIO_MIN") == 0.15

        dlg._on_profile_preset_changed("Desktop Quality")
        cfg_hq = dlg.get_config()
        assert cfg_hq.get("ASP_HOLD_THRESHOLD") == 0.02
        assert cfg_hq.get("ASP_USE_SAM2") == 1
        assert cfg_hq.get("ASP_FLOW_ENGINE") == "searaft"

    def test_filter_parameters(self, q_app):
        dlg = AspAdvancedConfigDialog()
        dlg._filter_parameters("SAM2")
        assert not dlg.widgets["ASP_USE_SAM2"].isHidden()
        assert dlg.widgets["ASP_HOLD_THRESHOLD"].isHidden()


    def test_load_and_extract_custom_config(self, q_app):
        custom = {
            "ASP_HOLD_THRESHOLD": 0.08,
            "ASP_USE_SAM2": 1,
            "ASP_SP_SOFT_PX": 25,
            "ASP_FLOW_ENGINE": "searaft",
        }
        dlg = AspAdvancedConfigDialog(initial_config=custom)
        cfg = dlg.get_config()
        assert cfg["ASP_HOLD_THRESHOLD"] == pytest.approx(0.08)
        assert cfg["ASP_USE_SAM2"] == 1
        assert cfg["ASP_SP_SOFT_PX"] == 25
        assert cfg["ASP_FLOW_ENGINE"] == "searaft"

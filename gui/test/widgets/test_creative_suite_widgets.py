"""Tests for ToggleSwitch and SegmentedControl (§2.37, §2.39)."""

from __future__ import annotations

import pytest
from gui.src.components.widgets.segmented_control import SegmentedControl
from gui.src.components.widgets.toggle_switch import ToggleSwitch

pytestmark = pytest.mark.gui


class TestCreativeSuiteWidgets:
    def test_toggle_switch_state(self, q_app):
        switch = ToggleSwitch()
        assert not switch.isChecked()

        toggled_states = []
        switch.toggled.connect(toggled_states.append)

        switch.setChecked(True)
        assert switch.isChecked()
        assert switch.thumb_position > 3.0

        switch.click()
        assert not switch.isChecked()

    def test_segmented_control_selection(self, q_app):
        items = [("grid", "Grid View"), ("masonry", "Masonry"), ("list", "List View")]
        seg = SegmentedControl(items)

        assert seg.selected_key == "grid"

        selected = []
        seg.selection_changed.connect(selected.append)

        seg.set_selected("masonry")
        assert seg.selected_key == "masonry"
        assert selected == ["masonry"]

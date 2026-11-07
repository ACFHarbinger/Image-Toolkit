"""Smart Extract method dropdown stays usable (2026-11-07)."""

import pytest

from gui.src.tabs.core.extractor_tab import VideoExtractorSubTab

pytestmark = pytest.mark.gui


def test_method_combo_is_clickable_and_a_pick_enables_smart_extract(q_app):
    tab = VideoExtractorSubTab()
    combo, check = tab.combo_smart_method, tab.check_smart_extract
    assert combo.isEnabled() and not check.isChecked()
    combo.activated.emit(2)
    assert check.isChecked()
    check.setChecked(False)
    assert combo.isEnabled()
    tab.close()


def test_restoring_a_method_does_not_enable_smart_extract(q_app):
    tab = VideoExtractorSubTab()
    tab.combo_smart_method.setCurrentText("scene (0.4)")
    assert not tab.check_smart_extract.isChecked()
    tab.close()

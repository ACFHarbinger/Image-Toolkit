"""ui-arch-25/#547: MonitorDisplaySubTab must run every mixin __init__ on its MRO."""

from __future__ import annotations

import pytest

from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab import MonitorDisplaySubTab, _lifecycle

pytestmark = pytest.mark.gui


def test_mixin_init_on_the_mro_is_reached(q_app, monkeypatch):
    calls: list[str] = []

    def _recording_init(self, *args, **kwargs):
        calls.append("lifecycle")
        super(_lifecycle._LifecycleMixin, self).__init__(*args, **kwargs)

    monkeypatch.setattr(_lifecycle._LifecycleMixin, "__init__", _recording_init, raising=False)
    tab = MonitorDisplaySubTab()
    try:
        assert calls == ["lifecycle"], "a mixin __init__ added to the MRO was skipped"
    finally:
        tab.close()

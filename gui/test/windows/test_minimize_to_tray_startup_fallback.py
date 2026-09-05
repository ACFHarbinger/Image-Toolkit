from unittest.mock import patch

import pytest

pytestmark = pytest.mark.gui


def _make_startup_prefs_host():
    from gui.src.windows.main._startup_prefs import _StartupPrefsMixin
    from gui.src.windows.main._tray import _TrayMixin
    from PySide6.QtWidgets import QComboBox, QWidget

    class Host(_StartupPrefsMixin, _TrayMixin, QWidget):
        def __init__(self):
            QWidget.__init__(self)
            self._minimize_to_tray = False
            self._tray_icon = None
            self.all_tabs = {}
            self.command_combo = QComboBox()
            # A non-empty dict -- _apply_startup_preferences() early-returns
            # on a falsy `prefs` dict, so an empty {} would never even reach
            # the minimize_to_tray fallback logic under test.
            self.cached_creds = {"preferences": {"thumbnail_size": 180}}

    return Host()


def test_apply_startup_preferences_falls_back_to_appsettings_minimize_to_tray(q_app):
    """Regression: vault preferences lack minimize_to_tray/close_to_tray (or
    lag a stale snapshot), but the separate QSettings-backed store has it
    True -- the setting must still actually apply, not silently reset."""
    host = _make_startup_prefs_host()
    assert host._minimize_to_tray is False

    with patch(
        "gui.src.windows.settings.app_settings.AppSettings.minimize_to_tray",
        return_value=True,
    ):
        host._apply_startup_preferences()

    assert host._minimize_to_tray is True, (
        "minimize_to_tray must fall back to AppSettings.minimize_to_tray() "
        "the same way settings_window.py's checkbox-init already does"
    )


def test_apply_tray_preference_does_not_require_legacy_tab_preferences(q_app):
    """The experimental shell does not run legacy tab preference setup."""
    host = _make_startup_prefs_host()
    host.cached_creds = {"preferences": {}}

    with patch(
        "gui.src.windows.settings.app_settings.AppSettings.minimize_to_tray",
        return_value=True,
    ):
        host._apply_tray_preference(host.cached_creds["preferences"])

    assert host._minimize_to_tray is True


def test_apply_startup_preferences_respects_vault_value_when_appsettings_false(q_app):
    host = _make_startup_prefs_host()
    host.cached_creds = {"preferences": {"minimize_to_tray": True}}

    with patch(
        "gui.src.windows.settings.app_settings.AppSettings.minimize_to_tray",
        return_value=False,
    ):
        host._apply_startup_preferences()

    assert host._minimize_to_tray is True

"""Tests for gui/src/utils/shortcut_manager.py -- multi-custom-shortcut
data model (GUI/UX §2.29 KDE-style shortcuts editor).
"""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence

from gui.src.utils.manager import shortcut_manager


@pytest.fixture(autouse=True)
def _isolated_keybindings(tmp_path, monkeypatch):
    path = tmp_path / "keybindings.json"
    monkeypatch.setattr(shortcut_manager, "_KEYBINDINGS_PATH", path)
    yield path


def _make_key_event(key, modifiers=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QKeyEvent.Type.KeyPress, key, modifiers)


class TestDefaults:
    def test_fresh_registry_has_default_enabled_and_no_custom(self):
        reg = shortcut_manager.ShortcutRegistry()
        assert reg.is_default_enabled("gallery.select_all") is True
        assert reg.get_custom_keys("gallery.select_all") == []
        assert reg.get_key("gallery.select_all") == "Ctrl+A"
        assert reg.is_default("gallery.select_all") is True

    def test_general_save_tab_config_registered(self):
        ids = {e["id"] for e in shortcut_manager.SHORTCUT_REGISTRY}
        assert "general.save_tab_config" in ids
        entry = next(e for e in shortcut_manager.SHORTCUT_REGISTRY if e["id"] == "general.save_tab_config")
        assert entry["default"] == "Ctrl+S"
        assert entry["scope"] == "General"

    def test_stitch_actions_are_configurable(self):
        entries = {entry["id"]: entry for entry in shortcut_manager.SHORTCUT_REGISTRY}
        assert {"stitch.run", "stitch.cancel", "stitch.compute_matches", "stitch.generate_scans_comparison"} <= set(entries)
        assert entries["stitch.run"]["default"] == "Ctrl+Return"
        assert entries["stitch.run"]["scope"] == "Stitch"

    def test_convert_and_merge_actions_are_configurable(self):
        entries = {entry["id"]: entry for entry in shortcut_manager.SHORTCUT_REGISTRY}
        assert {"convert.run_all", "convert.run_selected", "convert.cancel"} <= set(entries)
        assert {"merge.run", "merge.cancel"} <= set(entries)
        assert entries["convert.run_all"]["scope"] == "Convert"
        assert entries["merge.run"]["scope"] == "Merge"


class TestSaveLoad:
    def test_save_and_reload_round_trips(self, tmp_path):
        reg = shortcut_manager.ShortcutRegistry()
        reg.save({
            "gallery.select_all": {"default_enabled": False, "custom": ["Ctrl+Shift+A", "Meta+A"]},
        })
        reg2 = shortcut_manager.ShortcutRegistry()
        assert reg2.is_default_enabled("gallery.select_all") is False
        assert reg2.get_custom_keys("gallery.select_all") == ["Ctrl+Shift+A", "Meta+A"]

    def test_reset_clears_state_and_deletes_file(self, tmp_path):
        reg = shortcut_manager.ShortcutRegistry()
        reg.save({"gallery.select_all": {"default_enabled": False, "custom": ["Meta+A"]}})
        assert shortcut_manager._KEYBINDINGS_PATH.exists()
        reg.reset()
        assert not shortcut_manager._KEYBINDINGS_PATH.exists()
        assert reg.is_default_enabled("gallery.select_all") is True
        assert reg.get_custom_keys("gallery.select_all") == []

    def test_backward_compat_old_flat_string_format(self, tmp_path):
        # Pre-multi-shortcut format: {"action_id": "KeyStr"}
        shortcut_manager._KEYBINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        shortcut_manager._KEYBINDINGS_PATH.write_text(json.dumps({"gallery.select_all": "Meta+A"}))
        reg = shortcut_manager.ShortcutRegistry()
        # Old format fully replaced the default -- default off, old value becomes the one custom key.
        assert reg.is_default_enabled("gallery.select_all") is False
        assert reg.get_custom_keys("gallery.select_all") == ["Meta+A"]

    def test_malformed_json_falls_back_to_defaults(self, tmp_path):
        shortcut_manager._KEYBINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        shortcut_manager._KEYBINDINGS_PATH.write_text("{not valid json")
        reg = shortcut_manager.ShortcutRegistry()
        assert reg.is_default_enabled("gallery.select_all") is True
        assert reg.get_custom_keys("gallery.select_all") == []


class TestGetAllKeys:
    def test_default_enabled_plus_customs(self):
        reg = shortcut_manager.ShortcutRegistry()
        reg.save({"gallery.select_all": {"default_enabled": True, "custom": ["Meta+A"]}})
        assert reg.get_all_keys("gallery.select_all") == ["Ctrl+A", "Meta+A"]

    def test_default_disabled_only_customs(self):
        reg = shortcut_manager.ShortcutRegistry()
        reg.save({"gallery.select_all": {"default_enabled": False, "custom": ["Meta+A", "Meta+B"]}})
        assert reg.get_all_keys("gallery.select_all") == ["Meta+A", "Meta+B"]

    def test_default_disabled_no_customs_is_empty(self):
        reg = shortcut_manager.ShortcutRegistry()
        reg.save({"gallery.select_all": {"default_enabled": False, "custom": []}})
        assert reg.get_all_keys("gallery.select_all") == []
        assert reg.get_key("gallery.select_all") == ""


class TestMatches:
    def test_matches_default_binding(self):
        reg = shortcut_manager.ShortcutRegistry()
        event = _make_key_event(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        assert reg.matches(event, "gallery.select_all") is True

    def test_matches_custom_binding(self):
        reg = shortcut_manager.ShortcutRegistry()
        reg.save({"gallery.select_all": {"default_enabled": True, "custom": ["Meta+A"]}})
        event = _make_key_event(Qt.Key.Key_A, Qt.KeyboardModifier.MetaModifier)
        assert reg.matches(event, "gallery.select_all") is True

    def test_no_match_when_default_disabled_and_no_custom_matches(self):
        reg = shortcut_manager.ShortcutRegistry()
        reg.save({"gallery.select_all": {"default_enabled": False, "custom": ["Meta+A"]}})
        event = _make_key_event(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        assert reg.matches(event, "gallery.select_all") is False

    def test_get_key_sequence_matches_get_key(self):
        reg = shortcut_manager.ShortcutRegistry()
        assert reg.get_key_sequence("preview.zoom_in") == QKeySequence(reg.get_key("preview.zoom_in"))


class TestGetAll:
    def test_current_field_lists_all_active_keys(self):
        reg = shortcut_manager.ShortcutRegistry()
        reg.save({"gallery.select_all": {"default_enabled": True, "custom": ["Meta+A"]}})
        entries = {e["id"]: e for e in reg.get_all()}
        assert entries["gallery.select_all"]["current"] == "Ctrl+A, Meta+A"

    def test_current_field_none_when_no_active_keys(self):
        reg = shortcut_manager.ShortcutRegistry()
        reg.save({"gallery.select_all": {"default_enabled": False, "custom": []}})
        entries = {e["id"]: e for e in reg.get_all()}
        assert entries["gallery.select_all"]["current"] == "(none)"


class TestSingleton:
    def test_get_registry_returns_same_instance(self):
        shortcut_manager._registry = None
        reg1 = shortcut_manager.get_registry()
        reg2 = shortcut_manager.get_registry()
        assert reg1 is reg2
        shortcut_manager._registry = None  # don't leak into other test modules

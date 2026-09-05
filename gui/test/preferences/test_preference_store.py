"""gui/test/preferences/test_preference_store.py
=============================================
Unit tests for PreferenceStore contract and adapters (§1.1, #525).
"""

from __future__ import annotations

import pytest
from gui.src.preferences import (
    MemoryPreferenceAdapter,
    PreferenceDefinition,
    PreferenceScope,
    PreferenceStore,
    PrefKeys,
    VaultPreferenceAdapter,
)


class TestPreferenceDefinitions:
    """Verify typed preference schema and coercion rules."""

    def test_bool_coercion(self):
        defn = PreferenceDefinition("test/bool", PreferenceScope.DEVICE, False, bool)
        assert defn.cast(True) is True
        assert defn.cast(False) is False
        assert defn.cast("true") is True
        assert defn.cast("TRUE") is True
        assert defn.cast("1") is True
        assert defn.cast("false") is False
        assert defn.cast("0") is False
        assert defn.cast(None) is False

    def test_int_coercion(self):
        defn = PreferenceDefinition("test/int", PreferenceScope.ACCOUNT, 100, int)
        assert defn.cast(42) == 42
        assert defn.cast("42") == 42
        assert defn.cast("invalid") == 100
        assert defn.cast(None) == 100

    def test_list_coercion(self):
        defn = PreferenceDefinition("test/list", PreferenceScope.ACCOUNT, ["a"], list)
        assert defn.cast(["x", "y"]) == ["x", "y"]
        assert defn.cast(("x", "y")) == ["x", "y"]
        assert defn.cast("single") == ["single"]
        assert defn.cast("") == []
        assert defn.cast(None) == ["a"]

    def test_validation(self):
        defn = PreferenceDefinition(
            "test/valid",
            PreferenceScope.DEVICE,
            10,
            int,
            validator=lambda x: 0 <= x <= 100,
        )
        assert defn.validate(50) is True
        assert defn.validate(150) is False


class TestMemoryPreferenceAdapter:
    """Verify thread-safe in-memory adapter operations."""

    def test_crud_operations(self):
        adapter = MemoryPreferenceAdapter({"initial/key": 1})
        assert adapter.get("initial/key") == 1
        assert adapter.contains("initial/key") is True

        adapter.set("new/key", "value")
        assert adapter.get("new/key") == "value"
        assert set(adapter.all_keys()) == {"initial/key", "new/key"}

        adapter.remove("initial/key")
        assert adapter.contains("initial/key") is False
        assert adapter.get("initial/key", "fallback") == "fallback"

        adapter.clear()
        assert adapter.all_keys() == []


class TestVaultPreferenceAdapter:
    """Verify user profile vault adapter and guest session rules."""

    def test_preferences_prefix_normalization(self):
        creds = {
            "theme": "nord",
            "preferences": {
                "recursive_scan": True,
                "mal_fetch_method": "official_api",
            },
        }
        adapter = VaultPreferenceAdapter(creds)

        assert adapter.get("theme") == "nord"
        assert adapter.get("preferences/recursive_scan") is True
        assert adapter.get("recursive_scan") is True
        assert adapter.get("preferences/mal_fetch_method") == "official_api"

    def test_set_writes_to_correct_section(self):
        creds = {"preferences": {}}
        adapter = VaultPreferenceAdapter(creds)

        adapter.set("preferences/recursive_scan", False)
        adapter.set("theme", "light")

        snapshot = adapter.get_credentials()
        assert snapshot["preferences"]["recursive_scan"] is False
        assert snapshot["theme"] == "light"

    def test_guest_mode_status(self):
        class MockVault:
            is_guest = True

        adapter = VaultPreferenceAdapter({}, vault_manager=MockVault())
        assert adapter.is_guest is True


class TestPreferenceStore:
    """Verify canonical PreferenceStore routing and single-source semantics."""

    @pytest.fixture
    def isolated_store(self):
        """Create an isolated store backed entirely by memory adapters for tests."""
        store = PreferenceStore(lazy_adapters=True)
        store.register_adapter(PreferenceScope.DEVICE, MemoryPreferenceAdapter())
        store.register_adapter(PreferenceScope.ACCOUNT, MemoryPreferenceAdapter())
        store.register_adapter(PreferenceScope.SESSION, MemoryPreferenceAdapter())
        return store

    def test_scope_routing_for_known_definitions(self, isolated_store):
        # DEVICE scope key
        isolated_store.set(PrefKeys.MINIMIZE_TO_TRAY, True)
        assert isolated_store.get(PrefKeys.MINIMIZE_TO_TRAY) is True
        # Verify it was stored in the DEVICE adapter, not ACCOUNT or SESSION
        assert isolated_store.get_adapter(PreferenceScope.DEVICE).contains(PrefKeys.MINIMIZE_TO_TRAY.key)
        assert not isolated_store.get_adapter(PreferenceScope.ACCOUNT).contains(PrefKeys.MINIMIZE_TO_TRAY.key)

        # ACCOUNT scope key
        isolated_store.set(PrefKeys.RECURSIVE_SCAN, False)
        assert isolated_store.get(PrefKeys.RECURSIVE_SCAN) is False
        assert isolated_store.get_adapter(PreferenceScope.ACCOUNT).contains(PrefKeys.RECURSIVE_SCAN.key)
        assert not isolated_store.get_adapter(PreferenceScope.DEVICE).contains(PrefKeys.RECURSIVE_SCAN.key)

    def test_session_namespace_routing(self, isolated_store):
        isolated_store.set("session/ExtractorTab/last_dir", "/tmp/images")
        assert isolated_store.get("session/ExtractorTab/last_dir") == "/tmp/images"
        assert isolated_store.get_adapter(PreferenceScope.SESSION).contains("session/ExtractorTab/last_dir")

        isolated_store.set("splitters/main_horizontal", b"bytes123")
        assert isolated_store.get("splitters/main_horizontal") == b"bytes123"
        assert isolated_store.get_adapter(PreferenceScope.SESSION).contains("splitters/main_horizontal")

    def test_default_fallbacks(self, isolated_store):
        assert isolated_store.get(PrefKeys.RECURSIVE_SCAN) is True
        assert isolated_store.get(PrefKeys.MAL_FETCH_METHOD) == "jikan"
        assert isolated_store.get(PrefKeys.MINIMIZE_TO_TRAY) is False
        assert isolated_store.get("unknown/custom_key", "default_val") == "default_val"

    def test_subscriber_notifications(self, isolated_store):
        events = []

        def on_change(key, value, scope):
            events.append((key, value, scope))

        unsubscribe = isolated_store.subscribe(on_change)
        isolated_store.set(PrefKeys.THEME, "light")

        assert len(events) == 1
        assert events[0] == (PrefKeys.THEME.key, "light", PreferenceScope.ACCOUNT)

        unsubscribe()
        isolated_store.set(PrefKeys.THEME, "dark")
        assert len(events) == 1

    def test_validation_failure(self, isolated_store):
        constrained_key = PreferenceDefinition(
            "test/bounded",
            PreferenceScope.DEVICE,
            5,
            int,
            validator=lambda x: 0 <= x <= 10,
        )
        isolated_store.register_definition(constrained_key)

        isolated_store.set(constrained_key, 8)
        assert isolated_store.get(constrained_key) == 8

        with pytest.raises(ValueError):
            isolated_store.set(constrained_key, 99)

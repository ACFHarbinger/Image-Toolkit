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

    def test_set_persists_through_attached_vault_manager(self):
        """#525 cross-review: a write must survive restart, not just be
        visible to an immediate in-process read. Reproduces the real
        VaultManager.save_data(json_string) contract with a fake disk.
        """
        import json

        class FakeVaultManager:
            is_guest = False

            def __init__(self):
                self.disk: str | None = None

            def save_data(self, json_string: str) -> None:
                self.disk = json_string

        vault = FakeVaultManager()
        adapter = VaultPreferenceAdapter(
            {"preferences": {}}, vault_manager=vault, account_name="alice"
        )

        adapter.set("preferences/recursive_scan", False)

        assert vault.disk is not None
        persisted = json.loads(vault.disk)
        assert persisted["preferences"]["recursive_scan"] is False

        # Simulate a restart: a fresh adapter loading only what actually
        # reached the vault's disk representation.
        rehydrated = VaultPreferenceAdapter(json.loads(vault.disk))
        assert rehydrated.get("preferences/recursive_scan") is False

    def test_set_in_guest_mode_never_touches_disk(self):
        """Guest sessions must stay volatile-in-memory (matches
        VaultManager.save_data's own is_guest branch); FakeVaultManager
        mirrors that contract rather than writing to `disk`.
        """

        class FakeGuestVaultManager:
            is_guest = True

            def __init__(self):
                self.disk_writes = 0
                self._memory: dict = {}

            def save_data(self, json_string: str) -> None:
                import json as _json

                self._memory = _json.loads(json_string)
                # Guest mode: never increments disk_writes / touches real disk.

        vault = FakeGuestVaultManager()
        adapter = VaultPreferenceAdapter({}, vault_manager=vault)

        adapter.set("preferences/recursive_scan", False)

        assert vault.disk_writes == 0
        assert vault._memory["preferences"]["recursive_scan"] is False

    def test_account_switch_replaces_credentials_not_merges(self):
        """set_credentials() (the attach_vault_credentials() path) must
        fully replace the adapter's view -- switching accounts must not
        leak the previous account's values.
        """
        adapter = VaultPreferenceAdapter(
            {"preferences": {"recursive_scan": False}, "account_name": "alice"}
        )
        assert adapter.get("preferences/recursive_scan") is False

        adapter.set_credentials(
            {"preferences": {"recursive_scan": True}, "account_name": "bob"},
            account_name="bob",
        )
        assert adapter.get("preferences/recursive_scan") is True
        assert adapter.get("account_name") == "bob"


class TestPreferenceStoreVaultWiring:
    """#525 cross-review: PreferenceStore.attach_vault_credentials() must
    actually be reachable and make ACCOUNT-scope reads/writes resolve
    against the real session, not silently no-op against an empty adapter.
    """

    def test_attach_vault_credentials_wires_account_scope(self):
        import json

        class FakeVaultManager:
            is_guest = False

            def __init__(self):
                self.disk: str | None = None

            def save_data(self, json_string: str) -> None:
                self.disk = json_string

        store = PreferenceStore(lazy_adapters=True)
        store.register_adapter(PreferenceScope.DEVICE, MemoryPreferenceAdapter())
        store.register_adapter(PreferenceScope.SESSION, MemoryPreferenceAdapter())

        # Before attachment: ACCOUNT reads see only the built-in default.
        assert store.get(PrefKeys.RECURSIVE_SCAN) is True

        vault = FakeVaultManager()
        creds = {"preferences": {"recursive_scan": False}}
        store.attach_vault_credentials(creds, vault, account_name="alice")

        assert store.get(PrefKeys.RECURSIVE_SCAN) is False

        store.set(PrefKeys.MAL_FETCH_METHOD, "scrape")
        assert vault.disk is not None
        assert json.loads(vault.disk)["preferences"]["mal_fetch_method"] == "scrape"

    def test_reattach_on_account_switch_does_not_leak_previous_account(self):
        store = PreferenceStore(lazy_adapters=True)
        store.register_adapter(PreferenceScope.DEVICE, MemoryPreferenceAdapter())
        store.register_adapter(PreferenceScope.SESSION, MemoryPreferenceAdapter())

        store.attach_vault_credentials(
            {"preferences": {"recursive_scan": False}}, None, account_name="alice"
        )
        assert store.get(PrefKeys.RECURSIVE_SCAN) is False

        # Switch accounts (e.g. logout/login as a different user).
        store.attach_vault_credentials(
            {"preferences": {"recursive_scan": True}}, None, account_name="bob"
        )
        assert store.get(PrefKeys.RECURSIVE_SCAN) is True


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

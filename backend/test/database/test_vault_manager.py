import json
from pathlib import Path

import pytest
from src.core.vault_manager import (
    CryptographyLibNotBuiltError,
    VaultManager,
    _CryptoAPI,
)

from backend.src import constants as udef
from backend.test.conftest import repo_root

FIXTURE_DIR = Path(repo_root) / "backend" / "test" / "data" / "crypto_fixture"
FIXTURE_KEYSTORE = str(FIXTURE_DIR / "java_generated.p12")
FIXTURE_VAULT = str(FIXTURE_DIR / "java_generated.vault")
FIXTURE_KEY_BIN = FIXTURE_DIR / "java_generated_key.bin"
FIXTURE_PASSWORD = "fixture-pass"
FIXTURE_ALIAS = "fixture-alias"
FIXTURE_PAYLOAD = '{"fixture": true, "payload": "hello-from-java"}'


class VaultManagerTest:
    @pytest.fixture
    def vm(self):
        with VaultManager() as manager:
            yield manager

    def test_java_fixture_keystore_and_vault_compat(self, vm):
        """A keystore/vault written by the (removed) JVM module must be
        readable by the native library, with the exact key bytes and payload."""
        vm.load_keystore(FIXTURE_KEYSTORE, FIXTURE_PASSWORD)
        assert vm.contains_alias(FIXTURE_ALIAS)
        assert not vm.contains_alias("no-such-alias")

        vm.get_secret_key(FIXTURE_ALIAS, FIXTURE_PASSWORD)
        assert vm.secret_key == FIXTURE_KEY_BIN.read_bytes()

        vm.init_vault(FIXTURE_VAULT)
        assert vm.load_data() == FIXTURE_PAYLOAD

    def test_full_roundtrip(self, vm, tmp_path):
        keystore = str(tmp_path / "roundtrip.p12")
        vault = str(tmp_path / "roundtrip.vault")

        vm.create_key_if_missing("rt-alias", keystore, "rt-pass")
        assert vm.contains_alias("rt-alias")
        assert vm.keystore == keystore

        vm.get_secret_key("rt-alias", "rt-pass")
        assert isinstance(vm.secret_key, bytes) and len(vm.secret_key) == 32

        vm.init_vault(vault)
        payload = '{"note": "round-trip", "n": 42}'
        vm.save_data(payload)
        assert vm.load_data() == payload

    def test_create_key_if_missing_is_idempotent(self, vm, tmp_path):
        keystore = str(tmp_path / "idem.p12")
        vm.create_key_if_missing("idem-alias", keystore, "pass")
        vm.create_key_if_missing("idem-alias", keystore, "pass")
        vm.get_secret_key("idem-alias", "pass")
        assert len(vm.secret_key) == 32

    def test_wrong_keystore_password(self, vm):
        with pytest.raises(ValueError, match="Failed to load keystore"):
            vm.load_keystore(FIXTURE_KEYSTORE, "wrong-password")

    def test_missing_keystore_file(self, vm):
        with pytest.raises(FileNotFoundError):
            vm.load_keystore("/nonexistent/keystore.p12", "pass")

    def test_error_getting_key_before_load_keystore(self, vm):
        with pytest.raises(ValueError, match="Keystore is not loaded"):
            vm.get_secret_key("alias", "keypass")

    def test_error_non_existent_key_alias(self, vm):
        vm.load_keystore(FIXTURE_KEYSTORE, FIXTURE_PASSWORD)
        with pytest.raises(ValueError, match="No secret key found"):
            vm.get_secret_key("non_existent_key", FIXTURE_PASSWORD)

    def test_error_saving_data_before_init_vault(self, vm):
        vm.load_keystore(FIXTURE_KEYSTORE, FIXTURE_PASSWORD)
        vm.get_secret_key(FIXTURE_ALIAS, FIXTURE_PASSWORD)
        with pytest.raises(ValueError, match="Vault is not initialized"):
            vm.save_data("{}")

    def test_missing_vault_file_returns_empty_json(self, vm, tmp_path):
        vm.load_keystore(FIXTURE_KEYSTORE, FIXTURE_PASSWORD)
        vm.get_secret_key(FIXTURE_ALIAS, FIXTURE_PASSWORD)
        vm.init_vault(str(tmp_path / "does-not-exist.vault"))
        assert vm.load_data() == "{}"

    def test_wrong_key_fails_to_decrypt(self, vm, tmp_path):
        keystore = str(tmp_path / "k.p12")
        vault = str(tmp_path / "v.vault")
        vm.create_key_if_missing("a", keystore, "pass")
        vm.get_secret_key("a", "pass")
        vm.init_vault(vault)
        vm.save_data('{"secret": true}')

        vm2 = VaultManager()
        try:
            vm2.create_key_if_missing("b", str(tmp_path / "k2.p12"), "pass2")
            vm2.get_secret_key("b", "pass2")
            vm2.init_vault(vault)
            with pytest.raises(RuntimeError, match="Failed to load data"):
                vm2.load_data()
        finally:
            vm2.shutdown()

    def test_missing_library_raises_distinct_error(self, monkeypatch):
        monkeypatch.setattr(udef, "CRYPTO_LIB_FILE", "/nonexistent/libitk_crypto.so")
        monkeypatch.setattr(_CryptoAPI, "_lib", None)
        with pytest.raises(CryptographyLibNotBuiltError):
            VaultManager()

    def test_shutdown_and_shutdown_jvm_are_noops(self, vm):
        vm.shutdown()
        vm.shutdown_jvm()

    def test_guest_vault_volatile(self):
        guest = VaultManager.create_guest_vault("guest-user")
        guest.save_data('{"theme": "light"}')
        assert json.loads(guest.load_data())["theme"] == "light"
        guest.save_account_credentials("guest-user", "pw")
        creds = guest.load_account_credentials()
        assert creds["account_name"] == "guest-user"
        guest.shutdown()
        guest.shutdown_jvm()

    def test_update_account_password_preserves_data(self, monkeypatch, tmp_path):
        keystore = str(tmp_path / "upd.p12")
        vault = str(tmp_path / "upd.vault")
        monkeypatch.setattr(udef, "KEYSTORE_FILE", keystore)
        monkeypatch.setattr(udef, "VAULT_FILE", vault)

        with VaultManager() as manager:
            manager.create_key_if_missing(udef.KEY_ALIAS, keystore, "old-pass")
            manager.get_secret_key(udef.KEY_ALIAS, "old-pass")
            manager.init_vault(vault)
            manager.save_account_credentials("user", "old-pass")
            manager.save_data('{"note": "keep me"}')

            manager.update_account_password("user", "new-pass")

            loaded = manager.load_data()
            assert '"keep me"' in loaded
            creds = manager.load_account_credentials()
            assert creds["account_name"] == "user"
            assert creds["hashed_password"] != manager.PEPPER  # sanity: is a hash

        # Old password must no longer open the new keystore/vault
        with VaultManager() as manager2:
            with pytest.raises(ValueError, match="Failed to load keystore"):
                manager2.load_keystore(keystore, "old-pass")
            manager2.load_keystore(keystore, "new-pass")
            manager2.get_secret_key(udef.KEY_ALIAS, "new-pass")
            manager2.init_vault(vault)
            assert '"keep me"' in manager2.load_data()

import pytest

from unittest.mock import MagicMock
from conftest import MockKeyStoreManager
from src.core.vault_manager import VaultManager as JavaVaultManager


class JavaVaultManagerTest:
    @pytest.fixture(autouse=True)
    def reset_mocks(self):
        MockKeyStoreManager.keystore = MagicMock()
        MockKeyStoreManager.secret_key = MagicMock()

    def test_jvm_starts_on_init(self, mock_jpype):
        mock_start_jvm, _ = mock_jpype

        with JavaVaultManager("test.jar") as manager:
            pass

        mock_start_jvm.assert_called_once()

    def test_full_workflow_success(self, mock_jpype):
        JAR_PATH = "my_crypt.jar"
        KEYSTORE_PATH = "my.p12"
        KEY_ALIAS = "test-alias"
        with JavaVaultManager(JAR_PATH) as manager:
            manager.load_keystore(KEYSTORE_PATH, "storepass")
            assert manager.keystore is not None

            manager.get_secret_key(KEY_ALIAS, "keypass")
            assert manager.secret_key is not None

            manager.init_vault("data.vault")
            assert manager.vault is not None
            assert manager.vault.__class__.__name__ == "MockSecureJsonVault"

            JSON_DATA = '{"k": "v"}'
            manager.save_data(JSON_DATA)
            assert manager.vault.data == JSON_DATA

            loaded_data = manager.load_data()
            assert loaded_data == JSON_DATA

    def test_keystore_load_with_path_error(self, mock_jpype):
        with JavaVaultManager("test.jar") as manager:
            with pytest.raises(
                Exception, match="java.io.IOException: Keystore was tampered with."
            ):
                manager.load_keystore("wrong.p12", "badpass")

    def test_error_saving_data_before_init_vault(self, mock_jpype):
        with JavaVaultManager("test.jar") as manager:
            manager.load_keystore("my.p12", "storepass")
            manager.get_secret_key("alias", "keypass")

            with pytest.raises(ValueError, match="Vault is not initialized"):
                manager.save_data("{}")

    def test_error_getting_key_before_load_keystore(self, mock_jpype):
        with JavaVaultManager("test.jar") as manager:
            with pytest.raises(ValueError, match="Keystore is not loaded"):
                manager.get_secret_key("alias", "keypass")

    def test_error_non_existent_key_alias(self, mock_jpype):
        with JavaVaultManager("test.jar") as manager:
            manager.load_keystore("my.p12", "storepass")

            with pytest.raises(ValueError, match="No secret key found"):
                manager.get_secret_key("non_existent_key", "keypass")

    def test_jvm_shuts_down_on_exit(self, mock_jpype):
        mock_start_jvm, mock_shutdown_jvm = mock_jpype

        with JavaVaultManager("test.jar") as manager:
            mock_shutdown_jvm.assert_not_called()

        mock_shutdown_jvm.assert_called_once()

# Fixed test_java_vault_manager.py
import pytest

from unittest.mock import patch
from src.core import JavaVaultManager 

# --- Test Cases ---
class JavaVaultManagerTest:
    def test_jvm_starts_on_init(self, mock_jpype):
        """Verifies JVM starts when JavaVaultManager is instantiated."""
        mock_start_jvm, _ = mock_jpype
        
        with JavaVaultManager("test.jar") as manager:
            pass
            
        # Check if startJVM was called once
        mock_start_jvm.assert_called_once()

    def test_full_workflow_success(self, mock_jpype):
        """Tests the full sequence of load, get key, init vault, save, and load."""
        JAR_PATH = "my_crypt.jar"
        KEYSTORE_PATH = "my.p12"
        KEY_ALIAS = "test-alias"
        
        # We no longer need to define MockKSM/MockSJV here, as the JavaVaultManager
        # will receive the mock JClasses defined in conftest.py's mock_jclass function.
        
        with JavaVaultManager(JAR_PATH) as manager:
            # 1. Load Keystore
            manager.load_keystore(KEYSTORE_PATH, "storepass")
            assert manager.keystore is not None
            
            # 2. Get Secret Key
            manager.get_secret_key(KEY_ALIAS, "keypass")
            assert manager.secret_key is not None
            
            # 3. Init Vault
            manager.init_vault("data.vault")
            assert manager.vault is not None
            # We can still assert that the initialized vault is an instance of the Mock class
            # (retrieved via JClass mock defined in conftest)
            assert manager.vault.__class__.__name__ == 'MockSecureJsonVault'
            
            # 4. Save Data
            manager.save_data('{"api": "test"}')

            # 5. Load Data (Expected return is controlled by MockSecureJsonVault.__str__)
            loaded_data = manager.load_data()
            assert loaded_data == '{"test": "loaded_data"}'
            
    # --- Test Cases: Exception/Failure Handling ---
    def test_error_calling_vault_method_before_init_vault(self, mock_jpype):
        """Should raise ValueError if vault is accessed before init_vault."""
        with JavaVaultManager("test.jar") as manager:
            # Only load key
            manager.load_keystore("my.p12", "storepass")
            manager.get_secret_key("alias", "keypass")
            
            # Attempt to save data without initializing the vault
            with pytest.raises(ValueError, match="Vault is not initialized"):
                manager.save_data('{}')

    def test_error_getting_key_before_load_keystore(self, mock_jpype):
        """Should raise ValueError if keystore is not loaded."""
        with JavaVaultManager("test.jar") as manager:
            # Attempt to get key without loading keystore
            with pytest.raises(ValueError, match="Keystore is not loaded"):
                manager.get_secret_key("alias", "keypass")

    def test_error_non_existent_key_alias(self, mock_jpype):
        """Should raise ValueError if the Java method returns null (key not found)."""
        with JavaVaultManager("test.jar") as manager:
            manager.load_keystore("my.p12", "storepass")
            
            # The MockKeyStoreManager returns None if alias is "non_existent_key"
            with pytest.raises(ValueError, match="No secret key found"):
                manager.get_secret_key("non_existent_key", "keypass")
    
    def test_jvm_shuts_down_on_exit(self, mock_jpype):
        """Verifies JVM shuts down when exiting the context manager."""
        mock_start_jvm, mock_shutdown_jvm = mock_jpype

        with JavaVaultManager("test.jar") as manager:
            mock_shutdown_jvm.assert_not_called()

        mock_shutdown_jvm.assert_called_once()
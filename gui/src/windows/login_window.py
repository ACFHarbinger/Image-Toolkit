import os
import json
import backend.src.utils.definitions as udef

from PySide6.QtCore import Qt, Signal, Slot, QUrl, QObject
from PySide6.QtQml import QQmlApplicationEngine
from backend.src.core.vault_manager import VaultManager


class LoginWindow(QObject):
    """
    A logic provider for the Login QML window.
    Handles user authentication, login and account creation.

    Emits a signal upon successful login, passing the initialized
    VaultManager instance.
    """

    # Signal emitted on successful login or account creation
    login_successful = Signal(VaultManager)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Vault Manager and Authentication State
        self.vault_manager = None
        self.is_authenticated = False

        # --- Theme state ---
        self.current_theme = "dark"

        # --- QML Setup ---
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("backend", self)
        
        qml_path = os.path.join(os.path.dirname(__file__), "..", "..", "qml", "windows", "LoginWindow.qml")
        self.engine.load(QUrl.fromLocalFile(os.path.abspath(qml_path)))
        
        if not self.engine.rootObjects():
            print("Error: Could not load LoginWindow.qml")
            return

        self.root = self.engine.rootObjects()[0]

    def show(self):
        if hasattr(self, 'root'):
            self.root.show()

    def close(self):
        if hasattr(self, 'root'):
            self.root.close()

    @Slot(str, str)
    def attempt_login(self, username, raw_password):
        """Tries to authenticate the user against the stored hash."""
        if not username or not raw_password:
            print("Input Error: Please enter both account name and password.")
            return

        try:
            # 1. Update the global file paths
            udef.update_cryptographic_values(username)

            # 2. Initialize the Vault Manager
            self.vault_manager = VaultManager(udef.JAR_FILE)

            # 3. KeyStore Loading
            self.vault_manager.load_keystore(udef.KEYSTORE_FILE, raw_password)

            # 4. Get the specific AES key
            self.vault_manager.get_secret_key(udef.KEY_ALIAS, raw_password)
            self.vault_manager.init_vault(udef.VAULT_FILE)

            # 5. Load stored credentials (hash and salt)
            stored_data = self.vault_manager.load_account_credentials()

            if stored_data.get("account_name") != username:
                print("Login Failed: Account name does not match stored account.")
                return

            stored_hash = stored_data.get("hashed_password")
            stored_salt = stored_data.get("salt")
            pepper = self.vault_manager.PEPPER

            # 6. Re-hash and verify
            password_combined = (raw_password + stored_salt + pepper).encode("utf-8")
            import hashlib

            verification_hash = hashlib.sha256(password_combined).hexdigest()

            if verification_hash == stored_hash:
                # Preference Profile Selection (Simplified for QML/Console workflow)
                # Ideally this logic would be exposed via signals/slots to QML
                # For now, we skip the interactive dialog and use current or default
                
                print(f"Login successful for {username}.")
                self.is_authenticated = True

                # --- LOAD/DECRYPT API FILES ---
                self._load_api_files()

                self.login_successful.emit(self.vault_manager)
                # We don't close() here automatically, let app.py handle transitions
            else:
                print("Login Failed: Invalid password.")

        except FileNotFoundError:
            print("Configuration Error: Account files not found. Does this account exist?")
        except Exception as e:
            print(f"Vault Error: An error occurred during login: {e}")
            if self.vault_manager:
                self.vault_manager.shutdown()

    @Slot(str, str)
    def create_account(self, username, raw_password):
        """
        Creates a new account, hashes the password, and saves it to a new
        account-specific vault.
        """
        if not username or not raw_password:
            print("Input Error: Please enter both account name and password.")
            return

        # 1. Update the global file paths
        try:
            udef.update_cryptographic_values(username)
        except Exception as e:
            print(f"Path Error: Failed to set account-specific paths: {e}")
            return

        # 2. Check if files for this specific account already exist
        if os.path.exists(udef.KEYSTORE_FILE) or os.path.exists(udef.VAULT_FILE):
            print(f"Account Exists: An account named '{username}' already has files. Please try logging in instead.")
            return

        try:
            # 3. Initialize the Vault Manager
            self.vault_manager = VaultManager(udef.JAR_FILE)

            # 4. Load the KeyStore
            self.vault_manager.load_keystore(udef.KEYSTORE_FILE, raw_password)

            # 5. Ensure Key Entry exists
            self.vault_manager.create_key_if_missing(
                udef.KEY_ALIAS, udef.KEYSTORE_FILE, raw_password
            )

            # 6. Retrieve the secret key
            self.vault_manager.get_secret_key(udef.KEY_ALIAS, raw_password)

            # 7. Initialize the vault
            self.vault_manager.init_vault(udef.VAULT_FILE)

            # 8. Save credentials
            self.vault_manager.save_account_credentials(username, raw_password)

            print(f"Success: Account '{username}' created and saved securely.")
            self.is_authenticated = True

            # --- LOAD/DECRYPT API FILES ---
            self._load_api_files()

            self.login_successful.emit(self.vault_manager)

        except Exception as e:
            print(f"Creation Error: Failed to create account: {e}")
            if self.vault_manager:
                self.vault_manager.shutdown()

    def _load_api_files(self):
        """
        Encryption/Decryption of API files.
        """
        if not self.vault_manager or not self.vault_manager.secret_key:
            print("Warning: Vault manager not ready, cannot load API files.")
            return

        print("Checking for API files to encrypt/decrypt...")

        try:
            SecureJsonVault = self.vault_manager.SecureJsonVault
            secret_key = self.vault_manager.secret_key

            if not os.path.exists(udef.API_DIR):
                return

            # --- First, encrypt any unencrypted .json files ---
            for filename in os.listdir(udef.API_DIR):
                if filename.endswith(".json") and filename not in [
                    "token.json",
                    udef.TOKEN_FILE.split(os.sep)[-1],
                ]:
                    json_file_path = os.path.join(udef.API_DIR, filename)
                    enc_file_path = json_file_path + ".enc"

                    if not os.path.exists(enc_file_path):
                        print(f"Encrypting new file: {filename} -> {filename}.enc")
                        try:
                            with open(json_file_path, "r", encoding="utf-8") as f:
                                json_content = f.read()

                            temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
                            temp_file_vault.saveData(json_content)

                        except Exception as e:
                            print(f"Failed to encrypt {filename}: {e}")

            # --- Second, decrypt and load all .enc files ---
            for filename in os.listdir(udef.API_DIR):
                if filename.endswith(".enc"):
                    enc_file_path = os.path.join(udef.API_DIR, filename)
                    key_name = filename.replace(".json.enc", "").replace(".enc", "")

                    try:
                        temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
                        java_string = temp_file_vault.loadData()
                        decrypted_json_string = str(java_string)
                        api_data = json.loads(decrypted_json_string)
                        self.vault_manager.api_credentials[key_name] = api_data
                        print(
                            f"Successfully decrypted and loaded credentials for: {key_name}"
                        )
                    except Exception as e:
                        print(f"Failed to decrypt or parse {filename}: {e}")

        except Exception as e:
            print(f"An error occurred during API file loading: {e}")

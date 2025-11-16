import os
import json
import backend.src.utils.definitions as udef

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QSizePolicy, QMessageBox,
)
from backend.src.core.java_vault_manager import JavaVaultManager


class LoginWindow(QWidget):
    """
    A window for user authentication, handling login and account creation.
    
    Emits a signal upon successful login, passing the initialized 
    JavaVaultManager instance.
    """
    
    # Signal emitted on successful login or account creation
    login_successful = Signal(JavaVaultManager) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Secure Login")
        self.setFixedSize(400, 300)
        
        # Vault Manager and Authentication State
        self.vault_manager = None
        self.is_authenticated = False
        
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title Label
        title_label = QLabel("Welcome - Secure Toolkit Access")
        title_label.setObjectName("TitleLabel")
        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Input fields
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Account Name (e.g., user_id_123)")
        self.username_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(self.password_input)
        
        # Button container
        button_layout = QHBoxLayout()

        self.create_button = QPushButton("Create Account")
        self.create_button.clicked.connect(self.create_account)
        button_layout.addWidget(self.create_button)

        self.login_button = QPushButton("Login")
        self.login_button.setObjectName("LoginButton")
        self.login_button.clicked.connect(self.attempt_login)
        # Set Login as the default button for the window
        self.login_button.setDefault(True)
        button_layout.addWidget(self.login_button)

        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)

    def apply_styles(self):
        """Applies basic dark mode styling."""
        qss = """
            QWidget {
                background-color: #2d2d30;
                color: #ffffff;
                font-family: Arial;
            }
            #TitleLabel {
                font-size: 16pt;
                font-weight: bold;
                color: #00bcd4;
            }
            QLineEdit {
                background-color: #3e3e42;
                border: 1px solid #5f646c;
                padding: 8px;
                border-radius: 5px;
                color: #ffffff;
            }
            QPushButton {
                background-color: #00bcd4;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00e5ff;
            }
        """
        self.setStyleSheet(qss)

    def _get_credentials(self):
        """Helper to retrieve and validate input fields."""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Input Error", "Please enter both account name and password.")
            return None, None
        return username, password

    def attempt_login(self):
        """Tries to authenticate the user against the stored hash."""
        username, raw_password = self._get_credentials()
        if not username:
            return

        try:
            # --- START MODIFICATION ---
            # 1. Update the global file paths in 'definitions' to be specific
            #    to this account *before* initializing the vault.
            udef.update_cryptographic_values(username)
            # --- END MODIFICATION ---

            # 2. Initialize the Vault Manager
            self.vault_manager = JavaVaultManager(udef.JAR_FILE) 
            
            # 3. KeyStore Loading (now uses suffixed udef.KEYSTORE_FILE)
            self.vault_manager.load_keystore(udef.KEYSTORE_FILE, raw_password)
            
            # 4. Get the specific AES key
            self.vault_manager.get_secret_key(udef.KEY_ALIAS, raw_password)
            self.vault_manager.init_vault(udef.VAULT_FILE)
            
            # 5. Load stored credentials (hash and salt)
            stored_data = self.vault_manager.load_account_credentials()
            
            if stored_data.get("account_name") != username:
                QMessageBox.critical(self, "Login Failed", "Account name does not match stored account.")
                return

            stored_hash = stored_data.get("hashed_password")
            stored_salt = stored_data.get("salt")
            pepper = self.vault_manager.PEPPER
            
            # 6. Re-hash and verify
            password_combined = (raw_password + stored_salt + pepper).encode('utf-8')
            import hashlib
            verification_hash = hashlib.sha256(password_combined).hexdigest()
            
            if verification_hash == stored_hash:
                QMessageBox.information(self, "Success", f"Login successful for {username}.")
                self.is_authenticated = True
                
                # --- LOAD/DECRYPT API FILES ---
                self._load_api_files()
                
                self.login_successful.emit(self.vault_manager)
                self.close()
            else:
                QMessageBox.critical(self, "Login Failed", "Invalid password.")
            
        except FileNotFoundError:
             QMessageBox.critical(self, "Configuration Error", "Account files not found. Does this account exist?")
        except Exception as e:
            QMessageBox.critical(self, "Vault Error", f"An error occurred during login: {e}\n(Is the password correct?)")
            if self.vault_manager:
                self.vault_manager.shutdown()

    def create_account(self):
        """
        Creates a new account, hashes the password, and saves it to a new
        account-specific vault.
        """
        username, raw_password = self._get_credentials()
        if not username:
            return

        # --- START MODIFICATION ---
        # 1. Update the global file paths in 'definitions' to be specific
        #    to this account *before* initializing the vault.
        try:
            udef.update_cryptographic_values(username)
        except Exception as e:
            QMessageBox.critical(self, "Path Error", f"Failed to set account-specific paths: {e}")
            return
        
        # 2. Check if files *for this specific account* already exist
        #    This prevents accidental overwrites if "Create Account" is clicked twice
        if os.path.exists(udef.KEYSTORE_FILE) or os.path.exists(udef.VAULT_FILE):
            QMessageBox.warning(self, "Account Exists", f"An account named '{username}' already has files. Please try logging in instead.")
            return
        # --- END MODIFICATION ---

        try:
            # 3. Initialize the Vault Manager
            self.vault_manager = JavaVaultManager(udef.JAR_FILE)
            
            # 4. Load the KeyStore (Creates empty KeyStore in memory)
            self.vault_manager.load_keystore(udef.KEYSTORE_FILE, raw_password)
            
            # 5. CRITICAL: Ensure Key Entry exists and save KeyStore file
            self.vault_manager.create_key_if_missing(udef.KEY_ALIAS, udef.KEYSTORE_FILE, raw_password)
            
            # 6. Retrieve the now-guaranteed secret key
            self.vault_manager.get_secret_key(udef.KEY_ALIAS, raw_password)
            
            # 7. Initialize the vault
            self.vault_manager.init_vault(udef.VAULT_FILE)

            # 8. Save credentials (this handles hashing, salting, and saving)
            self.vault_manager.save_account_credentials(username, raw_password)
            
            QMessageBox.information(self, "Success", f"Account '{username}' created and saved securely.")
            self.is_authenticated = True
            
            # --- LOAD/DECRYPT API FILES ---
            self._load_api_files()
            
            self.login_successful.emit(self.vault_manager)
            self.close()

        except Exception as e:
            QMessageBox.critical(self, "Creation Error", f"Failed to create account: {e}")
            if self.vault_manager:
                self.vault_manager.shutdown()

    def _load_api_files(self):
        """
        Encrypts any new .json files and decrypts all .enc files
        from the API_DIR, loading their content into the vault_manager.
        """
        if not self.vault_manager or not self.vault_manager.secret_key:
            print("Warning: Vault manager not ready, cannot load API files.")
            return

        print("Checking for API files to encrypt/decrypt...")
        
        try:
            SecureJsonVault = self.vault_manager.SecureJsonVault
            secret_key = self.vault_manager.secret_key
            
            if not os.path.exists(udef.API_DIR):
                print(f"API directory not found, skipping: {udef.API_DIR}")
                return

            # --- First, encrypt any unencrypted .json files ---
            # These are shared keys, so they use the account's key to encrypt
            for filename in os.listdir(udef.API_DIR):
                if filename.endswith(".json") and filename not in ["token.json", udef.TOKEN_FILE.split(os.sep)[-1]]:
                    # ^ Don't encrypt the token file, it's handled differently
                    json_file_path = os.path.join(udef.API_DIR, filename)
                    enc_file_path = json_file_path + ".enc"
                    
                    if not os.path.exists(enc_file_path):
                        print(f"Encrypting new file: {filename} -> {filename}.enc")
                        try:
                            with open(json_file_path, 'r', encoding='utf-8') as f:
                                json_content = f.read()
                            
                            temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
                            temp_file_vault.saveData(json_content)
                            
                        except Exception as e:
                            print(f"Failed to encrypt {filename}: {e}")

            # --- Second, decrypt and load all .enc files ---
            for filename in os.listdir(udef.API_DIR):
                if filename.endswith(".enc"):
                    enc_file_path = os.path.join(udef.API_DIR, filename)
                    # Use filename without .json.enc or .enc as the key
                    key_name = filename.replace(".json.enc", "").replace(".enc", "")
                    
                    try:
                        # 1. Create a temp vault instance for this file
                        temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
                        
                        # 2. Load and decrypt the data
                        java_string = temp_file_vault.loadData()
                        
                        # 3. Convert the java.lang.String to a Python str
                        decrypted_json_string = str(java_string)
                        
                        # 4. Parse the Python str
                        api_data = json.loads(decrypted_json_string)
                        
                        # 5. Store it in the vault_manager's dictionary
                        self.vault_manager.api_credentials[key_name] = api_data
                        print(f"Successfully decrypted and loaded credentials for: {key_name}")

                    except Exception as e:
                        print(f"Failed to decrypt or parse {filename}: {e}")

        except Exception as e:
            print(f"An error occurred during API file loading: {e}")
            # Do not block login/startup for this

    def closeEvent(self, event):
        """Ensure JVM is shut down if the window is closed without successful login."""
        if self.vault_manager and not self.is_authenticated:
            self.vault_manager.shutdown()
        super().closeEvent(event)

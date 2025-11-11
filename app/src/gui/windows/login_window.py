import getpass
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QSizePolicy, QMessageBox,
)
try:
    import app.src.utils.definitions as udef
    from app.src.core.java_vault_manager import JavaVaultManager
except:
    import src.utils.definitions as udef
    from src.core.java_vault_manager import JavaVaultManager


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
            # 1. Initialize the Vault Manager
            self.vault_manager = JavaVaultManager(udef.JAR_FILE) 
            
            # 2. KeyStore Loading (using raw_password for KeyStore password)
            self.vault_manager.load_keystore(udef.KEYSTORE_FILE, raw_password)
            
            # 3. Get the specific AES key (using raw_password for Key entry password)
            # NOTE: If this fails, it means the keystore wasn't created via "Create Account"
            self.vault_manager.get_secret_key(udef.KEY_ALIAS, raw_password)
            self.vault_manager.init_vault(udef.VAULT_FILE)
            
            # 4. Load stored credentials (hash and salt)
            stored_data = self.vault_manager.load_account_credentials()
            
            if stored_data.get("account_name") != username:
                QMessageBox.critical(self, "Login Failed", "Account name does not match stored account.")
                return

            stored_hash = stored_data.get("hashed_password")
            stored_salt = stored_data.get("salt")
            pepper = self.vault_manager.PEPPER
            
            # 5. Re-hash and verify
            password_combined = (raw_password + stored_salt + pepper).encode('utf-8')
            import hashlib
            verification_hash = hashlib.sha256(password_combined).hexdigest()
            
            if verification_hash == stored_hash:
                QMessageBox.information(self, "Success", f"Login successful for {username}.")
                self.is_authenticated = True
                self.login_successful.emit(self.vault_manager)
                self.close()
            else:
                QMessageBox.critical(self, "Login Failed", "Invalid password.")
            
        except FileNotFoundError:
             QMessageBox.critical(self, "Configuration Error", "Vault or KeyStore files not found. Create account first.")
        except Exception as e:
            QMessageBox.critical(self, "Vault Error", f"An error occurred during login: {e}")
            if self.vault_manager:
                self.vault_manager.shutdown()

    def create_account(self):
        """Creates a new account, hashes the password, and saves it to the vault."""
        username, raw_password = self._get_credentials()
        if not username:
            return

        try:
            # 1. Initialize the Vault Manager
            self.vault_manager = JavaVaultManager(udef.JAR_FILE)
            
            # 2. Load the KeyStore (Creates empty KeyStore in memory if file doesn't exist)
            self.vault_manager.load_keystore(udef.KEYSTORE_FILE, raw_password)
            
            # 3. CRITICAL FIX: Ensure Key Entry exists and save KeyStore file
            self.vault_manager.create_key_if_missing(udef.KEY_ALIAS, udef.KEYSTORE_FILE, raw_password)
            
            # 4. Retrieve the now-guaranteed secret key
            self.vault_manager.get_secret_key(udef.KEY_ALIAS, raw_password)
            
            # 5. Initialize the vault
            self.vault_manager.init_vault(udef.VAULT_FILE)

            # 6. Save credentials (this handles hashing, salting, and saving to encrypted file)
            self.vault_manager.save_account_credentials(username, raw_password)
            
            QMessageBox.information(self, "Success", f"Account '{username}' created and saved securely.")
            self.is_authenticated = True
            self.login_successful.emit(self.vault_manager)
            self.close()

        except Exception as e:
            QMessageBox.critical(self, "Creation Error", f"Failed to create account: {e}")
            if self.vault_manager:
                self.vault_manager.shutdown()

    def closeEvent(self, event):
        """Ensure JVM is shut down if the window is closed without successful login."""
        if self.vault_manager and not self.is_authenticated:
            self.vault_manager.shutdown()
        super().closeEvent(event)

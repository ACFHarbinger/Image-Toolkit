import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

import backend.src.constants as udef
from backend.src.core.vault_manager import VaultManager
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class LoginWindow(QWidget):
    """
    A window for user authentication, handling login and account creation.

    Emits a signal upon successful login, passing the initialized
    VaultManager instance.
    """

    # Signal emitted on successful login or account creation
    login_successful = Signal(VaultManager)

    # ── modes ──────────────────────────────────────────────────────────────────
    _MODE_NORMAL = "normal"
    _MODE_GUEST  = "guest"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Secure Login")
        self.setFixedSize(450, 320)

        # Vault Manager and Authentication State
        self.vault_manager = None
        self.is_authenticated = False

        # Theme state
        self.current_theme = "dark"
        # Current UI mode
        self._mode = self._MODE_NORMAL

        self.init_ui()
        self.apply_styles()

    # ── UI construction ────────────────────────────────────────────────────────

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Header Layout (Title + Theme Button) ---
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("Account Login")
        self.title_label.setObjectName("TitleLabel")
        header_layout.addWidget(self.title_label, alignment=Qt.AlignmentFlag.AlignLeft)

        header_layout.addStretch(1)

        # Theme Button
        self.theme_button = QPushButton("🎨")
        self.theme_button.setObjectName("ThemeButton")
        self.theme_button.setFixedSize(30, 30)
        self.theme_button.setToolTip("Toggle light/dark theme")
        self.theme_button.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.theme_button, alignment=Qt.AlignmentFlag.AlignRight)

        main_layout.addLayout(header_layout)

        # ── Username field (always visible) ────────────────────────────────────
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Account Name (e.g., user_id_123)")
        self.username_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(self.username_input)

        # ── Password field (normal mode only) ──────────────────────────────────
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(self.password_input)

        # ── Guest-mode info label (hidden by default) ───────────────────────────
        self.guest_info_label = QLabel(
            "👤  Guest session — settings are kept in volatile memory only."
        )
        self.guest_info_label.setObjectName("GuestInfoLabel")
        self.guest_info_label.setWordWrap(True)
        self.guest_info_label.setVisible(False)
        main_layout.addWidget(self.guest_info_label)

        # ── Primary action buttons row ──────────────────────────────────────────
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        # Normal mode: Create Account
        self.create_button = QPushButton("Create Account")
        self.create_button.clicked.connect(self.create_account)
        button_layout.addWidget(self.create_button)

        # Normal mode: Login  /  Guest mode: Login Anonymously
        self.login_button = QPushButton("Login")
        self.login_button.setObjectName("LoginButton")
        self.login_button.clicked.connect(self._primary_action)
        self.login_button.setDefault(True)
        button_layout.addWidget(self.login_button)

        main_layout.addLayout(button_layout)

        # ── Guest-mode secondary button row (hidden by default) ─────────────────
        self.guest_action_layout = QHBoxLayout()
        self.guest_as_button = QPushButton("Login as Guest")
        self.guest_as_button.setObjectName("LoginButton")
        self.guest_as_button.clicked.connect(self._guest_with_username)
        self.guest_as_button.setVisible(False)
        self.guest_action_layout.addWidget(self.guest_as_button)
        main_layout.addLayout(self.guest_action_layout)

        # ── Bottom row: Guest-mode toggle (distinct pill button, centered) ───
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.addStretch(1)

        self.guest_toggle_button = QPushButton("👤  Guest Mode")
        self.guest_toggle_button.setObjectName("GuestToggleButton")
        self.guest_toggle_button.setToolTip(
            "Switch to Guest login mode — no password required; "
            "settings remain in volatile memory only"
        )
        self.guest_toggle_button.clicked.connect(self.toggle_guest_mode)
        bottom_layout.addWidget(self.guest_toggle_button, alignment=Qt.AlignmentFlag.AlignCenter)

        bottom_layout.addStretch(1)

        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

    # ── Mode switching ──────────────────────────────────────────────────────────

    def toggle_guest_mode(self):
        """Toggle between normal login mode and guest login mode."""
        if self._mode == self._MODE_NORMAL:
            self._enter_guest_mode()
        else:
            self._enter_normal_mode()

    def _enter_guest_mode(self):
        self._mode = self._MODE_GUEST

        # Update title
        self.title_label.setText("Guest Login")

        # Hide password field; show guest info label
        self.password_input.setVisible(False)
        self.guest_info_label.setVisible(True)

        # Reconfigure primary button row to "Login Anonymously"
        self.create_button.setText("Login Anonymously")
        self.login_button.setText("Login as Guest")

        # Show guest-as button (redundant alias kept for clarity)
        # Actually we re-use the existing two primary buttons, so hide the extra row
        self.guest_as_button.setVisible(False)

        # Update placeholder
        self.username_input.setPlaceholderText("Username (optional for anonymous login)")

        # Toggle button becomes "🔐  Account Access"
        self.guest_toggle_button.setText("🔐  Account Access")
        self.guest_toggle_button.setToolTip("Return to standard account login")

        self.apply_styles()

    def _enter_normal_mode(self):
        self._mode = self._MODE_NORMAL

        # Restore title
        self.title_label.setText("Account Login")

        # Restore password field; hide guest info
        self.password_input.setVisible(True)
        self.guest_info_label.setVisible(False)

        # Restore primary button labels
        self.create_button.setText("Create Account")
        self.login_button.setText("Login")

        # Restore connections
        # (already correctly bound in init_ui via _primary_action)

        # Restore placeholder
        self.username_input.setPlaceholderText("Account Name (e.g., user_id_123)")

        # Toggle button reverts
        self.guest_toggle_button.setText("👤  Guest Mode")
        self.guest_toggle_button.setToolTip(
            "Switch to Guest login mode — no password required; "
            "settings remain in volatile memory only"
        )

        self.apply_styles()

    # ── Action dispatch ─────────────────────────────────────────────────────────

    def _primary_action(self):
        """Dispatch the primary button click based on the current mode."""
        if self._mode == self._MODE_GUEST:
            # In guest mode the right-hand button is "Login as Guest" (with typed username)
            self._guest_with_username()
        else:
            self.attempt_login()

    def _secondary_action(self):
        """Dispatch the secondary button click based on the current mode."""
        if self._mode == self._MODE_GUEST:
            # In guest mode the left-hand button is "Login Anonymously"
            self._guest_anonymous()
        else:
            self.create_account()

    # ── Theme ───────────────────────────────────────────────────────────────────

    def toggle_theme(self):
        """Switches the theme from dark to light and vice-versa."""
        if self.current_theme == "dark":
            self.current_theme = "light"
        else:
            self.current_theme = "dark"
        self.apply_styles()

    def apply_styles(self):
        """Applies styling based on the current self.current_theme."""
        is_guest_mode = (self._mode == self._MODE_GUEST)

        if self.current_theme == "dark":
            bg_color      = "#2d2d30"
            text_color    = "#ffffff"
            title_color   = "#00bcd4" if not is_guest_mode else "#ffb300"
            input_bg      = "#3e3e42"
            input_border  = "#5f646c"
            btn_bg        = "#00bcd4"
            btn_hover     = "#00e5ff"
            theme_btn_color = "#00bcd4"
            guest_btn_bg    = "#e65100"
            guest_btn_hover = "#ff6d00"
            account_btn_bg    = "#0288d1"
            account_btn_hover = "#039be5"
            guest_info_color = "#ffb300"
        else:
            bg_color      = "#f4f4f4"
            text_color    = "#2d2d30"
            title_color   = "#007AFF" if not is_guest_mode else "#e65100"
            input_bg      = "#ffffff"
            input_border  = "#cccccc"
            btn_bg        = "#007AFF"
            btn_hover     = "#0056b3"
            theme_btn_color = "#007AFF"
            guest_btn_bg    = "#e65100"
            guest_btn_hover = "#ff6d00"
            account_btn_bg    = "#1976d2"
            account_btn_hover = "#1565c0"
            guest_info_color = "#e65100"

        guest_toggle_bg    = guest_btn_bg    if self._mode == self._MODE_NORMAL else account_btn_bg
        guest_toggle_hover = guest_btn_hover if self._mode == self._MODE_NORMAL else account_btn_hover

        qss = f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
                font-family: Arial;
            }}
            #TitleLabel {{
                font-size: 16pt;
                font-weight: bold;
                color: {title_color};
            }}
            #GuestInfoLabel {{
                color: {guest_info_color};
                font-size: 10pt;
                font-style: italic;
            }}
            QLineEdit {{
                background-color: {input_bg};
                border: 1px solid {input_border};
                padding: 8px;
                border-radius: 5px;
                color: {text_color};
            }}
            QPushButton {{
                background-color: {btn_bg};
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                font-weight: bold;
                color: #ffffff;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}

            /* Theme Button Specific Style */
            #ThemeButton {{
                background-color: transparent;
                color: {theme_btn_color};
                font-size: 16pt;
                padding: 0;
                border: none;
            }}
            #ThemeButton:hover {{
                color: {btn_hover};
            }}

            /* Guest Mode Toggle — pill shaped, distinctly coloured */
            #GuestToggleButton {{
                background-color: {guest_toggle_bg};
                border: none;
                padding: 6px 16px;
                border-radius: 12px;
                font-weight: bold;
                font-size: 9pt;
                color: #ffffff;
                min-width: 120px;
                max-width: 160px;
            }}
            #GuestToggleButton:hover {{
                background-color: {guest_toggle_hover};
            }}
        """
        self.setStyleSheet(qss)

    # ── Guest login helpers ─────────────────────────────────────────────────────

    def _guest_anonymous(self):
        """Log in as a completely anonymous guest with a randomly generated username."""
        random_username = f"guest_{uuid.uuid4().hex[:8]}"
        self._do_guest_login(random_username, anonymous=True)

    def _guest_with_username(self):
        """Log in as a guest using the typed username (or anonymous if field is empty)."""
        username = self.username_input.text().strip()
        if not username:
            # If field is empty fall back to anonymous
            self._guest_anonymous()
            return
        self._do_guest_login(username, anonymous=False)

    def _do_guest_login(self, username: str, *, anonymous: bool):
        """Core guest-login logic shared by both anonymous and named paths."""
        try:
            self.vault_manager = VaultManager.create_guest_vault(username)
            self.is_authenticated = True

            label = f"anonymous guest ('{username}')" if anonymous else f"guest '{username}'"
            QMessageBox.information(
                self,
                "Guest Mode",
                f"Logged in as {label}.\n\n"
                "Settings saved during this session will be stored in volatile memory "
                "only and will not persist on disk.",
            )
            self.login_successful.emit(self.vault_manager)
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Guest Mode Error", f"Failed to start Guest session: {e}")
            if self.vault_manager:
                self.vault_manager.shutdown()

    # ── Normal-mode button handlers ─────────────────────────────────────────────

    def _get_credentials(self):
        """Helper to retrieve and validate input fields."""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "Input Error", "Please enter both account name and password.")
            return None, None
        return username, password

    def _copy_template_crypto_files(self):
        """
        Copies all files from assets/secrets to ~/.image-toolkit/secrets/
        if they do not yet exist in the target directory.
        """
        template_dir = Path(udef.SECRETS_DIR)
        target_dir = Path(udef.LOCAL_SECRETS_DIR)

        if not template_dir.exists():
            print(f"[LoginWindow] Warning: Template cryptography directory {template_dir} does not exist.")
            return

        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            for item in template_dir.iterdir():
                if item.is_file():
                    dest_file = target_dir / item.name
                    if not dest_file.exists():
                        shutil.copy2(item, dest_file)
                        print(f"[LoginWindow] Copied template crypto file: {item.name} -> {dest_file}")
        except Exception as e:
            print(f"[LoginWindow] Error copying template cryptography files: {e}")

    # Keep old public name for backward compat with any external callers
    def attempt_guest_login(self):
        """
        Legacy public entry-point: redirect to the guest-with-username path.
        Logs in the user in Guest Mode without requiring a password.
        """
        self._guest_with_username()

    def attempt_login(self):  # noqa: C901
        """Tries to authenticate the user against the stored hash."""
        self._copy_template_crypto_files()
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
            self.vault_manager = VaultManager()

            # 3. KeyStore Loading (now uses suffixed udef.KEYSTORE_FILE)
            self.vault_manager.load_keystore(udef.KEYSTORE_FILE, raw_password)  # pyrefly: ignore [bad-argument-type]

            # 4. Get the specific AES key
            self.vault_manager.get_secret_key(udef.KEY_ALIAS, raw_password)  # pyrefly: ignore [bad-argument-type]
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
            password_combined = (raw_password + stored_salt + pepper).encode("utf-8")  # pyrefly: ignore [unsupported-operation]

            verification_hash = hashlib.sha256(password_combined).hexdigest()
            if verification_hash == stored_hash:
                # --- NEW: Preference Profile Selection ---
                profiles = stored_data.get("system_preference_profiles", {})
                save_required = False  # <--- NEW FLAG

                if profiles:
                    items = ["Default", "Previous Profile"] + sorted(profiles.keys())
                    item, ok = QInputDialog.getItem(
                        self,
                        "Select Preference Profile",
                        "Choose a system preference setup to apply:",
                        items,
                        0,  # Select "Default" by default
                        False,
                    )

                    if ok and item:
                        if item == "Default":
                            new_theme = "dark"
                            new_configs = {}
                            new_accent_dark = "#00bcd4"
                            new_accent_light = "#007AFF"
                            new_font_scale = 100
                            new_ui_density = "Comfortable"

                            current_theme = stored_data.get("theme", "dark")
                            current_configs = stored_data.get("active_tab_configs", {})

                            if new_theme != current_theme or new_configs != current_configs:
                                stored_data["theme"] = new_theme
                                stored_data["active_tab_configs"] = new_configs
                                save_required = True

                            prefs = stored_data.get("preferences")
                            if not isinstance(prefs, dict):
                                prefs = {}
                                stored_data["preferences"] = prefs

                            _APPEARANCE_DEFAULTS = {
                                "accent_color_dark": new_accent_dark,
                                "accent_color_light": new_accent_light,
                                "font_scale": new_font_scale,
                                "ui_density": new_ui_density,
                            }
                            for _key, _val in _APPEARANCE_DEFAULTS.items():
                                if prefs.get(_key) != _val:
                                    prefs[_key] = _val
                                    save_required = True
                        elif item != "Previous Profile":
                            # Apply selected profile to the temporary dictionary
                            profile_data = profiles[item]
                            new_theme = profile_data.get("theme", "dark")
                            new_configs = profile_data.get("active_tab_configs", {})

                            # 1. Check if the theme or active configs are changing
                            current_theme = stored_data.get("theme", "dark")
                            current_configs = stored_data.get("active_tab_configs", {})

                            if new_theme != current_theme or new_configs != current_configs:
                                # 2. Update the data and set the flag
                                stored_data["theme"] = new_theme
                                stored_data["active_tab_configs"] = new_configs
                                save_required = True  # <--- SET FLAG

                            # §4.13 — Merge appearance keys into preferences if present
                            _APPEARANCE_KEYS = (
                                "accent_color_dark",
                                "accent_color_light",
                                "font_scale",
                                "ui_density",
                            )
                            prefs = stored_data.get("preferences")
                            if not isinstance(prefs, dict):
                                prefs = {}
                                stored_data["preferences"] = prefs

                            for _key in _APPEARANCE_KEYS:
                                if _key in profile_data and profile_data[_key] != prefs.get(_key):
                                    prefs[_key] = profile_data[_key]
                                    save_required = True

                # === CRITICAL MODIFICATION: Check flag before saving ===
                if save_required:
                    # Save back to vault only if settings have changed
                    self.vault_manager.save_data(json.dumps(stored_data))

                # -----------------------------------------

                QMessageBox.information(self, "Success", f"Login successful for {username}.")
                self.is_authenticated = True
                self.vault_manager.account_name = username  # pyrefly: ignore [missing-attribute]
                self.vault_manager.raw_password = raw_password  # pyrefly: ignore [missing-attribute]

                # --- LOAD/DECRYPT API FILES ---
                self._load_api_files()

                self.login_successful.emit(self.vault_manager)
                self.close()
            else:
                QMessageBox.critical(self, "Login Failed", "Invalid password.")

        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Configuration Error",
                "Account files not found. Does this account exist?",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Vault Error",
                f"An error occurred during login: {e}\n(Is the password correct?)",
            )
            if self.vault_manager:
                self.vault_manager.shutdown()

    def create_account(self):
        """
        Creates a new account, hashes the password, and saves it to a new
        account-specific vault.
        """
        # In guest mode the "Create Account" button was replaced by "Login Anonymously"
        if self._mode == self._MODE_GUEST:
            self._guest_anonymous()
            return

        self._copy_template_crypto_files()
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
            QMessageBox.warning(
                self,
                "Account Exists",
                f"An account named '{username}' already has files. Please try logging in instead.",
            )
            return
        # --- END MODIFICATION ---

        try:
            # 3. Initialize the Vault Manager
            self.vault_manager = VaultManager()

            # 4. Load the KeyStore (Creates empty KeyStore in memory)
            self.vault_manager.load_keystore(udef.KEYSTORE_FILE, raw_password)  # pyrefly: ignore [bad-argument-type]

            # 5. CRITICAL: Ensure Key Entry exists and save KeyStore file
            self.vault_manager.create_key_if_missing(
                udef.KEY_ALIAS,
                udef.KEYSTORE_FILE,
                raw_password,  # pyrefly: ignore [bad-argument-type]
            )

            # 6. Retrieve the now-guaranteed secret key
            self.vault_manager.get_secret_key(udef.KEY_ALIAS, raw_password)  # pyrefly: ignore [bad-argument-type]

            # 7. Initialize the vault
            self.vault_manager.init_vault(udef.VAULT_FILE)

            # 8. Save credentials (this handles hashing, salting, and saving)
            self.vault_manager.save_account_credentials(username, raw_password)  # pyrefly: ignore [bad-argument-type]

            QMessageBox.information(self, "Success", f"Account '{username}' created and saved securely.")
            self.is_authenticated = True
            self.vault_manager.account_name = username  # pyrefly: ignore [missing-attribute]
            self.vault_manager.raw_password = raw_password  # pyrefly: ignore [missing-attribute]

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
                if filename.endswith(".json") and filename not in [
                    "token.json",
                    udef.TOKEN_FILE.split(os.sep)[-1],
                ]:
                    # ^ Don't encrypt the token file, it's handled differently
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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Ensure JVM is shut down if the window is closed without successful login."""
        if self.vault_manager and not self.is_authenticated:
            self.vault_manager.shutdown()
        super().closeEvent(event)

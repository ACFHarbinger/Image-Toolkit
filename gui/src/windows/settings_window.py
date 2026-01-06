import json

import os
from PySide6.QtCore import Qt, QObject, Slot, Property, Signal, QUrl
from PySide6.QtQml import QQmlApplicationEngine


class SettingsWindow(QObject):
    """
    A logic provider for the Settings QML window.
    """
    # Signals
    account_changed = Signal()
    theme_changed = Signal()
    profiles_changed = Signal()
    config_list_changed = Signal()
    current_config_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window_ref = parent
        
        # Reference to the Vault Manager from MainWindow
        self.vault_manager = (
            self.main_window_ref.vault_manager if self.main_window_ref else None
        )

        # Load initial credentials and settings
        self.current_account_name = "N/A"
        self.initial_theme = "dark"
        self.active_tab_configs = {}
        self.system_profiles = {}

        if self.vault_manager:
            try:
                creds = self.vault_manager.load_account_credentials()
                self.current_account_name = creds.get("account_name", "N/A")
                self.initial_theme = creds.get("theme", "dark")
                self.active_tab_configs = creds.get("active_tab_configs", {})
                self.system_profiles = creds.get("system_preference_profiles", {})
            except Exception:
                pass

        self.tab_defaults_config = self._load_tab_defaults_from_vault()
        
        # State mapping logic
        self._current_tab_class_selection = ""
        self._current_config_selection = ""

        # QML Setup
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("backend", self)
        
        qml_path = os.path.join(os.path.dirname(__file__), "..", "..", "qml", "windows", "SettingsWindow.qml")
        self.engine.load(QUrl.fromLocalFile(os.path.abspath(qml_path)))
        
        if not self.engine.rootObjects():
            print("Error: Could not load SettingsWindow.qml")
            return
            
        self.root = self.engine.rootObjects()[0]

    def show(self):
        if hasattr(self, 'root'):
            self.root.show()

    # --- Properties ---

    @Property(str, notify=account_changed)
    def accountName(self):
        return self.current_account_name
        
    @Property(str, notify=theme_changed)
    def currentTheme(self):
        return self.initial_theme

    @Property(list, notify=profiles_changed)
    def profileList(self):
        return sorted(list(self.system_profiles.keys()))

    @Property(list, notify=config_list_changed)
    def tabList(self):
        # Flattened list of tab class names
        return sorted(self._get_all_tab_names_uncategorized())

    @Property(list, notify=current_config_changed)
    def configListForTab(self):
        if not self._current_tab_class_selection: 
            return []
        configs = self.tab_defaults_config.get(self._current_tab_class_selection, {})
        return sorted(configs.keys())

    @Property(str, notify=current_config_changed)
    def configContent(self):
        if not self._current_tab_class_selection:
            return ""
        
        # If a specific config is selected
        if self._current_config_selection:
             configs = self.tab_defaults_config.get(self._current_tab_class_selection, {})
             config = configs.get(self._current_config_selection, {})
             return json.dumps(config, indent=4)
        
        # Otherwise return default
        tab_instance = self._get_tab_instance(self._current_tab_class_selection)
        if tab_instance and hasattr(tab_instance, "get_default_config"):
            try:
                return json.dumps(tab_instance.get_default_config(), indent=4)
            except:
                pass
        return "{}"

    # --- Slots ---

    @Slot(str)
    def setTabSelection(self, class_name):
        self._current_tab_class_selection = class_name
        self._current_config_selection = "" # Reset config selection on tab change
        self.config_list_changed.emit() # Potentially not needed if list is static per tab
        self.current_config_changed.emit()

    @Slot(str)
    def setConfigSelection(self, config_name):
        self._current_config_selection = config_name
        self.current_config_changed.emit()

    @Slot(str, str)
    def saveConfig(self, name, json_content):
        # Reuse logic from _save_current_tab_config
        # We'll need to adapt the method to take args instead of reading widgets
        pass # To be implemented in next step by modifying existing methods

    @Slot()
    def applySettings(self):
        # Adapted from confirm_update_settings / _update_settings_logic
        self._update_settings_logic()
    
    @Slot()
    def resetToDefaults(self):
        self.reset_settings()

    @Slot(str)
    def loadProfile(self, profile_name):
        if profile_name in self.system_profiles:
            # We need to signal QML to update its state
            # This might require more properties or a signal with data
            pass 
            
    # Keep helper methods...

    # ---------------------------------------------------------------------
    # --- Profile Management Methods ---
    # ---------------------------------------------------------------------

    @Slot(str)
    def loadProfile(self, profile_name):
        if profile_name in self.system_profiles:
            profile_data = self.system_profiles[profile_name]
            
            # Apply Theme
            loaded_theme = profile_data.get("theme", "dark")
            self.initial_theme = loaded_theme
            self.theme_changed.emit()
            
            # Apply Tab Configs
            self.active_tab_configs = profile_data.get("active_tab_configs", {})
            print(f"Profile '{profile_name}' loaded.")

    @Slot(str)
    def deleteProfile(self, profile_name):
        if profile_name in self.system_profiles:
            del self.system_profiles[profile_name]
            if self.vault_manager:
                try:
                    user_data = self.vault_manager.load_account_credentials()
                    user_data["system_preference_profiles"] = self.system_profiles
                    self.vault_manager.save_account_credentials(user_data)
                    self.profiles_changed.emit()
                except Exception as e:
                    print(f"Error deleting profile: {e}")

    @Slot(str, str)
    def saveCurrentAsProfile(self, profile_name, theme_choice):
        if not profile_name: return
        
        new_profile = {
            "theme": theme_choice,
            "active_tab_configs": self.active_tab_configs
        }
        self.system_profiles[profile_name] = new_profile
        
        if self.vault_manager:
            try:
                user_data = self.vault_manager.load_account_credentials()
                user_data["system_preference_profiles"] = self.system_profiles
                self.vault_manager.save_account_credentials(user_data)
                self.profiles_changed.emit()
            except Exception as e:
                 print(f"Error saving profile: {e}")

    # ---------------------------------------------------------------------
    # --- Tab Config Logic ---
    # ---------------------------------------------------------------------

    def _load_tab_defaults_from_vault(self):
        if self.vault_manager:
            try:
                creds = self.vault_manager.load_account_credentials()
                return creds.get("tab_defaults_config", {})
            except Exception:
                return {}
        return {}
        
    def _save_tab_defaults_to_vault(self):
        if self.vault_manager:
            try:
                user_data = self.vault_manager.load_account_credentials()
                user_data["tab_defaults_config"] = self.tab_defaults_config
                return self.vault_manager.save_account_credentials(user_data)
            except Exception as e:
                print(f"Error saving tab defaults: {e}")
                return False
        return False

    @Slot(str, str)
    def createConfigFromEditor(self, config_name, json_content):
        if not self._current_tab_class_selection or not config_name:
            return

        try:
            config_data = json.loads(json_content)
            
            if self._current_tab_class_selection not in self.tab_defaults_config:
                self.tab_defaults_config[self._current_tab_class_selection] = {}
            
            self.tab_defaults_config[self._current_tab_class_selection][config_name] = config_data
            
            if self._save_tab_defaults_to_vault():
                self.config_list_changed.emit()
                self._current_config_selection = config_name
                self.current_config_changed.emit()
        except Exception as e:
             print(f"Error creating config: {e}")

    @Slot(str)
    def deleteCurrentConfig(self, config_name):
        if not self._current_tab_class_selection or not config_name:
            return
            
        if self._current_tab_class_selection in self.tab_defaults_config:
             if config_name in self.tab_defaults_config[self._current_tab_class_selection]:
                 del self.tab_defaults_config[self._current_tab_class_selection][config_name]
                 if self._save_tab_defaults_to_vault():
                     self.config_list_changed.emit()
                     self._current_config_selection = ""
                     self.current_config_changed.emit()

    @Slot(str)
    def setConfigForTab(self, config_name):
        """Sets the selected config as the active one for the current tab (Apply Action)."""
        if not self._current_tab_class_selection: return
        
        display_name = config_name if config_name else "None (Default)"
        self.active_tab_configs[self._current_tab_class_selection] = display_name
        
        tab_instance = self._get_tab_instance(self._current_tab_class_selection)
        
        config_data = {}
        if config_name:
            configs = self.tab_defaults_config.get(self._current_tab_class_selection, {})
            config_data = configs.get(config_name, {})
        elif tab_instance and hasattr(tab_instance, "get_default_config"):
            try:
                config_data = tab_instance.get_default_config()
            except: 
                pass
                
        if tab_instance and hasattr(tab_instance, "set_config"):
             try:
                 tab_instance.set_config(config_data)
                 print(f"Applied config {config_name} to {self._current_tab_class_selection}")
             except Exception as e:
                 print(f"Error setting config: {e}")

    # ---------------------------------------------------------------------
    # --- Helper Logic ---
    # ---------------------------------------------------------------------
    
    def _update_settings_logic(self):
        """Saves settings to vault."""
        try:
            if not self.vault_manager: return

            user_data = self.vault_manager.load_account_credentials()
            user_data["theme"] = self.initial_theme
            user_data["active_tab_configs"] = self.active_tab_configs
            user_data["system_preference_profiles"] = self.system_profiles
            
            if self.vault_manager.save_account_credentials(user_data):
                if self.main_window_ref and self.initial_theme:
                    self.main_window_ref.set_application_theme(self.initial_theme)
                    
            if hasattr(self, 'root'):
                self.root.close()
        except Exception as e:
            print(f"Update failed: {e}")

    @Slot(str)
    def setTheme(self, theme_name):
        self.initial_theme = theme_name.lower()
        self.theme_changed.emit()

    @Slot()
    def refreshApplication(self):
        if self.main_window_ref and hasattr(self.main_window_ref, "restart_application"):
            self.main_window_ref.restart_application()

    def _get_all_tab_names_uncategorized(self):
        """Returns a flat list of all tab class names from the MainWindow."""
        names = []
        if self.main_window_ref and hasattr(self.main_window_ref, "get_all_tabs"):
             tabs = self.main_window_ref.get_all_tabs()
             for tab in tabs:
                 names.append(tab.__class__.__name__)
        return names

    def _get_tab_instance(self, class_name):
        if self.main_window_ref and hasattr(self.main_window_ref, "get_tab_by_class_name"):
            return self.main_window_ref.get_tab_by_class_name(class_name)
        return None

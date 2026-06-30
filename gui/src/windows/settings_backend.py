import json
from PySide6.QtCore import QObject, Signal, Property, Slot
from PySide6.QtWidgets import QMessageBox

class SettingsBackend(QObject):
    profile_list_changed = Signal()
    account_changed = Signal()
    theme_changed = Signal()
    tab_list_changed = Signal()
    config_list_changed = Signal()
    config_content_changed = Signal()

    def __init__(self, main_backend_ref):
        super().__init__()
        self.main_backend = main_backend_ref
        self.vault_manager = getattr(main_backend_ref, "vault_manager", None)
        
        self._system_profiles = {}
        self._account_name = "N/A"
        self._current_theme = "dark"
        self._tab_defaults_config = {}
        
        # Load initial data
        if self.vault_manager:
            try:
                creds = self.vault_manager.load_account_credentials()
                self._account_name = creds.get("account_name", "N/A")
                self._current_theme = creds.get("theme", "dark")
                self._system_profiles = creds.get("system_preference_profiles", {})
                self._tab_defaults_config = creds.get("tab_configurations", {})
            except Exception as e:
                print(f"Error loading settings: {e}")

        # Active selection state
        self._selected_tab_class = ""
        self._selected_config_name = ""
        self._config_editor_content = ""

    # --- Properties ---

    @Property(list, notify=profile_list_changed)
    def profileList(self):
        return sorted(list(self._system_profiles.keys()))

    @Property(str, notify=account_changed)
    def accountName(self):
        return self._account_name

    @Property(str, notify=theme_changed)
    def currentTheme(self):
        return self._current_theme

    @Property(list, notify=tab_list_changed)
    def tabList(self):
        # We need to get available tab classes.
        # MainBackend likely has references or we can list them manually or dynamically.
        # For now, return a placeholder or dynamic list if possible.
        # existing SettingsWindow iterated over MainWindow tabs.
        # main_backend has explicit tab instances.
        tabs = [
            "ImageExtractorTab", "ImageCrawlTab", "ReverseImageSearchTab", 
            "DriveSyncTab", "WebRequestsTab", "DeleteTab", "ConvertTab", 
            "WallpaperTab", "ScanMetadataTab", "DatabaseTab", "SearchTab", "MergeTab"
        ]
        return sorted(tabs)

    @Property(list, notify=config_list_changed)
    def configListForTab(self):
        if not self._selected_tab_class:
            return []
        configs = self._tab_defaults_config.get(self._selected_tab_class, {})
        return sorted(list(configs.keys()))

    @Property(str, notify=config_content_changed)
    def configContent(self):
        return self._config_editor_content

    # --- Slots ---

    @Slot(str)
    def loadProfile(self, name):
        if name in self._system_profiles:
            profile = self._system_profiles[name]
            # Apply profile (theme, etc.)
            new_theme = profile.get("theme", "dark")
            self.setTheme(new_theme)
            # TODO: Apply tab configs

    @Slot(str)
    def deleteProfile(self, name):
        if name in self._system_profiles:
            del self._system_profiles[name]
            self._save_vault()
            self.profile_list_changed.emit()

    @Slot(str, str)
    def saveCurrentAsProfile(self, name, theme):
        # Simplified: Just saving theme for now
        self._system_profiles[name] = {"theme": theme.lower()}
        self._save_vault()
        self.profile_list_changed.emit()

    @Slot(str)
    def setTheme(self, theme):
        self._current_theme = theme.lower()
        self.theme_changed.emit()
        # Save to vault immediately? Or wait for apply?
        # SettingsWindow saved via 'applySettings'.
        
    @Slot(str)
    def setTabSelection(self, tab_name):
        self._selected_tab_class = tab_name
        self.config_list_changed.emit()
        self._config_editor_content = "" # Reset or load default
        self.config_content_changed.emit()

    @Slot(str)
    def setConfigSelection(self, config_name):
        self._selected_config_name = config_name
        if self._selected_tab_class and config_name:
            configs = self._tab_defaults_config.get(self._selected_tab_class, {})
            data = configs.get(config_name, {})
            self._config_editor_content = json.dumps(data, indent=4)
            self.config_content_changed.emit()

    @Slot(str)
    def createConfigFromEditor(self, name, content):
        try:
            data = json.loads(content)
            if self._selected_tab_class:
                if self._selected_tab_class not in self._tab_defaults_config:
                    self._tab_defaults_config[self._selected_tab_class] = {}
                self._tab_defaults_config[self._selected_tab_class][name] = data
                self._save_vault()
                self.config_list_changed.emit()
        except Exception as e:
            print(f"JSON Error: {e}")

    @Slot(str)
    def deleteCurrentConfig(self, name):
         if self._selected_tab_class and name:
             if name in self._tab_defaults_config.get(self._selected_tab_class, {}):
                 del self._tab_defaults_config[self._selected_tab_class][name]
                 self._save_vault()
                 self.config_list_changed.emit()

    @Slot()
    def applySettings(self):
        # Save theme and other global settings to vault
        creds = self.vault_manager.load_account_credentials()
        creds["theme"] = self._current_theme
        # creds["system_preference_profiles"] = self._system_profiles # Already saved on modify
        self.vault_manager.save_data(json.dumps(creds))
        # Emit generic signal if needed

    @Slot()
    def refreshApplication(self):
         print("Requesting Application Refresh/Relaunch")

    @Slot()
    def resetToDefaults(self):
        print("Resetting defaults")

    def _save_vault(self):
        if self.vault_manager:
            try:
                creds = self.vault_manager.load_account_credentials()
                creds["system_preference_profiles"] = self._system_profiles
                creds["tab_configurations"] = self._tab_defaults_config
                self.vault_manager.save_data(json.dumps(creds))
            except Exception as e:
                print(f"Vault save error: {e}")

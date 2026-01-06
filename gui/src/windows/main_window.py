import os
import sys

from PySide6.QtCore import Qt, QSize, QObject, Property, Slot
from PySide6.QtGui import QIcon, QImageReader

from .settings_window import SettingsWindow
from ..utils.app_definitions import NEW_LIMIT_MB
from backend.src.core.vault_manager import VaultManager


class MainWindow(QObject):
    def __init__(self, vault_manager: VaultManager, dropdown=True, app_icon=None):
        super().__init__()
        from ..tabs import (
            ConvertTab,
            DeleteTab,
            ScanMetadataTab,
            SearchTab,
            ImageExtractorTab,
            MergeTab,
            ImageCrawlTab,
            DriveSyncTab,
            WallpaperTab,
            WebRequestsTab,
            DatabaseTab,
            ReverseImageSearchTab,
            UnifiedTrainTab,
            UnifiedGenerateTab,
            R3GANEvaluateTab,
            MetaCLIPInferenceTab,
        )
        
        # Store the authenticated vault manager instance
        self.vault_manager = vault_manager
        QImageReader.setAllocationLimit(NEW_LIMIT_MB)

        # --- LOAD THEME AND ACCOUNT INFO FROM VAULT (LOAD 1 OF 1) ---
        account_name = "Authenticated User"
        initial_theme = "dark"

        # Load credentials once to get theme and account name
        self.cached_creds = {}

        if self.vault_manager:
            try:
                self.cached_creds = self.vault_manager.load_account_credentials()
                account_name = self.cached_creds.get(
                    "account_name", "Authenticated User"
                )
                initial_theme = self.cached_creds.get("theme", "dark")
            except Exception as e:
                print(f"Warning: Failed to load account credentials or theme: {e}")

        self.current_theme = initial_theme

        self.settings_window = None
        self.account_name = account_name

        # --- Tab Initialization ---
        self.database_tab = DatabaseTab()
        self.search_tab = SearchTab(self.database_tab, dropdown=dropdown)
        self.scan_metadata_tab = ScanMetadataTab(self.database_tab)
        self.convert_tab = ConvertTab(dropdown=dropdown)
        self.merge_tab = MergeTab()
        self.delete_tab = DeleteTab(dropdown=dropdown)
        self.crawler_tab = ImageCrawlTab()
        self.reverse_search_tab = ReverseImageSearchTab()
        self.drive_sync_tab = DriveSyncTab(vault_manager)
        self.wallpaper_tab = WallpaperTab(self.database_tab)
        self.web_requests_tab = WebRequestsTab()
        self.image_extractor_tab = ImageExtractorTab()
        self.train_tab = UnifiedTrainTab()
        self.generate_tab = UnifiedGenerateTab()
        self.eval_tab = R3GANEvaluateTab()
        self.inference_tab = MetaCLIPInferenceTab()

        # --- LINK TABS (Critical for Cross-Tab Communication) ---
        self.database_tab.scan_tab_ref = self.scan_metadata_tab
        self.database_tab.search_tab_ref = self.search_tab
        self.database_tab.merge_tab_ref = self.merge_tab
        self.database_tab.delete_tab_ref = self.delete_tab
        self.database_tab.wallpaper_tab_ref = self.wallpaper_tab

        self.all_tabs = {
            "System Tools": {
                "Convert": self.convert_tab,
                "Merge": self.merge_tab,
                "Delete": self.delete_tab,
                "Extractor": self.image_extractor_tab,
                "Display Wallpaper": self.wallpaper_tab,
            },
            "Database Management": {
                "Database Configuration": self.database_tab,
                "Search Images": self.search_tab,
                "Scan Metadata": self.scan_metadata_tab,
            },
            "Web Integration": {
                "Web Crawler": self.crawler_tab,
                "Web Requests": self.web_requests_tab,
                "Cloud Synchronization": self.drive_sync_tab,
                "Reverse Search": self.reverse_search_tab,
            },
            "Deep Learning": {
                "Training": self.train_tab,
                "Generation": self.generate_tab,
                "Evaluation": self.eval_tab,
                "Inference": self.inference_tab,
            },
        }

        # --- APPLY ACTIVE DEFAULT CONFIGURATIONS ---
        # 1. Retrieve the saved active configurations and the repository of all configs
        active_configs = self.cached_creds.get("active_tab_configs", {})
        saved_tab_configs = self.cached_creds.get("tab_configurations", {})

        # 2. Iterate through all instantiated tabs
        for category, tabs_in_category in self.all_tabs.items():
            for tab_instance in tabs_in_category.values():
                tab_class_name = type(tab_instance).__name__

                # 3. Check if there is an active config set for this tab class
                if tab_class_name in active_configs:
                    config_name = active_configs[tab_class_name]

                    # 4. Retrieve the actual config data (JSON)
                    # The structure is { 'TabClassName': { 'ConfigName': { ...data... } } }
                    if (
                        tab_class_name in saved_tab_configs
                        and config_name in saved_tab_configs[tab_class_name]
                    ):
                        config_data = saved_tab_configs[tab_class_name][config_name]

                        # 5. Apply it if the tab supports set_config
                        if hasattr(tab_instance, "set_config") and callable(
                            tab_instance.set_config
                        ):
                            try:
                                tab_instance.set_config(config_data)
                                print(
                                    f"Applied active config '{config_name}' to {tab_class_name}"
                                )
                            except Exception as e:
                                print(f"Error applying config to {tab_class_name}: {e}")

    @Property(QObject, constant=True)
    def convertTab(self):
        return self.convert_tab

    @Property(QObject, constant=True)
    def databaseTab(self):
        return self.database_tab

    @Property(str, constant=True)
    def accountName(self):
        return self.account_name

    @Property(str, constant=True)
    def currentTheme(self):
        return self.current_theme

    @Slot()
    def open_settings_window(self):
        # Implementation to open QML SettingsWindow would go here
        print("Opening settings window...")

    @Slot()
    def close(self):
        print("Closing application logic...")
        if self.vault_manager:
            self.vault_manager.shutdown()

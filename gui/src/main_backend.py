from PySide6.QtCore import QObject, Property, Slot, Signal
from gui.src.windows.settings_backend import SettingsBackend
from gui.src.windows.log_backend import LogBackend
from gui.src.windows.slideshow_backend import SlideshowBackend
from gui.src.tabs import (
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

class MainBackend(QObject):
    def __init__(self, vault_manager):
        super().__init__()
        self.vault_manager = vault_manager
        
        # Initialize Tabs
        # Note: We pass minimal args where possible. Some tabs depend on others (e.g. search depends on db).
        
        self._database_tab = DatabaseTab()
        self._search_tab = SearchTab(self._database_tab, dropdown=True)
        self._scan_metadata_tab = ScanMetadataTab(self._database_tab)
        
        self._convert_tab = ConvertTab(dropdown=True)
        self._merge_tab = MergeTab()
        self._delete_tab = DeleteTab(dropdown=True)
        self._image_extractor_tab = ImageExtractorTab()
        self._delete_tab = DeleteTab()
        self._merge_tab = MergeTab()
        self._image_extractor_tab = ImageExtractorTab()
        self._wallpaper_tab = WallpaperTab(self._database_tab, self)
        
        self._crawler_tab = ImageCrawlTab()
        self._drive_sync_tab = DriveSyncTab(vault_manager)
        self._web_requests_tab = WebRequestsTab()
        self._reverse_search_tab = ReverseImageSearchTab()
        
        self._train_tab = UnifiedTrainTab()
        self._generate_tab = UnifiedGenerateTab()
        self._eval_tab = R3GANEvaluateTab()
        self._inference_tab = MetaCLIPInferenceTab()

        # Windows Backends
        self._settings_backend = SettingsBackend(self)
        self._log_backend = LogBackend()
        self._slideshow_backend = SlideshowBackend(self)

        # Link Tabs
        self._database_tab.scan_tab_ref = self._scan_metadata_tab
        self._database_tab.search_tab_ref = self._search_tab
        self._database_tab.merge_tab_ref = self._merge_tab
        self._database_tab.delete_tab_ref = self._delete_tab
        self._database_tab.wallpaper_tab_ref = self._wallpaper_tab

        # Cache account name
        self._account_name = "User"
        if self.vault_manager:
            creds = self.vault_manager.load_account_credentials()
            self._account_name = creds.get("account_name", "User")

    @Property(str, constant=True)
    def accountName(self):
        return self._account_name

    # --- Core Properties ---
    @Property(QObject, constant=True)
    def convertTab(self): return self._convert_tab

    @Property(QObject, constant=True)
    def mergeTab(self): return self._merge_tab
    
    @Property(QObject, constant=True)
    def deleteTab(self): return self._delete_tab

    @Property(QObject, constant=True)
    def imageExtractorTab(self): return self._image_extractor_tab
    
    @Property(QObject, constant=True)
    def wallpaperTab(self):
        return self._wallpaper_tab

    @Property(QObject, constant=True)
    def settingsBackend(self):
        return self._settings_backend

    @Property(QObject, constant=True)
    def logBackend(self):
        return self._log_backend

    @Property(QObject, constant=True)
    def slideshowBackend(self):
        return self._slideshow_backend
    
    # --- Methods ---

    # --- Window Management Signals ---
    requestShowSettings = Signal()
    requestShowLog = Signal(str) # str for tab name optional
    requestShowPreview = Signal(str) # path
    requestShowSlideshow = Signal() 

    @Slot()
    def open_settings(self):
        self.requestShowSettings.emit()

    @Slot(str)
    def open_log(self, tab_name="System"):
        self.requestShowLog.emit(tab_name)

    @Slot(str)
    def open_preview(self, path):
        self.requestShowPreview.emit(path)

    @Slot()
    def open_slideshow(self):
        self.requestShowSlideshow.emit()

    # --- Database Properties ---
    @Property(QObject, constant=True)
    def databaseTab(self): return self._database_tab

    @Property(QObject, constant=True)
    def searchTab(self): return self._search_tab

    @Property(QObject, constant=True)
    def scanMetadataTab(self): return self._scan_metadata_tab

    # --- Web Properties ---
    @Property(QObject, constant=True)
    def imageCrawlTab(self): return self._crawler_tab
    
    @Property(QObject, constant=True)
    def driveSyncTab(self): return self._drive_sync_tab

    @Property(QObject, constant=True)
    def webRequestsTab(self): return self._web_requests_tab

    @Property(QObject, constant=True)
    def reverseSearchTab(self): return self._reverse_search_tab

    # --- Models Properties ---
    @Property(QObject, constant=True)
    def trainTab(self): return self._train_tab

    @Property(QObject, constant=True)
    def generateTab(self): return self._generate_tab

    @Property(QObject, constant=True)
    def r3ganEvaluateTab(self): return self._eval_tab

    @Property(QObject, constant=True)
    def metaClipInferenceTab(self): return self._inference_tab

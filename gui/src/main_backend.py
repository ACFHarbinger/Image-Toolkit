from asp_gui.tabs.stitch_tab_backend import StitchTabBackend
from PySide6.QtCore import Property, QObject, Signal, Slot

from gui.src.modules import (
    LIBRARY_DATABASE_SERVICE,
    EventHub,
    LibraryDatabaseService,
    ModuleServices,
)
from gui.src.tabs import (
    ConvertTab,
    DatabaseTab,
    DriveSyncTab,
    EntityReconTab,
    ExtractorTab,
    ImageCrawlTab,
    MergeTab,
    MetaCLIPInferenceTab,
    R3GANEvaluateTab,
    ReverseImageSearchTab,
    ScanMetadataTab,
    SearchTab,
    SimilarityTab,
    UnifiedGenerateTab,
    UnifiedTrainTab,
    WallpaperTab,
    WebRequestsTab,
)
from gui.src.tabs.database.listings_tab import ListingsTab
from gui.src.windows.logging.log_backend import LogBackend
from gui.src.windows.settings.settings_backend import SettingsBackend
from gui.src.windows.slideshow_backend import SlideshowBackend


class MainBackend(QObject):
    def __init__(self, vault_manager):
        super().__init__()
        self.vault_manager = vault_manager

        # Shared non-visual library service + event hub (issue #534): the
        # database-family tabs now depend on the service, never a DatabaseTab
        # widget. Kept in sync with _tab_registry's composition root.
        self.module_event_hub = EventHub(self)
        self.module_services = ModuleServices()
        self.library_database_service = LibraryDatabaseService(vault_manager)
        self.module_services.register(
            LIBRARY_DATABASE_SERVICE, self.library_database_service
        )

        # Initialize Tabs
        self._database_tab = DatabaseTab(
            vault_manager,
            database_service=self.library_database_service,
            event_hub=self.module_event_hub,
        )
        self._search_tab = SearchTab(
            self.library_database_service, self.module_event_hub, dropdown=True
        )
        self._scan_metadata_tab = ScanMetadataTab(
            self.library_database_service, self.module_event_hub
        )

        self._convert_tab = ConvertTab(dropdown=True)
        self._merge_tab = MergeTab()
        # SimilarityTab is the refactored Delete tab (keeps its delete API)
        self._delete_tab = SimilarityTab(dropdown=True)
        self._extractor_tab = ExtractorTab()
        self._wallpaper_tab = WallpaperTab(
            self.library_database_service, self.module_event_hub
        )

        self._crawler_tab = ImageCrawlTab()
        self._drive_sync_tab = DriveSyncTab(vault_manager)
        self._web_requests_tab = WebRequestsTab()
        self._reverse_search_tab = ReverseImageSearchTab()
        self._entity_recon_tab = EntityReconTab()

        self._train_tab = UnifiedTrainTab()
        self._generate_tab = UnifiedGenerateTab()
        self._eval_tab = R3GANEvaluateTab()
        self._inference_tab = MetaCLIPInferenceTab()

        # Listings tab
        self._listings_tab = ListingsTab(vault_manager=vault_manager)

        # Animation tab backends
        self._stitch_tab = StitchTabBackend(self)

        # Windows Backends
        self._settings_backend = SettingsBackend(self)
        self._log_backend = LogBackend()
        self._slideshow_backend = SlideshowBackend(self)

        # Cross-tab coupling removed (issue #534): database-family tabs
        # coordinate via ModuleServices + EventHub intents, not widget refs.

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

    # New canonical name for the refactored tab; deleteTab stays as an alias.
    @Property(QObject, constant=True)
    def similarityTab(self): return self._delete_tab

    @Property(QObject, constant=True)
    def extractorTab(self): return self._extractor_tab

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

    @Property(QObject, constant=True)
    def entityReconTab(self): return self._entity_recon_tab

    # --- Models Properties ---
    @Property(QObject, constant=True)
    def trainTab(self): return self._train_tab

    @Property(QObject, constant=True)
    def generateTab(self): return self._generate_tab

    @Property(QObject, constant=True)
    def r3ganEvaluateTab(self): return self._eval_tab

    @Property(QObject, constant=True)
    def metaClipInferenceTab(self): return self._inference_tab

    # --- Listings Properties ---
    @Property(QObject, constant=True)
    def listingsTab(self): return self._listings_tab

    # --- Animation Properties ---
    @Property(QObject, constant=True)
    def stitchTab(self): return self._stitch_tab

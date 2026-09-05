"""Tab instantiation, cross-tab wiring, and the ``all_tabs`` category map.

Extracted from ``MainWindow.__init__`` -- pure code motion, no logic change.
"""

from __future__ import annotations


class _TabRegistryMixin:
    """Builds every tab instance and the category → {name: tab} map."""

    def _create_tabs(self, dropdown: bool, enable_manager: bool) -> None:
        # Deferred import: these tab modules transitively import a lot of the
        # app, and importing them at gui.src.windows.main module load time
        # would be circular.
        from ...modules import (
            LIBRARY_DATABASE_SERVICE,
            EventHub,
            ImportPathsIntent,
            LibraryDatabaseService,
            ModuleServices,
            NavigateIntent,
        )
        from ...tabs import (
            ComfyUITab,
            ConvertTab,
            DatabaseTab,
            DataBrowserTab,
            DriveSyncTab,
            EntityReconTab,
            ExtractorTab,
            HieEditorTab,
            ImageCrawlTab,
            MangaAnimationTab,
            MangaColorizationTab,
            MangaPuppeteeringTab,
            MediaLoaderTab,
            MergeTab,
            MetaCLIPInferenceTab,
            R3GANEvaluateTab,
            ReverseImageSearchTab,
            ScanMetadataTab,
            SearchTab,
            SimilarityTab,
            StitchTab,
            UnifiedGenerateTab,
            UnifiedTrainTab,
            WallpaperTab,
            WebRequestsTab,
        )
        from ...tabs.database import ListingsTab

        # pyrefly: ignore [missing-attribute]
        vault_manager = self.vault_manager
        self.module_event_hub = EventHub(self)
        self.module_services = ModuleServices()
        self.library_database_service = LibraryDatabaseService(vault_manager)
        self.module_services.register(LIBRARY_DATABASE_SERVICE, self.library_database_service)

        # --- Tab Initialization ---
        self.database_tab = DatabaseTab(
            vault_manager,
            database_service=self.library_database_service,
            event_hub=self.module_event_hub,
        )
        self.data_browser_tab = DataBrowserTab(vault_manager)
        self.search_tab = SearchTab(
            self.library_database_service,
            self.module_event_hub,
            dropdown=dropdown,
        )
        self.scan_metadata_tab = ScanMetadataTab(
            self.library_database_service,
            self.module_event_hub,
        )
        self.convert_tab = ConvertTab(dropdown=dropdown)
        self.merge_tab = MergeTab()
        self.delete_tab = SimilarityTab(dropdown=dropdown)
        self.crawler_tab = ImageCrawlTab()
        self.reverse_search_tab = ReverseImageSearchTab()  # pyrefly: ignore [bad-instantiation]
        self.entity_recon_tab = EntityReconTab()
        self.drive_sync_tab = DriveSyncTab(vault_manager)
        self.media_loader_tab = MediaLoaderTab()
        self.wallpaper_tab = WallpaperTab(
            self.library_database_service,
            self.module_event_hub,
        )
        self.web_requests_tab = WebRequestsTab()
        self.extractor_tab = ExtractorTab()  # pyrefly: ignore [bad-instantiation]
        self.listings_tab = ListingsTab(vault_manager=vault_manager, event_hub=self.module_event_hub)
        self.train_tab = UnifiedTrainTab()
        self.generate_tab = UnifiedGenerateTab()
        self.eval_tab = R3GANEvaluateTab()
        self.inference_tab = MetaCLIPInferenceTab()
        self.comfyui_tab = ComfyUITab(enable_manager=enable_manager)
        self.stitch_tab = StitchTab()
        self.manga_colorization_tab = MangaColorizationTab()
        self.manga_animation_tab = MangaAnimationTab()
        self.manga_puppeteering_tab = MangaPuppeteeringTab()
        self.hie_editor_tab = HieEditorTab()

        # Merge and Similarity have not migrated to lifecycle contracts yet;
        # route their legacy path imports through the hub instead of DatabaseTab.
        self.module_event_hub.subscribe(ImportPathsIntent, self._handle_legacy_path_import, owner=self)
        self.module_event_hub.subscribe(NavigateIntent, self._activate_legacy_module, owner=self)

        self.all_tabs = {
            "System Tools": {
                "Convert": self.convert_tab,
                "Merge": self.merge_tab,
                "Similarity": self.delete_tab,
                "Extractor": self.extractor_tab,
                "Wallpaper": self.wallpaper_tab,
            },
            # Phase DB (DB.6): one category for everything on the unified
            # library store — listings, image search/tagging, maintenance.
            "Library Database": {
                "Listings": self.listings_tab,
                "Image Search": self.search_tab,
                "Scan and Tag": self.scan_metadata_tab,
                "Management": self.database_tab,
                "Data Browser": self.data_browser_tab,
            },
            "Web Integration": {
                "Crawler": self.crawler_tab,
                "Requests": self.web_requests_tab,
                "Cloud Synchronization": self.drive_sync_tab,
                "Media Loader": self.media_loader_tab,
                "Reverse Search": self.reverse_search_tab,
                "Entity Reconnaissance": self.entity_recon_tab,
            },
            "Deep Learning": {
                "Training": self.train_tab,
                "Generation": self.generate_tab,
                "Evaluation": self.eval_tab,
                "Inference": self.inference_tab,
                "ComfyUI": self.comfyui_tab,
            },
            "Image Stitching": {
                "Stitch": self.stitch_tab.stitch_panel,
                "Graph": self.stitch_tab.graph_panel,
                "Adjust": self.stitch_tab.adjust_panel,
                "Canvas": self.stitch_tab.canvas_panel,
                "Statistics": self.stitch_tab.stats_panel,
                "Sequence Builder": self.stitch_tab.seq_builder_panel,
                "Hybrid Stitch": self.stitch_tab.hybrid_stitch_panel,
                "Animation Clusters": self.stitch_tab.anim_clusters_panel,
            },
            "Manga": {
                "Colorization": self.manga_colorization_tab,
                "Animation": self.manga_animation_tab,
                "Puppeteering": self.manga_puppeteering_tab,
            },
            "Image Editor": {
                "Hybrid Editor": self.hie_editor_tab,
            },
        }

    def _activate_legacy_module(self, intent) -> None:
        """Temporary old-shell router while ModuleRuntime is not mounted."""
        targets = {
            "library.listings": ("Library Database", "Listings"),
            "library.search": ("Library Database", "Image Search"),
            "library.scan": ("Library Database", "Scan and Tag"),
            "system.merge": ("System Tools", "Merge"),
            "system.similarity": ("System Tools", "Similarity"),
            "system.wallpaper": ("System Tools", "Wallpaper"),
        }
        target = targets.get(intent.module_id)
        if target is None:
            return
        category, tab_name = target
        self.command_combo.setCurrentText(category)
        self._select_tab_by_name(tab_name)

    def _handle_legacy_path_import(self, intent) -> None:
        if intent.module_id == "system.merge":
            self.merge_tab.display_scan_results(list(intent.paths))
        elif intent.module_id == "system.similarity":
            self.delete_tab.clear_galleries()
            self.delete_tab.duplicate_results = {"imported": list(intent.paths)}
            self.delete_tab.status_label.setText(f"Imported {len(intent.paths)} files from Search.")
            self.delete_tab.start_loading_thumbnails(list(intent.paths))


__all__ = ["_TabRegistryMixin"]

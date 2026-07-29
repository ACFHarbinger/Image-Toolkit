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
        from ....tabs import (
            ComfyUITab,
            ConvertTab,
            DatabaseTab,
            DriveSyncTab,
            EntityReconTab,
            ExtractorTab,
            ImageCrawlTab,
            ListingsTab,
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

        vault_manager = self.vault_manager

        # --- Tab Initialization ---
        self.database_tab = DatabaseTab(vault_manager)
        self.search_tab = SearchTab(self.database_tab, dropdown=dropdown)
        self.scan_metadata_tab = ScanMetadataTab(self.database_tab)  # pyrefly: ignore [bad-instantiation]
        self.convert_tab = ConvertTab(dropdown=dropdown)
        self.merge_tab = MergeTab()
        self.delete_tab = SimilarityTab(dropdown=dropdown)
        self.crawler_tab = ImageCrawlTab()
        self.reverse_search_tab = ReverseImageSearchTab()  # pyrefly: ignore [bad-instantiation]
        self.entity_recon_tab = EntityReconTab()
        self.drive_sync_tab = DriveSyncTab(vault_manager)
        self.wallpaper_tab = WallpaperTab(self.database_tab)
        self.web_requests_tab = WebRequestsTab()
        self.extractor_tab = ExtractorTab()  # pyrefly: ignore [bad-instantiation]
        self.listings_tab = ListingsTab(vault_manager=vault_manager)
        self.train_tab = UnifiedTrainTab()
        self.generate_tab = UnifiedGenerateTab()
        self.eval_tab = R3GANEvaluateTab()
        self.inference_tab = MetaCLIPInferenceTab()
        self.comfyui_tab = ComfyUITab(enable_manager=enable_manager)
        self.stitch_tab = StitchTab()

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
                "Maintenance": self.database_tab,
            },
            "Web Integration": {
                "Crawler": self.crawler_tab,
                "Requests": self.web_requests_tab,
                "Cloud Synchronization": self.drive_sync_tab,
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
        }


__all__ = ["_TabRegistryMixin"]

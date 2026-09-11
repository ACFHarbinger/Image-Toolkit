"""Tab instantiation, cross-tab wiring, and the ``all_tabs`` category map.

Classic construction is lazy per category (R2.e / #566): ``_create_tabs``
registers services and the title map, then ``_ensure_category`` builds tabs
through ``build_tab`` on first select.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger(__name__)

# module_id, category, title, live_expression, factory_id
# factory_id is the R1.4 ``build_tab`` key; Image Stitching routes share one
# StitchTab workspace. Keep this table in lockstep with the inventory in
# docs/moon/roadmaps/gui_refactoring.md §2.4 (test_legacy_module_inventory).
CLASSIC_TAB_ROUTES = (
    ("system.convert", "System Tools", "Convert", "self.convert_tab", "system.convert"),
    ("system.merge", "System Tools", "Merge", "self.merge_tab", "system.merge"),
    ("system.similarity", "System Tools", "Similarity", "self.delete_tab", "system.similarity"),
    ("system.extractor", "System Tools", "Extractor", "self.extractor_tab", "system.extractor"),
    ("system.wallpaper", "System Tools", "Wallpaper", "self.wallpaper_tab", "system.wallpaper"),
    ("library.listings", "Library Database", "Listings", "self.listings_tab", "library.listings"),
    ("library.search", "Library Database", "Image Search", "self.search_tab", "library.search"),
    ("library.scan", "Library Database", "Scan and Tag", "self.scan_metadata_tab", "library.scan"),
    ("library.management", "Library Database", "Management", "self.database_tab", "library.management"),
    ("library.data-browser", "Library Database", "Data Browser", "self.data_browser_tab", "library.data-browser"),
    ("web.crawler", "Web Integration", "Crawler", "self.crawler_tab", "web.crawler"),
    ("web.requests", "Web Integration", "Requests", "self.web_requests_tab", "web.requests"),
    ("web.drive-sync", "Web Integration", "Cloud Synchronization", "self.drive_sync_tab", "web.drive-sync"),
    ("web.media-loader", "Web Integration", "Media Loader", "self.media_loader_tab", "web.media-loader"),
    ("web.reverse-search", "Web Integration", "Reverse Search", "self.reverse_search_tab", "web.reverse-search"),
    ("web.entity-recon", "Web Integration", "Entity Reconnaissance", "self.entity_recon_tab", "web.entity-recon"),
    ("ml.training", "Deep Learning", "Training", "self.train_tab", "ml.training"),
    ("ml.generation", "Deep Learning", "Generation", "self.generate_tab", "ml.generation"),
    ("ml.evaluation", "Deep Learning", "Evaluation", "self.eval_tab", "ml.evaluation"),
    ("ml.inference", "Deep Learning", "Inference", "self.inference_tab", "ml.inference"),
    ("ml.comfyui", "Deep Learning", "ComfyUI", "self.comfyui_tab", "ml.comfyui"),
    ("stitch.stitch", "Image Stitching", "Stitch", "self.stitch_tab.stitch_panel", "stitch.workspace"),
    ("stitch.graph", "Image Stitching", "Graph", "self.stitch_tab.graph_panel", "stitch.workspace"),
    ("stitch.adjust", "Image Stitching", "Adjust", "self.stitch_tab.adjust_panel", "stitch.workspace"),
    ("stitch.canvas", "Image Stitching", "Canvas", "self.stitch_tab.canvas_panel", "stitch.workspace"),
    ("stitch.statistics", "Image Stitching", "Statistics", "self.stitch_tab.stats_panel", "stitch.workspace"),
    (
        "stitch.sequence-builder",
        "Image Stitching",
        "Sequence Builder",
        "self.stitch_tab.seq_builder_panel",
        "stitch.workspace",
    ),
    ("stitch.hybrid", "Image Stitching", "Hybrid Stitch", "self.stitch_tab.hybrid_stitch_panel", "stitch.workspace"),
    (
        "stitch.animation-clusters",
        "Image Stitching",
        "Animation Clusters",
        "self.stitch_tab.anim_clusters_panel",
        "stitch.workspace",
    ),
    ("manga.colorization", "Manga", "Colorization", "self.manga_colorization_tab", "manga.colorization"),
    ("manga.animation", "Manga", "Animation", "self.manga_animation_tab", "manga.animation"),
    ("manga.puppeteering", "Manga", "Puppeteering", "self.manga_puppeteering_tab", "manga.puppeteering"),
    ("editor.hybrid", "Image Editor", "Hybrid Editor", "self.hie_editor_tab", "editor.hybrid"),
)


def _expression_parts(expression: str) -> tuple[str, str | None]:
    parts = expression.split(".")
    if len(parts) < 2 or parts[0] != "self":
        raise ValueError(f"unsupported live expression: {expression!r}")
    if len(parts) == 2:
        return parts[1], None
    return parts[1], parts[2]


def classic_category_order() -> list[str]:
    ordered: list[str] = []
    for _module_id, category, _title, _expression, _factory_id in CLASSIC_TAB_ROUTES:
        if category not in ordered:
            ordered.append(category)
    return ordered


def classic_factory_ids_for(category: str) -> list[str]:
    ids: list[str] = []
    for _module_id, route_category, _title, _expression, factory_id in CLASSIC_TAB_ROUTES:
        if route_category == category and factory_id not in ids:
            ids.append(factory_id)
    return ids


class _TabRegistryMixin:
    """Builds tab instances lazily and the category → {name: tab} map."""

    def _create_tabs(self, dropdown: bool, enable_manager: bool) -> None:
        # Deferred import: tab modules transitively import a lot of the app.
        from ...modules import (
            LIBRARY_DATABASE_SERVICE,
            EventHub,
            ImportPathsIntent,
            LibraryDatabaseService,
            ModuleContext,
            ModuleServices,
            NavigateIntent,
        )

        vault_manager = self.vault_manager
        self.module_event_hub = EventHub(self)
        self.module_services = ModuleServices()
        self.module_services.register("vault_manager", vault_manager)
        self.library_database_service = LibraryDatabaseService(vault_manager)
        self.module_services.register(LIBRARY_DATABASE_SERVICE, self.library_database_service)
        self.module_context = ModuleContext(
            event_hub=self.module_event_hub,
            services=self.module_services,
            dropdown=dropdown,
            enable_manager=enable_manager,
        )

        self._constructed_categories: set[str] = set()
        self._classic_construction_log: list[tuple[str, str, float]] = []
        self._pending_tab_configs: dict[str, Any] = {}
        self._lazy_recovery_level: str = "None"

        self.all_tabs: dict[str, dict[str, Any]] = {category: {} for category in classic_category_order()}
        for _module_id, category, title, expression, _factory_id in CLASSIC_TAB_ROUTES:
            attr, _panel = _expression_parts(expression)
            if not hasattr(self, attr):
                setattr(self, attr, None)
            self.all_tabs[category][title] = None

        self.module_event_hub.subscribe(ImportPathsIntent, self._handle_legacy_path_import, owner=self)
        self.module_event_hub.subscribe(NavigateIntent, self._activate_legacy_module, owner=self)

    def _begin_classic_tab_construction(self) -> None:
        """End the init deferral and build the currently selected category."""
        if not getattr(self, "_classic_defer_construction", False):
            if not getattr(self, "_constructed_categories", None):
                combo = getattr(self, "command_combo", None)
                if combo is not None:
                    self.on_command_changed(combo.currentText())
            return
        self._classic_defer_construction = False
        combo = getattr(self, "command_combo", None)
        if combo is not None:
            self.on_command_changed(combo.currentText())

    def _ensure_category(self, category: str) -> None:
        """Construct every tab in *category* via ``build_tab`` if needed."""
        if not category or category in self._constructed_categories:
            return
        if category not in self.all_tabs:
            return

        from ...modules import build_tab

        built_factory_ids: set[str] = set()
        for _module_id, route_category, title, expression, factory_id in CLASSIC_TAB_ROUTES:
            if route_category != category:
                continue
            attr, panel = _expression_parts(expression)
            if factory_id not in built_factory_ids:
                started = time.perf_counter()
                widget = build_tab(factory_id, self.module_context)
                elapsed = time.perf_counter() - started
                setattr(self, attr, widget)
                built_factory_ids.add(factory_id)
                self._classic_construction_log.append((category, factory_id, elapsed))
                logger.info("classic category %r built %s in %.3fs", category, factory_id, elapsed)
            host = getattr(self, attr)
            page = getattr(host, panel) if panel else host
            self.all_tabs[category][title] = page
            self._apply_lazy_tab_hooks(page)

        self._constructed_categories.add(category)
        if hasattr(self, "_apply_wallpaper_slideshow_prefs") and category == "System Tools":
            self._apply_wallpaper_slideshow_prefs()

    def _apply_lazy_tab_hooks(self, tab: Any) -> None:
        if tab is None:
            return
        apply_prefs = getattr(self, "_apply_gallery_prefs_to_tab", None)
        if callable(apply_prefs):
            prefs = getattr(self, "cached_creds", {}).get("preferences", {}) or {}
            if prefs:
                apply_prefs(tab, prefs)
        pending = getattr(self, "_pending_tab_configs", None) or {}
        if not pending or not getattr(self, "_lazy_configs_primed", False):
            return
        level = getattr(self, "_lazy_recovery_level", "None")
        if level == "All Tabs":
            restore = getattr(self, "_restore_tab_config_instance", None)
            if callable(restore):
                restore(tab, pending, " (lazy category)")

    def _iter_live_tabs(self) -> Iterator[Any]:
        for pages in self.all_tabs.values():
            for tab in pages.values():
                if tab is not None:
                    yield tab

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
            self._ensure_category("System Tools")
            self.merge_tab.display_scan_results(list(intent.paths))
        elif intent.module_id == "system.similarity":
            self._ensure_category("System Tools")
            self.delete_tab.clear_galleries()
            self.delete_tab.duplicate_results = {"imported": list(intent.paths)}
            self.delete_tab.status_label.setText(f"Imported {len(intent.paths)} files from Search.")
            self.delete_tab.start_loading_thumbnails(list(intent.paths))


__all__ = ["CLASSIC_TAB_ROUTES", "_TabRegistryMixin", "classic_category_order", "classic_factory_ids_for"]

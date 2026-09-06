# Legacy Module and Route Inventory (2026 Q3)

**Status:** Baseline for #509, now re-landed and shipped (2026-09-06) —
see `docs/moon/roadmaps/ui_architecture_2026q3.md`'s status block for
the full crash/revert/re-land history. This table describes the
**classic shell's** eager `_tab_registry.py` state, which stays live
and default (the runtime shell mounts behind the `experimental/
runtime_shell` `PreferenceStore` flag, off by default, until §6's
fallback-retirement question is decided) — so the table itself remains
accurate for its stated purpose. `gui/test/modules/
test_legacy_module_inventory.py` (recreated in the re-land) still
passes against it. The "Direct-object coupling" sections below describe
the classic path specifically; the re-landed typed-intent/
`LibraryDatabaseService` alternative now lives permanently in
`gui/src/main_backend.py`/`gui/src/modules/library_service.py`, active
only when the runtime shell is enabled.

## Construction baseline

`_TabRegistryMixin._create_tabs()` imports 25 names from `gui.src.tabs`, one
additional `ListingsTab` symbol, and directly constructs 26 top-level tab
objects before the window shows. All 33 navigable routes are therefore eager
today. The eight Image Stitching routes are views owned by one `StitchTab`, not
eight independently constructible modules.

Per-module import timings are intentionally not inferred from this inventory:
the aggregate import is entangled with optional ML/submodule dependencies.
#510's lazy-runtime benchmark must measure cold activation and cached
reactivation for representative lightweight, database, stitching, and ML
routes on the same machine.

## Route inventory

| Module ID | Category | Current title | Live expression | Runtime kind |
|---|---|---|---|---|
| system.convert | System Tools | Convert | self.convert_tab | page |
| system.merge | System Tools | Merge | self.merge_tab | page |
| system.similarity | System Tools | Similarity | self.delete_tab | page |
| system.extractor | System Tools | Extractor | self.extractor_tab | page |
| system.wallpaper | System Tools | Wallpaper | self.wallpaper_tab | page |
| library.listings | Library Database | Listings | self.listings_tab | page |
| library.search | Library Database | Image Search | self.search_tab | page |
| library.scan | Library Database | Scan and Tag | self.scan_metadata_tab | page |
| library.management | Library Database | Management | self.database_tab | page |
| library.data-browser | Library Database | Data Browser | self.data_browser_tab | page |
| web.crawler | Web Integration | Crawler | self.crawler_tab | page |
| web.requests | Web Integration | Requests | self.web_requests_tab | page |
| web.drive-sync | Web Integration | Cloud Synchronization | self.drive_sync_tab | page |
| web.media-loader | Web Integration | Media Loader | self.media_loader_tab | page |
| web.reverse-search | Web Integration | Reverse Search | self.reverse_search_tab | page |
| web.entity-recon | Web Integration | Entity Reconnaissance | self.entity_recon_tab | page |
| ml.training | Deep Learning | Training | self.train_tab | page |
| ml.generation | Deep Learning | Generation | self.generate_tab | page |
| ml.evaluation | Deep Learning | Evaluation | self.eval_tab | page |
| ml.inference | Deep Learning | Inference | self.inference_tab | page |
| ml.comfyui | Deep Learning | ComfyUI | self.comfyui_tab | page |
| stitch.stitch | Image Stitching | Stitch | self.stitch_tab.stitch_panel | route:stitch |
| stitch.graph | Image Stitching | Graph | self.stitch_tab.graph_panel | route:stitch |
| stitch.adjust | Image Stitching | Adjust | self.stitch_tab.adjust_panel | route:stitch |
| stitch.canvas | Image Stitching | Canvas | self.stitch_tab.canvas_panel | route:stitch |
| stitch.statistics | Image Stitching | Statistics | self.stitch_tab.stats_panel | route:stitch |
| stitch.sequence-builder | Image Stitching | Sequence Builder | self.stitch_tab.seq_builder_panel | route:stitch |
| stitch.hybrid | Image Stitching | Hybrid Stitch | self.stitch_tab.hybrid_stitch_panel | route:stitch |
| stitch.animation-clusters | Image Stitching | Animation Clusters | self.stitch_tab.anim_clusters_panel | route:stitch |
| manga.colorization | Manga | Colorization | self.manga_colorization_tab | page |
| manga.animation | Manga | Animation | self.manga_animation_tab | page |
| manga.puppeteering | Manga | Puppeteering | self.manga_puppeteering_tab | page |
| editor.hybrid | Image Editor | Hybrid Editor | self.hie_editor_tab | page |

## Direct-object coupling baseline (classic shell, default path)

Constructor-time dependencies require a live database widget:
`SearchTab(database_tab)`, `ScanMetadataTab(database_tab)`, and
`WallpaperTab(database_tab)`. After construction, `DatabaseTab` retains direct
references to Scan, Search, Merge, Similarity, Wallpaper, and Listings;
`DatabaseTab` and `ListingsTab` retain `main_window_ref` for navigation.
This is the classic shell's own coupling and is unaffected by the
runtime shell's parallel path below — it's what Phase 2's tab-mixin
migration (`ui-arch-21`/#531) will eventually replace outright, once the
runtime shell (or its successor) is the sole shell.

## Typed-intent alternative (runtime shell path, ui-arch-11/#534, shipped)

`SearchTab`, `ScanMetadataTab`, and `WallpaperTab` also accept an
optional `(database_service, event_hub)` pair — `LibraryDatabaseService`
(database handle + vault session, never a `QWidget`) plus typed
navigation/filter/path-import intents, with database availability and
catalog changes delivered as facts. `gui/src/main_backend.py` and
`gui/src/windows/main/_tab_registry.py` (when the runtime shell is
active) both inject the shared instance; the classic shell's direct
`database_tab` construction (above) is the fallback when neither is
supplied, keeping both paths live in the same tab classes rather than
forking them.

## Contract

`gui/test/modules/test_legacy_module_inventory.py` statically compares this
table to the live `all_tabs` dictionary and asserts the documented eager-import
and direct-reference baseline for the classic shell. A route rename, addition,
removal, or coupling change must update this inventory deliberately.
Recreated verbatim during the re-land after being lost in the `7559b1d2`
revert; passes against current `_tab_registry.py`.

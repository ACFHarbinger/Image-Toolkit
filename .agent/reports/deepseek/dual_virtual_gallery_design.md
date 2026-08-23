# Dual-Panel Virtual Gallery (`VirtualDualGallery`) Design & Adoption Architecture

## 1. Executive Summary & Context

`AbstractClassTwoGalleries` is the base class for tabs with linked **Found** and **Selected** panels (`SimilarityTab`, `SearchTab`, `ScanMetadataTab`, `FormatSubTab`, `CodecSubTab`, `SamplerSubTab`). 

Currently, `AbstractClassTwoGalleries` relies on a bounded-page `QGridLayout` + `ClickableLabel` architecture with:
1. **Page-cap constraints** (e.g., 100/200/500 items per page) to avoid runaway widget allocation.
2. **Sequential UI rebuild timers** (`_populate_found_timer`, `_populate_found_step`) that churn Qt widgets on page flips.
3. **Synchronous layout clears** (`_clear_layout`, `deleteLater`) that cause heap pressure and PySide binding crashes (issue #461).

With `VirtualGallery` (`QListView` in `IconMode` backed by `VirtualGalleryModel` with lazy `QThreadPool` loading and `LRUImageCache`), viewport culling renders widget cost constant regardless of item count (1,000 or 100,000 files).

This design specification details how `AbstractClassTwoGalleries` tabs adopt `VirtualGallery` through the **`VirtualDualGallery`** composite widget.

---

## 2. Structural Analysis: Single vs. Two-Gallery Tabs

| Property | Single Gallery (`ReverseImageSearchTab`, `ExtractorTab`) | Two-Gallery Tabs (`SimilarityTab`, `SearchTab`, etc.) |
| :--- | :--- | :--- |
| **Viewports** | 1 (`VirtualGallery`) | 2 (`Found` + `Selected`) |
| **Path Pools** | 1 (`gallery_image_paths`) | 2 (`master_found_files` / filtered `found_files` vs. `selected_files`) |
| **Ordering** | Sorted by single sort key / scan discovery | Found is sorted; Selected preserves user insertion or drag-reorder sequence |
| **Search / Filter** | Filters the single gallery in-place | Filtering Found must **not** clear or modify Selected |
| **Selection Behavior** | Highlight within same view | Clicking in Found stages image into Selected; Deselecting removes from Selected |
| **Thumbnail Caching** | Local `LRUImageCache` | Must share a single `LRUImageCache` to prevent duplicate decodes |

---

## 3. Design Decision: Composite `VirtualDualGallery` vs. `QSortFilterProxyModel`

### Evaluated Alternatives

1. **Option 1: Single Model + Dual `QSortFilterProxyModel`**
   - Single list model storing all items with a `selected` boolean attribute.
   - Found view uses a proxy filtering on `search_query`; Selected view uses a proxy filtering on `selected == True`.
   - **Trade-off / Rejection Reason**: In two-gallery workflows, users drag-and-drop to reorder `selected_files` independently of the underlying directory or sort order in Found. Forcing a proxy model to preserve arbitrary, user-reordered indices while Found is dynamically filtered or resorted introduces severe synchronization complexity and state fragility.

2. **Option 2: Composed Dual `VirtualGallery` with Shared Cache (Adopted)**
   - Top panel owns `found_gallery: VirtualGallery`.
   - Bottom panel owns `selected_gallery: VirtualGallery`.
   - Both models share the **exact same `LRUImageCache` instance** (`_shared_cache`), preventing redundant background thumbnail decodes.
   - Independent path lists: `_filtered_found_paths` (sorted/filtered) and `_selected_paths` (insertion/reordered).
   - Coordinated selection signals: clicks on Found toggle inclusion in `_selected_paths` and update Selected view instantly without rebuilds.

---

## 4. Prototype Architecture (`gui/src/components/virtual_gallery/dual_widget.py`)

### Component Structure

```
VirtualDualGallery (QWidget)
 ├── QSplitter (Vertical / Horizontal)
 │    ├── Found Panel (QWidget)
 │    │    ├── Found Header (Title Badge + QLineEdit Filter + Select All)
 │    │    └── found_gallery (VirtualGallery -> VirtualGalleryModel)
 │    └── Selected Panel (QWidget)
 │         ├── Selected Header (Title Badge + Deselect All + Compare Selected)
 │         └── selected_gallery (VirtualGallery -> VirtualGalleryModel)
 └── _shared_cache (LRUImageCache) [Shared by both models]
```

### Key Interfaces

- **Data Ingestion**: `set_found_paths(paths)`, `set_selected_paths(paths)`.
- **Selection Operations**: `select_all()`, `deselect_all()`, `toggle_selection(path)`, `remove_selected(path)`.
- **Filtering**: Live search input with 200ms debouncing filtering `_master_found_paths` -> `_filtered_found_paths`.
- **Lifecycle & Cache**: `cancel_loading()`, `clear_cache()`, `clear()`.
- **Comparison Integration (§2.27)**: `compare_selected()` launches `ImageCompareWindow` for selected files.

---

## 5. Tab Migration Sequencing Plan

When migrating tabs from `AbstractClassTwoGalleries` to `VirtualDualGallery`, the following phased approach is recommended:

1. **Phase 1: `SimilarityTab` (`gui/src/tabs/core/similarity_tab/`)**
   - Cleanest candidate: processes duplicate/similarity groups, stages selected duplicates for deletion/merge.
   - Replace manual card grid with `VirtualDualGallery`.
2. **Phase 2: Convert Subtabs (`FormatSubTab`, `CodecSubTab`, `SamplerSubTab`)**
   - Batch conversion input staging tabs.
3. **Phase 3: `ScanMetadataTab` (`gui/src/tabs/database/scan_metadata_tab/`)**
   - High item count (~10k+ files). Eliminates sequential population timers entirely.
4. **Phase 4: `SearchTab` (`gui/src/tabs/database/search_tab/`)**
   - Integrates SQLCipher / FTS5 search queries directly into `set_found_paths`.

---

## 6. Verification & Test Suite

Unit tests in `gui/test/components/test_virtual_dual_gallery.py` (5 tests):
- `test_dual_gallery_init` — verifies cache sharing and widget setup.
- `test_dual_gallery_population_and_selection` — tests select/deselect/toggle flows.
- `test_dual_gallery_search_filtering` — tests independent search filtering without affecting Selected.
- `test_dual_gallery_compare_selected` — verifies §2.27 multi-image comparison integration.
- `test_dual_gallery_clear_and_lifecycle` — verifies clean thread cancellation and cache clearing.

# GUI/UX Roadmap — Desktop Interface Quality & Ergonomics

---

## Table of Contents

- [How to Use This Document](#how-to-use-this-document)
- [2.1 Virtual Scroll Gallery](#21-virtual-scroll-gallery)
- [2.2 Gallery Thumbnail Size Control](#22-gallery-thumbnail-size-control)
- [2.3 Keyboard Navigation](#23-keyboard-navigation)
- [2.4 Bulk Selection and Operations](#24-bulk-selection-and-operations)
- [2.5 Session Persistence](#25-session-persistence)
- [2.6 Stitch Tab UX — Before/After Comparison](#26-stitch-tab-ux--beforeafter-comparison)
- [2.7 Progress and Cancellation](#27-progress-and-cancellation)
- [2.8 Theme Support](#28-theme-support)
- [2.9 Settings Window Extensions](#29-settings-window-extensions)
- [2.10 In-App Toast Notification System](#210-in-app-toast-notification-system)
- [2.11 Image Preview Window Enhancements](#211-image-preview-window-enhancements)
- [2.12 System Tray Integration](#212-system-tray-integration)
- [2.13 Gallery Filtering and Sort Controls](#213-gallery-filtering-and-sort-controls)
- [2.14 Thumbnail Metadata Overlay](#214-thumbnail-metadata-overlay)
- [2.15 Undo/Redo for Destructive Operations](#215-undoredo-for-destructive-operations)
- [2.16 Command Palette / Quick Launcher](#216-command-palette--quick-launcher)
- [2.17 Global Collapsible Log Panel](#217-global-collapsible-log-panel)
- [2.18 Image Rating and Color Labels](#218-image-rating-and-color-labels)
- [2.19 Gallery Export and Contact Sheet](#219-gallery-export-and-contact-sheet)
- [2.20 Resizable Sidebar Panels and QSplitter Persistence](#220-resizable-sidebar-panels-and-qsplitter-persistence)
- [2.21 Directory Navigation History](#221-directory-navigation-history-back--forward)
- [2.22 Tag Chip UI and Compound Tag Search](#222-tag-chip-ui-and-compound-tag-search)
- [2.23 Accessibility and Keyboard Tab Order](#223-accessibility-and-keyboard-tab-order)
- [2.24 Thumbnail Hover Animations](#224-thumbnail-hover-animations)
- [2.25 Keyboard Shortcut Discovery Overlay](#225-keyboard-shortcut-discovery-overlay)
- [2.26 Inline Rename](#226-inline-rename)
- [2.27 Multi-Image Comparison View ✅](#227-multi-image-comparison-view)
- [2.28 Global Cross-Tab Search](#228-global-cross-tab-search)
- [2.29 Configurable Keyboard Shortcuts](#229-configurable-keyboard-shortcuts)
- [2.30 Accent Color and UI Density Customization](#230-accent-color-and-ui-density-customization)
- [2.31 Custom QSS User Theme Override](#231-custom-qss-user-theme-override)
- [2.32 Window Layout and State Profiles](#232-window-layout-and-state-profiles)
- [2.33 Extractor Tab Playback Engine — libmpv Integration](#233-extractor-tab-playback-engine--libmpv-integration)
- [2.34 Custom Theme Engine & Semantic Color System](#234-custom-theme-engine--semantic-color-system)
- [2.35 Full-Window Background Canvas & Glassmorphic Layering](#235-full-window-background-canvas--glassmorphic-layering)
- [2.36 Dual Navigation Shell & Modular Module Architecture](#236-dual-navigation-shell--modular-module-architecture)
- [2.37 Anime Creative Suite Visual System & Presets](#237-anime-creative-suite-visual-system--presets)
- [2.38 Universal Collapsible Context Inspector Panel](#238-universal-collapsible-context-inspector-panel)
- [2.39 Rich Telemetry Status Bar & System Monitoring](#239-rich-telemetry-status-bar--system-monitoring)
- [2.40 Advanced Gallery Presentation Modes & Custom Thumbnail Overlays](#240-advanced-gallery-presentation-modes--custom-thumbnail-overlays)
- [Effort × Impact Matrix](#effort--impact-matrix)
- [Anchor Index](#anchor-index)

---

## Implementation Timeline

> **Legend** — *Node fill:* new feature (blue) · augmentation (violet) · performance (orange) — *Node border:* ✅ complete (green, thick) · 🔄 in-progress (amber, thick) · ⬜ planned (slate, thin) — *Edges:* `==>` critical prerequisite · `-->` sequential dependency · `---` complements

```mermaid
flowchart LR
    %% ── TYPE classes (node fill = element type) ─────────────────────────────
    classDef feature     fill:#2563eb,color:#fff
    classDef augment     fill:#7c3aed,color:#fff
    classDef fix         fill:#dc2626,color:#fff
    classDef infra       fill:#0891b2,color:#fff
    classDef perf        fill:#ea580c,color:#fff
    classDef research    fill:#475569,color:#fff
    classDef security    fill:#7f1d1d,color:#fff
    classDef refactor    fill:#0f766e,color:#fff
    classDef migration   fill:#4338ca,color:#fff
    classDef testing     fill:#a16207,color:#fff
    classDef docs        fill:#15803d,color:#fff
    classDef integration fill:#9d174d,color:#fff
    %% ── STATUS classes (node border = implementation status) ─────────────────
    classDef done        stroke:#16a34a,stroke-width:4px
    classDef active      stroke:#d97706,stroke-width:4px
    classDef planned     stroke:#64748b,stroke-width:2px
    classDef blocked     stroke:#dc2626,stroke-width:3px
    classDef hold        stroke:#9333ea,stroke-width:3px

    subgraph GC["🖼️ Gallery Core"]
        direction TB
        S21["§2.1 Virtual Scroll Gallery"]:::perf:::planned
        S22["§2.2 Thumbnail Size Control ✅"]:::augment:::done
        S23["§2.3 Keyboard Navigation ✅p"]:::augment:::active
        S24["§2.4 Bulk Selection ✅p"]:::feature:::active
        S213["§2.13 Filter & Sort Controls ✅p"]:::feature:::active
        S214["§2.14 Metadata Overlay ✅p"]:::augment:::active
        S21 ==> S22
        S21 --> S213
        S21 --> S214
        S23 --- S24
    end

    subgraph WF["⚡ Workflow & Productivity"]
        direction TB
        S25["§2.5 Session Persistence ✅"]:::augment:::done
        S27["§2.7 Progress & Cancel ✅p"]:::augment:::active
        S215["§2.15 Undo/Redo ✅"]:::feature:::done
        S216["§2.16 Command Palette ✅p"]:::feature:::active
        S221["§2.21 Dir Nav History ✅p"]:::augment:::active
        S222["§2.22 Tag Chip UI ✅p"]:::feature:::active
        S227["§2.27 Multi-Image Compare ✅"]:::feature:::done
        S228["§2.28 Global Search ✅"]:::feature:::done
        S222 --> S228
        S216 --> S228
    end

    subgraph SYS["🔔 Notifications & System"]
        direction TB
        S28["§2.8 Theme Support"]:::feature:::planned
        S29["§2.9 Settings Window"]:::augment:::planned
        S210["§2.10 Toast Notifications ✅p"]:::feature:::active
        S212["§2.12 System Tray ✅p"]:::feature:::active
        S217["§2.17 Log Panel ✅p"]:::feature:::active
        S229["§2.29 Configurable Shortcuts ✅"]:::augment:::done
        S212 --- S217
    end

    subgraph VIS["🎨 Visual Customisation"]
        direction TB
        S218["§2.18 Image Rating ✅p"]:::feature:::active
        S225["§2.25 Shortcut Overlay ✅p"]:::feature:::active
        S230["§2.30 Accent Color ✅"]:::augment:::done
        S231["§2.31 Custom QSS Theme ✅"]:::augment:::done
        S232["§2.32 Layout Profiles ✅p"]:::augment:::active
        S234["§2.34 Custom Theme Engine ✅p"]:::feature:::active
        S235["§2.35 Background Canvas & Glass ✅p"]:::feature:::active
        S237["§2.37 Anime Creative Suite Presets"]:::feature:::planned
        S230 --- S231
        S234 --> S235
        S234 --> S237
    end

    subgraph ARCH["🏛️ Modular Shell & Creative Studio"]
        direction TB
        S236["§2.36 Dual Navigation Shell & Module Registry"]:::feature:::planned
        S238["§2.38 Universal Context Inspector Panel"]:::feature:::planned
        S239["§2.39 Telemetry Status Bar"]:::augment:::planned
        S240["§2.40 Gallery Presentation & Custom Overlays"]:::augment:::planned
        S236 ==> S238
        S236 --> S239
        S238 --- S240
    end

    %% Cross-group dependencies
    S28 --> S230
    S28 --> S231
    S216 --- S229
    S25 --- S232
    S216 ==> S236
    S237 --- S236
    S214 --> S240
```

Each node's **fill colour** shows element type: blue = new feature, violet = augmentation, orange = performance optimisation. The **border colour** shows implementation status: thick green = complete, thick amber = partially shipped (✅p), thin slate = not yet started. **Edge style** encodes relationship: `==>` critical prerequisite (must land first), `-->` sequential dependency, `---` complements (parallel work).

---

## How to Use This Document

Each section describes an ergonomic pain point, all viable implementation options with trade-offs, and a recommendation. Items tagged **[Quick Win]** take under a day. Items tagged **[Research]** require prototyping.

**Critical constraint:** Never use `QWebEngineView` (QtWebEngine/Chromium). Opening URLs must use `QDesktopServices.openUrl()`. All heavy operations must run off the main thread (QThread/QRunnable). See MEMORY.md for the JVM + native dialog SIGSEGV context.

---

## 2.1 Virtual Scroll Gallery ✅ Partial (2026-08-22 — prototype + 10 tabs migrated; Listings stays on Option C)

**2026-08-19 update:** a perf pass (issues #444/#445/#447) fixed several
real bugs in the current page-based system — thumbnails were being
decoded twice per image, the loading pipeline drained the thread pool
twice per page turn, the LRU cache was smaller than common page sizes,
and database listing tabs had no pagination at all (rebuilt every card on
every keystroke). Series/entity listings are now capped at 100 cards/page
(Option C below). None of this is the Option A virtualized rewrite —
still a `QLabel` grid under a fixed page cap, not `QListView` viewport
culling. The user is still seeing slowness and occasional freezes on
large directories after this pass; see the 2026-08-19 bus log for the
live investigation. If that turns out to be inherent to the bounded-page
QLabel approach at real-world directory sizes (hundreds-to-thousands of
images), Option A is the actual fix, not another tuning pass on C.

**2026-08-19 follow-up:** root-caused the "still slow, sometimes freezes"
report. Real cause: the LRU cache resize from the fix above never shrank
(`resize(max(current_maxsize, page_size))`), so one directory opened at
page size "All" permanently inflated the cache for the rest of the
process's life — unbounded RSS growth, matching the freeze exactly.
Capped with `LRU_CACHE_CEILING` (#458, fixed). Also fixed in the same
pass: a same-day theming regression that made every gallery viewport
transparent and disabled Qt's scroll-blit fast path (#453), extractor's
use of the global thread pool causing app-quit hangs (#455), synchronous
per-card metadata reads blocking the GUI thread at widget-construction
time (#456), and chunk/concurrency tuning for progressive rendering
(#454). All closed and verified against actual code, not just landing
claims. Still Option C underneath, not the Option A rewrite — revisit if
freezes recur at very large (thousands-of-images) directory sizes.

**2026-08-19 listing parity follow-up:** series/entity listings now inherit
the shared two-gallery foundation through a database-record adapter (#447).
Their existing 100-card pages now also support §2.13E search operators,
arrow/Enter navigation, per-tab Ctrl+wheel card sizing, and persisted §2.18
color-label borders without applying filesystem-only rename/copy operations
to database record IDs. This closes the listing-specific parity work while
retaining Option C pagination.

**2026-08-22 wallpaper crash follow-up:** linked Wallpaper panels no longer
release their directory-switch serialization when enumeration alone finishes.
They wait asynchronously for the initiating panel's thumbnail pool to drain,
then allow the mirrored panel or latest queued switch to start. This removes
the overlapping decode/signal churn observed when opening large directories.

**2026-08-22 native follow-up:** a core from the remaining directory crash
showed the GUI thread faulting in `QObject::property()` during PySide timer
dispatch while about 150 OpenMP workers from `base.load_image_batch()` were
alive. Native thumbnail batches now cap their OpenMP team at eight workers;
the real 165-image directory measured 24 baseline threads and 32 peak after
the change. This preserves parallel decoding without flooding the process.

**2026-08-22 Option A prototype shipped (opencode):** new
`gui/src/components/virtual_gallery/` — `VirtualGalleryModel`
(`QAbstractListModel` exposing every path as a row; `Qt.DecorationRole`
serves a lazily-loaded thumbnail, scheduling the background load on first
request via the same `ImageLoaderWorker` + `LRUImageCache` (QImage, never
QPixmap) + generation-tagged per-gallery `QThreadPool` the QLabel galleries
use, then emitting `dataChanged` for that row), `VirtualGalleryView`
(`QListView` IconMode, `uniformItemSizes`, scroll prefetch of the visible ±
buffer range, `QItemSelectionModel` selection, and `path_clicked` /
`path_activated` / `path_right_clicked` / `ctrl_wheel` signals mirroring
`ClickableLabel` + `MarqueeScrollArea`), and a `VirtualGallery` composite
widget exposing the tab-facing API (`set_paths`, `set_thumbnail_size`,
`selected_files`, `select_all`, `jump_to_path`, `cancel_loading`,
`clear_cache`). 14 tests in `gui/test/components/test_virtual_gallery.py`
verify the property that makes the page cap obsolete: a 10k-item gallery
creates **zero** card widgets, decoration requests are lazy (asking for one
row schedules exactly that row's load), stale results after `set_paths`/
`cancel_loading` are dropped, scroll prefetch schedules exactly the
visible±buffer range, and selection works over the model.

**2026-08-22 first tab migrated (opencode, Harbinger-approved):**
`ReverseImageSearchTab` (`gui/src/tabs/web/reverse_search_tab.py`) now renders
its scanned directory through `VirtualGallery` — the `QGridLayout` +
`ClickableLabel` card grid, its page-size/pagination bar, and the
card-rendering overrides (`create_card_widget`/`update_card_pixmap`/
`_style_label`) are deleted. Selection (`handle_image_selection` /
`update_visual_selection` / `select_all_items` / `deselect_all_items`)
maps onto the view's `QItemSelectionModel`; search-box filtering, Ctrl+wheel
zoom, drag-drop scan, config persistence, and the reverse-search engine flow
are unchanged (search/zoom now just feed/scale the virtual gallery). 7 new
tests in `gui/test/web/test_reverse_search_gallery.py` cover scan→model
population, empty scans, search-box filtering, selection mapping, select-all,
and zoom; verified `gui/test/{web,components,image,core,database}` `--run-gui`
→ 380 passed. The remaining `AbstractClassTwoGalleries` /
`AbstractClassSingleGallery` tabs (Extractor, Wallpaper, Format, Codec,
Similarity, database listings, …) still use the QLabel grid; migrate one at a
time using this tab as the pattern.

**2026-08-22 mass migration (opencode, one commit per tab):** the remaining
single-gallery tabs — `VideoExtractorSubTab` (extractor_tab, results gallery
with a video-capable worker factory), `MergeTab` (Image Library in
`MultiSelection` mode), and the `WallpaperCommonBase` system/monitor display
galleries (with the custom drag-to-monitor ported generically onto the virtual
view) — were migrated to `VirtualGallery`, and the dual-panel Convert
subtabs — `FormatSubTab`, `CodecSubTab`, `SamplerSubTab` — plus
`SimilarityTab`, the database `SearchTab`, and `ScanMetadataTab` were migrated
to Agy's `VirtualDualGallery` (found + selected panels, shared cache).
`ScanMetadataTab` also gained the `VirtualGalleryDelegate` in-DB green-border
styling (a reusable `InDbRole` extension). All drop their page-size/pagination
bars. Per-tab migration tests added;
`gui/test/{web,components,image,core,database}` `--run-gui` → 429 passed.
`ListingGalleryBase` (series/entity listings) is **not** an Option A target —
it stays on its deliberate Option C page cap (DB.5) because its rich
interactive `_ListingCard` DB widgets (File/Link buttons, context menus)
aren't expressible in the image-thumbnail model without a large custom
delegate, and the virtualization benefit is marginal at a 100-card cap.

**2026-08-22 eager pre-fill (opencode, S430):** `VirtualGalleryModel` now
pre-loads the whole item list in the background as soon as a gallery is
populated (`set_paths` → `_fill_all`, chained 4-in-flight dispatch), instead
of only loading the visible viewport ± buffer on scroll — images are already
in the cache when the user scrolls to them. Applies to every migrated tab;
memory stays bounded by the LRU cache and worker count by the chained dispatch.

**2026-08-22 dual-gallery design & prototype shipped (Agy):** Design document
`.agent/reports/dual_virtual_gallery_design.md` and prototype composite widget
`VirtualDualGallery` (`gui/src/components/virtual_gallery/dual_widget.py`).
Solves the two-gallery (`Found` + `Selected`) adoption path for
`AbstractClassTwoGalleries`: links two `VirtualGallery` instances sharing a
single `LRUImageCache` across a `QSplitter`, synchronizing selection staging,
independent search-filtering, drag-reordering, and §2.27 comparison without
page caps or sequential layout rebuild timers. 5 unit tests in
`gui/test/components/test_virtual_dual_gallery.py`.

**Pain point:** Page-based gallery requires manual forward/back navigation. LRU eviction on page change causes 50–200ms thumbnail reloads. `QLabel` grid layout does not scale beyond 200 items without noticeable lag.

### Options

**A — QListView + QAbstractItemModel with virtual scrolling**
Replace the grid of `QLabel` widgets with a `QListView` in `IconMode`, backed by a custom `QAbstractItemModel`. The model loads thumbnails on-demand via `fetchMore()` or lazy role population. Qt handles viewport culling automatically — only visible cells are rendered.
- Implementation notes: Subclass `QAbstractListModel`; implement `data()` returning `Qt.DecorationRole` as a `QPixmap` loaded from LRU cache. Use `uniformItemSizes(True)` for performance. Bind `QListView.verticalScrollBar().valueChanged` to trigger background prefetch of upcoming rows.
- Pros: Best long-term approach. Qt's viewport culling means 10k items cost the same as 100. Natural integration with `QItemSelectionModel` for bulk selection (§2.4).
- Cons: Large refactor of `AbstractClassTwoGalleries` and `AbstractClassSingleGallery`. Risk of breaking existing signal/slot connections.
- Reference: [Qt QListView docs](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QListView.html)

**B — QGraphicsView scene with item culling**
Place `QGraphicsPixmapItem` objects on a `QGraphicsScene`. Override `drawBackground()` to only load pixmaps for items intersecting the viewport rect. Items outside the viewport hold a placeholder.
- Pros: Easier to add zoom/pan interactions. Natural canvas for drag-and-drop.
- Cons: `QGraphicsScene` memory overhead per item is higher than model/view. Less battle-tested for 1000+ item galleries.

**C — Keep page system; increase page size + scroll indicator [Quick Win]**
Increase default page size from 50 to 150–200 images (safe now that LRU bounds RAM). Add a visual scroll indicator showing current position in the total collection. Add "Jump to page N" input.
- Pros: Minimal refactor. Acceptable for most use cases. Ships in hours.
- Cons: Still requires manual navigation for collections > 200 images. LRU eviction still reloads on page switch.

**D — QScrollArea with recycled QLabel pool**
Maintain a fixed pool of ~N_visible `QLabel` widgets. On scroll events, reassign the out-of-viewport labels to incoming images (widget recycling, similar to Android RecyclerView).
- Pros: No Qt model/view refactor needed. Can be retrofitted into the existing layout.
- Cons: Custom recycling logic is complex and error-prone. Higher maintenance than A.

**Recommendation:** C is the fastest improvement with no architecture change. A is the right long-term direction — prototype it against `AbstractClassTwoGalleries` in an isolated branch.

---

## 2.2 Gallery Thumbnail Size Control ✅ (2026-09-05: A + B + C + D) {: #22-gallery-thumbnail-size-control }
**Shipped:** Reusable `ThumbnailZoomControl` component (`gui/src/components/widgets/thumbnail_zoom_control.py`) combining live slider (Option A), Ctrl+scroll zooming in `VirtualGallery` / `VirtualDualGallery` / `AbstractGalleryBase` (Option B), S/M/L/XL preset buttons (Option C), and per-tab persistent size memory via `AppSettings.session(class_name, "thumbnail_size")` and `save_thumbnail_size` / `load_thumbnail_size` (Option D).

**Pain point:** Fixed thumbnail size suits neither 4K monitors nor laptops. Users managing large libraries want smaller thumbnails; users doing quality review want larger ones.

### Options

**A — Persistent slider in gallery toolbar**
A `QSlider` (range 48–512px, step 16) that updates the `thumbnail_size` parameter live. Store the value in `QSettings`. Re-trigger the batch loader with the new size.
- Pros: Explicit, always visible. Easy to discover.
- Cons: Adds a persistent UI element to the toolbar.

**B — Ctrl+scroll zoom [Quick Win]**
Intercept `wheelEvent` with `Ctrl` modifier in the gallery widget to resize thumbnails in place. Each scroll step changes size by 16px. Familiar from OS file managers (Finder, Nautilus) and IDEs.
- Pros: No UI chrome. Muscle memory from other apps.
- Cons: Ctrl+scroll conflict with text editors if the gallery has keyboard focus unexpectedly.

**C — Preset buttons (S/M/L/XL)**
Four fixed sizes (96/160/240/384px) as toggle buttons in the toolbar. Less flexible but harder to mis-click to an unusable size.
- Pros: Discoverable. Safe range.
- Cons: Limited flexibility.

**D — Per-tab persistent size**
Extend A/B so each tab remembers its own thumbnail size independently (e.g., convert tab prefers larger, database tab prefers smaller).
- Pros: Workflow-aware sizing.
- Cons: More `QSettings` keys to manage.

---

## 2.3 Keyboard Navigation ✅ Partial (2026-06-10 — §A arrow-key navigation in both gallery base classes; §B satisfied via §2.29, corrected 2026-07-27 — see below) {: #23-keyboard-navigation }

**Pain point:** Common operations require mouse interaction. Power users expect keyboard shortcuts for gallery navigation, preview, and operations.

### Options

**A — Arrow key gallery navigation**
Left/right/up/down select the adjacent thumbnail. Enter opens the full-size preview. Delete triggers the deletion workflow.
- Pros: Baseline expectation for any image browser. Minimal code (install `QShortcut` on the gallery widget).
- Cons: Requires focus management — shortcuts only fire when gallery has focus.

**B — Global hotkey table in settings** ✅ **Satisfied via §2.29, verified 2026-07-27 (GitHub issue #47).**
Let users configure custom bindings for any tab action. Store in `~/.config/image-toolkit/keybindings.json`. Use Qt's `QShortcut` with `Qt.ApplicationShortcut` context.
- Pros: Power-user friendly. Accommodates diverse workflows.
- Cons: Significant UI investment for the settings panel. Conflict detection between shortcuts.
- **Verified before building anything new**: this option's own architecture — a central registry, a settings-window table with `QKeySequenceEdit` per row, JSON persistence, reset-to-default — is exactly what §2.29 ("Configurable Keyboard Shortcuts") already built and shipped: `gui/src/utils/shortcut_manager.py`'s `SHORTCUT_REGISTRY`/`ShortcutRegistry` (load/save/reset/`get_key_sequence`/`matches`, persisted to `~/.image-toolkit/keybindings.json` — same file, `.image-toolkit` not `.config/image-toolkit`, a harmless path difference from this bullet's original text) and `SettingsWindow`'s "Keyboard Shortcuts" tab (`settings_window.py`, Tab 6). Confirmed genuinely wired at runtime, not just a settings stub: both `AbstractClassTwoGalleries` and `AbstractClassSingleGallery`'s `keyPressEvent` handlers call `reg.matches(event, "...")` against the live registry. This section's own status line simply never got updated to point at §2.29's completion — no new code needed.
- **Honest scope note**: the registry currently covers 24 actions across two scopes (`Gallery`, `Preview`) — genuinely "global" in *mechanism* (any future shortcut can register into it and gets settings-UI configurability for free), but not yet *coverage* of every tab's actions (e.g. ASP stitch tab, convert/merge-specific operations beyond gallery basics have no registry entries yet). Expanding registry coverage to more tabs is a legitimate, separate follow-on — not a gap in what this option asked for.

- **2026-08-27 Stitch coverage:** the ASP Stitch tab now adds a third `Stitch`
  scope with configurable run, cancel, compute-matches, and SCANS-comparison
  actions. Each dispatches through the existing button, preserving validation
  and enabled-state behavior; convert/merge follow-ons remain separate.

- **2026-08-27 Windows teardown check:** the authorized isolated
  `gui/test/windows/` directory run completed in 0.37 seconds (5 passed, 112
  expected skips), with no recurrence of the reported quadratic hang.

**C — Operation hotkeys (non-configurable)**
Fixed shortcuts for common operations: `Ctrl+D` duplicate scan, `Ctrl+E` export, `Ctrl+W` close preview, `Space` toggle selection. Discoverable via tooltips.
- Pros: Fast to implement. Covers 80% of use cases.
- Cons: Inflexible. May conflict with OS shortcuts on some platforms.

**D — Vim-style modal navigation (hjkl)**
Optional mode toggle: press `v` to enter visual navigation mode, use hjkl for movement. For users comfortable with modal navigation.
- Pros: High efficiency for keyboard-centric users.
- Cons: Niche appeal. Mode switching adds cognitive overhead.

**Recommendation:** A is the baseline expectation. C covers common operations quickly. B is the right long-term architecture for a power-user tool. Skip D unless there's explicit demand.

---

## 2.4 Bulk Selection and Operations ✅ Partial (2026-06-10 — §B Shift+click range + §C right-click context menu) {: #24-bulk-selection-and-operations }

**Pain point:** No way to select multiple images across the gallery and apply operations (convert, delete, tag) to all at once. Every operation is per-image or per-directory.

### Options

**A — Checkbox select mode**
Toggle a "select mode" button that shows checkboxes on all thumbnails. Selected images passed to operations via a "batch apply" button.
- Pros: Clear visual indication of selection state. No accidental selection.
- Cons: Requires a mode toggle; breaks flow.

**B — Shift+click range + Ctrl+click multi-select**
Standard file-manager pattern. No mode toggle needed. Works naturally with keyboard navigation (§2.3A).
- Pros: Users already know this pattern. Integrates cleanly with `QItemSelectionModel` if using QListView.
- Cons: Harder to implement cleanly in the current `QLabel` grid layout (no `QItemSelectionModel`).

**C — Context menu on selection**
Right-click shows a context menu with available batch operations when multiple images are selected.
- Pros: Discovers available operations without cluttering the toolbar.
- Cons: Requires B or A to first establish a selection.

**D — Lasso/rubber band selection**
Drag a selection rectangle over the gallery to select all thumbnails within it.
- Pros: Fast for spatially contiguous selections.
- Cons: Non-trivial to implement on a grid layout. Easier on QGraphicsView (§2.1B).

**E — "Select all" and "Invert selection" toolbar buttons**
One-click select all / deselect all / invert. Common in batch photo editors.
- Pros: Trivial to implement. High utility for "delete all except these" workflows.
- Cons: Only useful when combined with B or A for partial selection.

**Recommendation:** B + C together — standard patterns users already know. E is a trivial follow-on. D is better deferred until §2.1A is implemented.

---

## 2.5 Session Persistence ✅ (2026-09-05: A + C) {: #25-session-persistence }
**Shipped:** Per-tab last browsed directory persistence via `AppSettings.set_session` / `_save_last_dir` (Option A), and reusable `RecentDirectoriesPicker` dropdown tool button component (Option C) displaying MRU directory paths with elision, clear history action, and fast navigation across `SamplerSubTab`, `MergeTab`, `SimilarityTab`, `VideoExtractorSubTab`, `ScanMetadataTab`, `FormatSubTab`, and `CodecSubTab`.

**Pain point:** Every app restart requires re-browsing to the last directory. For consistent workflows this is repetitive friction.

### Options

**A — Remember last browsed path per tab [Quick Win]**
Store each tab's last directory in `QSettings`. Restore on startup. One-line change per tab.
- Pros: Minimal effort. Highest bang-for-buck.
- Cons: No scroll position or filter state is restored.

**B — Full session file**
Save the full app state (open tabs, loaded directories, gallery scroll position, active filters, selected images) to `session.json` in `~/.config/image-toolkit/`. Restore on startup.
- Pros: Complete workspace restoration.
- Cons: Complex to implement correctly. State deserialization can fail on version changes.

**C — Recent directories dropdown**
Show the 10 most recently browsed directories in a dropdown per tab. No auto-restore; user chooses.
- Pros: Low friction. Covers 80% of the use case without autoloading potentially stale paths.
- Cons: Still requires a click to restore.

**D — Named workspaces**
Save/load named "workspace" profiles that capture the full session state (B). Expose as a menu: `File → Workspaces → [Save / Load]`.
- Pros: Enables project-based workflows (e.g., "novel reading session" vs "wallpaper curation").
- Cons: Significant effort. Better deferred until B proves valuable.

---

## 2.6 Stitch Tab UX — Before/After Comparison ✅ (2026-08-22: B + C) {: #26-stitch-tab-ux--beforeafter-comparison }

**Shipped:** The Stitch result preview offers an on-demand, off-main-thread
OpenCV SCANS baseline written beside the ASP panorama (`<stem>_scans.<ext>`).
Its toggle crossfades ASP ↔ SCANS over 100 ms and switches the displayed
sharpness, double-edge ghosting, and seam-gradient readout with the image.

### Options

**A — Split-view with draggable divider**
Display ASP result on the left, SCANS result on the right, separated by a draggable vertical line. Both images registered to the same canvas coordinates.
- Pros: Precise spatial comparison.
- Cons: Requires two images to be loaded simultaneously. Custom `QWidget` paint override for the divider handle.

**B — Overlay toggle button [Quick Win]**
A single button that swaps between ASP and SCANS outputs. Add a brief crossfade animation (100ms) to highlight the difference.
- Pros: Faster than split-view for single-image judgement. Low UI complexity.
- Cons: Cannot compare two regions simultaneously.

**C — Quality metric overlay**
Show sharpness, ghosting, and seam gradient scores as a floating panel on top of the preview image. Scores update when switching between ASP/SCANS.
- Pros: Quantifies the visual difference. No comparison image needed.
- Cons: Numbers alone don't convey spatial distribution of quality issues.

**D — Difference heatmap view**
Compute |ASP - SCANS| per pixel and display as a colourmap overlay (e.g., hot colourmap). Regions of improvement are immediately visible.
- Pros: Spatially precise. Visually compelling.
- Cons: Requires both outputs to be the same resolution/alignment (may need registration step).

**Recommendation:** B + C. The metrics give context; the toggle lets the user see the actual visual difference. D is a [Research] quality analysis tool.

---

## 2.7 Progress and Cancellation ✅ Partial (2026-06-10 — §A stage progress + §B cancellable workers) {: #27-progress-and-cancellation }

**Pain point:** Long-running operations show minimal progress feedback and cannot be cancelled without killing the process.

### Options

**A — Stage-level progress bar for ASP**
Emit a stage-name signal at the start of each of the 13 pipeline stages. Display current stage name + per-stage progress percentage in the StitchTab status bar.
- Pros: Minimum viable feedback for a 90-second operation. Uses existing signal infrastructure.
- Cons: Within-stage progress (e.g., BiRefNet inference for frame N of M) requires additional signals.

**B — Cancellable QThread with `_should_stop` flag**
Add a `cancel()` method to all worker QThreads. Workers check the flag between stages and emit a `cancelled` signal.
- Pros: Correctness feature — prevents zombie workers. Reusable pattern for all long operations.
- Cons: Requires modifying every worker class. Some stages (e.g., single long GPU call) cannot be interrupted mid-stage.

**C — ETA estimate**
Based on benchmark timing data (per-stage avg seconds), display "~Xs remaining" that updates as each stage completes. Use exponential moving average to smooth the estimate.
- Pros: Reduces anxiety during long runs. Data already available from benchmark module.
- Cons: ETA is only accurate for corpus-similar inputs. Novel datasets (different resolution, frame count) will have inaccurate estimates.

**D — Per-operation cancellation tokens (async pattern)**
Use `asyncio.CancelledError` or a `threading.Event` as a cancellation token passed through the call stack. More composable than the `_should_stop` flag on the worker class.
- Pros: Cancellation can be triggered at any depth in the call stack, not just between stages.
- Cons: Requires refactoring the pipeline to pass the token through all stage calls.

**Recommendation:** A + B. Cancellation is a correctness feature. Stage progress is the minimum viable feedback. C is a quick add-on once A is in place.

**2026-08-22 (scanner-thread lifecycle audit — #461):** Audited bespoke worker and scanner threads across all GUI tabs to eliminate bounded waits (`wait(1000)`, `wait(5000)`, `waitForDone(2000)`) and fix improper stop/teardown order before widget clearing across `MergeTab`, `ScanMetadataTab`, `ReverseSearchTab`, `SimilarityTab`, `ImageExtractorSubTab`, `EntityReconTab`, and `FrameSelectionDialog`.

**2026-08-31 (worker-thread GC guard — #480):** Generalized the #478 fix into `gui/src/helpers/gc_safe.py` (`@gc_disabled_run` / `GcSafeThread` / `gc_disabled()`): the cyclic GC is disabled for a worker's whole `run()` so an allocation burst on a worker thread can never finalize GUI QWidget cycles off the GUI thread. Applied at `BaseQThreadWorker` / `BaseQRunnableWorker` and on the 11 direct-`run()` JSON/listing/DB workers; heavy CV/torch workers are listed as Tier-2 follow-ups in `.agent/reports/opencode/issue_480_gc_guard_audit_2026-08-31.md`.

**2026-08-31 (GIF creation streaming — #484):** `ImageMerger._create_gif` (`backend/src/core/image/_gif_video.py`) no longer opens every source frame into a list and holds them decoded for the whole `save()`; it streams one frame at a time through a lazy generator passed as Pillow's `append_images`, closing each source once copied. Peak RSS Δ ~145.7→50.2 MiB on the 48-frame and 269.6→72.2 MiB on the 96-frame benchmark (byte-identical output). Before/after harness: `backend/benchmark/bench_gif_creation.py`.

**2026-08-31 (queue extraction audit — #485):** queued GIFs use the same two-pass FFmpeg palette pipeline as direct exports; the queue's open-ended OpenCV probe and MoviePy GIF fallback now release resources on every path. A controlled two-worker start measurement keeps Linux `fork`: `spawn` added 0.687 s and ~92 MiB private memory per child before extraction.

**2026-08-31 (GC-guard Tier-2 — #481):** Extended `@gc_disabled_run` to the heavy CV/torch/ffmpeg worker threads listed as Tier-2 in the #480 audit — extraction, conversion, merge/scan/search, codec, video/image loader, embedding, model-training, web-recon (torch/HNSW/Selenium), `_FrameWorker`, and the ASP stitch / graph-stitch / batch-stitch / mask-preview workers (asp_gui aliases). Decorator sits outermost above any `@Slot()`. Static registry check over 38 classes + dynamic signal-probe tests: `gui/test/helpers/test_gc_tier2_workers.py` (51 passed).

---

## 2.8 Theme Support ✅ Partial (options A + D shipped — dark/light QSS toggle with per-theme accent-color override, `gui/src/windows/main/_theme.py` + `gui/src/styles/`; also UI density and a `load_user_qss_override` power-user hook) {: #28-theme-support }

**2026-08-18 — superseded by a much larger scope.** Harbinger wants full
user-defined theming (every color token, not just an accent tint) plus a
custom app background image, across all three of the project's UI
surfaces (PySide6 desktop app, `dev/app` devtool Tauri/React app, and the
docs website) — not just the PySide6 app this section originally scoped.
Full brainstorm-stage design doc:
[`app_theming_2026q3.md`](app_theming_2026q3.md). This section stays as
history for what shipped in the smaller original scope; new work happens
in that doc.

**2026-08-18 (round-1 Q&A, deepseek → Harbinger):** brainstorm refinements
folded into the design doc — hybrid QSS migration (keep the existing
$VAR system, generate the 5 core slots now), global background + per-tab
override, JSON-pack and raw-QSS both first-class theme formats, dynamic
palette extraction off by default (Theme Studio toggle), density as a
theme axis, base-theme + overrides model with follow-system switching the
base, blur off by default (opt-in, adaptive radius + cached layers), and
desktop-first Phase 1 with the shared token schema designed for reuse.

**Original pain point (for history):** App uses the system Qt palette, producing inconsistent look across platforms. Dark-mode OS settings not reliably respected.

### Options

**A — Dark/light mode toggle using QSS**
Write `dark.qss` and `light.qss`. Toggle via a settings checkbox. Load at startup from `~/.config/image-toolkit/theme.qss`.
- Pros: Full control over every widget style.
- Cons: QSS is verbose and brittle; needs maintenance as new widgets are added.

**B — qt-material or qdarkstyle integration**
Drop-in third-party stylesheets. `qt-material` (Google Material Design colours) or `qdarkstyle` (dark professional look).
- Pros: Fastest path to a polished dark theme.
- Cons: Adds a runtime dependency. Themes may not cover all custom widgets.

**C — Follow OS dark mode automatically [Quick Win]**
Use `QPalette.ColorScheme` (Qt 6.5+) to detect the OS preference and apply the matching Qt palette. Register a `QApplication.paletteChanged` handler to respond to live OS theme changes.
- Implementation: `QApplication.styleHints().colorScheme()` returns `Qt.ColorScheme.Dark/Light/Unknown`.
- Pros: Zero effort for correct behaviour. Respects user OS setting.
- Cons: Qt's auto-palette is less visually polished than a custom QSS.

**D — Accent colour customisation**
Allow users to choose a custom accent colour (used for selected thumbnails, progress bars, etc.) via a colour picker in settings. Inject into QSS as a CSS variable.
- Pros: Personalisation without maintaining full QSS.
- Cons: Requires QSS templating.

**Recommendation:** C first (zero effort, correct by default). A as a power-user override for users who want a specific look. Skip B — adds a dependency for minimal gain over C.

---

## 2.9 Settings Window Extensions

**Status:** Partially implemented (2026-05-31). The base settings window now includes Gallery & Display, Startup & Session, Performance & Cache, Slideshow Defaults, Logging, and Reset State sections. The items below describe the remaining work to make these settings take effect at runtime.

### Implemented (2026-05-31)

| Setting | Group | Persisted to Vault | Live Apply |
|---------|-------|--------------------|------------|
| Default thumbnail size | Gallery & Display | ✅ | Restart required |
| Default gallery page size | Gallery & Display | ✅ | Restart required |
| Confirm file deletions toggle | Gallery & Display | ✅ | Restart required |
| Startup default category | Startup & Session | ✅ | Next launch |
| Restore last browsed directory | Startup & Session | ✅ | Next launch |
| Recent directories count | Startup & Session | ✅ | Next launch |
| Found gallery LRU cache size | Performance & Cache | ✅ | Restart required |
| Selected gallery LRU cache size | Performance & Cache | ✅ | Restart required |
| Wallpaper gallery LRU cache size | Performance & Cache | ✅ | Restart required |
| Slideshow default interval | Slideshow Defaults | ✅ | Next slideshow start |
| Slideshow default playback order | Slideshow Defaults | ✅ | Next slideshow start |
| Log level | Logging | ✅ | Restart required |
| Enable file logging to disk | Logging | ✅ | Restart required |
| Clear thumbnail cache (action) | Reset State | N/A — immediate | ✅ |
| Reset slideshow daemon (action) | Reset State | N/A — immediate | ✅ |
| Clear all tab configs & profiles (action) | Reset State | ✅ — clears vault keys | ✅ |

### Remaining Work

**Re-verified 2026-07-27** against `gui/src/windows/main/main_window.py` (`_apply_startup_preferences()`) and
`gui/src/windows/settings/settings_window.py`. A/B/C/E/F/G below are all now confirmed wired (each is
tagged `§2.16A`/`§2.16B`/`§2.16C`/`§2.16E`/`§2.16F` directly in `_apply_startup_preferences()`, `G` via
`§2.9G`); D was already shipped per the note below. F was the last remaining gap and is fixed as of
2026-07-27 (issue #48) — see its entry for what changed.

**A — ✅ Wire thumbnail size / page size to gallery base classes at startup**
Confirmed shipped: `_apply_startup_preferences()` reads `preferences["thumbnail_size"]` / `["page_size"]` and sets `tab.thumbnail_size` / `tab.found_page_size` / `tab.page_size` on every gallery tab, tagged `§2.16A`.

**B — ✅ Wire LRU cache sizes to gallery base classes at startup**
Confirmed shipped: same function reads `found_cache_maxsize`, `selected_cache_maxsize`, `initial_cache_maxsize` and rebuilds `tab._found_pixmap_cache` / `_selected_pixmap_cache` / `_initial_pixmap_cache` as `LRUImageCache(maxsize=...)`, tagged `§2.16B`.

**C — ✅ Wire startup category to MainWindow**
Confirmed shipped: `_apply_startup_preferences()` sets `self.command_combo.setCurrentText(startup_cat)` from `prefs.get("startup_category", "")`, tagged `§2.16C`.

**D — Wire confirm_deletions to deletion workflows ✅ (2026-08-22)**
`_confirm_deletions_enabled()` reads `preferences["confirm_deletions"]` in the
gallery bases; the remaining standalone Similarity (single, batch, and worker
directory) and Wallpaper preview deletion paths now use the same policy.
Similarity's local checkbox only adds a confirmation when the global preference
is enabled. Its non-deletion "Compare first 10?" prompt is intentionally
unchanged.

**E — ✅ Wire slideshow defaults to WallpaperTab**
Confirmed shipped: `_apply_startup_preferences()` sets `wallpaper_tab.interval_min_spinbox` / `interval_sec_spinbox` / `playback_order_combo` from `prefs`, tagged `§2.16E`.

**F — ✅ Wire logging settings (2026-07-27, issue #48)**
Confirmed the gap before fixing: `preferences["log_level"]`/`["file_logging_enabled"]` round-tripped through `settings_window.py` but were never consumed. The architectural constraint is real — `_setup_logging()` runs before `QApplication`/vault unlock, so it has no access to vault preferences at that point — so the fix applies them later instead: a new `_reconfigure_logging(log_level_name, file_logging_enabled)` in `backend/src/app.py`, called from `_apply_startup_preferences()` (tagged `§2.16F`) once the vault is unlocked. It sets the console handler's level from the preference (string "DEBUG"/"INFO"/"WARNING"/"ERROR" → `logging` module constant, defaulting to INFO for an unrecognized value) and adds/removes a tagged `RotatingFileHandler` based on `file_logging_enabled` (`_make_file_handler()`/`_LOG_FILE_HANDLER_TAG`, factored out of `_setup_logging()` to avoid duplicating the handler-construction logic). Since `_apply_startup_preferences()` runs during the current launch's `MainWindow` init (right after login), this preference now actually takes effect on the very session it's read in, not just "next restart" as the table above implies for these two rows. Verified via 6 new unit tests in `backend/test/core/test_app_logging.py` (handler tagging, level application, add/remove/idempotent-enable, unknown-level fallback) — all passing; a `_clean_root_logger` fixture saves/restores the real root logger's handlers around each test so this doesn't leak into other test files' logging state.

**G — ✅ Wire restore_last_dir and recent_dirs_count (2026-07-27, issue #49)**
`restore_last_dir` was already consumed (`_apply_startup_preferences()` reads it and gates directory restoration). `recent_dirs_count` is now wired too: `settings_window.py` gained a `recent_dirs_count_spinbox` (QSpinBox, range 1-50, default 10) in the Startup & Session section, `collect()` now saves `self.recent_dirs_count_spinbox.value()` instead of the literal `10`, and `set_config()`/`reset_settings()` populate/reset it. `AbstractGalleryBase.__init__` (`gui/src/classes/base/gallery_base.py`) gained a `self.recent_dirs_limit: int = 10` instance attribute, and `_add_recent_dir(self, path, max_entries: Optional[int] = None)` now defaults to `self.recent_dirs_limit` when no explicit `max_entries` is passed (existing explicit-argument callers are unaffected). `main_window.py::_apply_startup_preferences()` reads `prefs.get("recent_dirs_count", 10)` and sets `recent_dirs_limit` on every gallery tab plus, since `ConvertTab` is a plain `QWidget` wrapper (not a gallery base subclass itself), explicitly on its nested `format_subtab`/`codec_subtab`/`sampler_subtab` — the actual `_add_recent_dir` callers. Default behavior (10) is unchanged for existing saved configs with no `recent_dirs_count` key. Verified via `gui/test/core/test_settings_window.py` and `gui/test/core/test_main_window.py` (both green, `--run-gui` scoped) plus a manual smoke test of `_add_recent_dir` MRU-trim behavior under a custom limit.

**H — ✅ Current Category session recovery + Default Startup Tab / restore-last-tab decoupling (2026-08-01)**
Two related additions. First, Session Recovery Level gained a fourth option, "Current Category": saves/restores `.collect()`/`.set_config()` for every tab within whichever category was active on close, not just the single active tab (`Current Tab`) or every tab in the app (`All Tabs`) — `main_window/_session_recovery.py`'s `_save_session_recovery()`/`_restore_session_recovery()` both gained a `"Current Category"` branch, plus the `restore_last_dir` reset-on-startup block gained a matching branch that only resets directories for tabs *outside* the active category. Second, tab **selection** at startup is now fully decoupled from Session Recovery Level (previously, any non-"None" recovery level implicitly also navigated to the last-active tab as a side effect of restoring its config): a new "Default Startup Tab" combo (cascades from the existing "Default Startup Category" combo) and an independent "Restore last opened tab on startup" checkbox (next to "Restore last browsed directory on startup") now govern *which tab is shown*, while Session Recovery Level governs only *which tab configs get restored*. `_restore_session_recovery()` picks the previously-active category/tab from `recovery_data` when the checkbox is on, else the Default Startup Category/Tab preferences — and `_save_session_recovery()` now persists `active_category`/`active_tab` whenever either feature needs them (previously only written when `session_recovery_level != "None"`). Verified via `gui/test/core/test_main_window.py` (`TestMainWindowSessionRecovery`, `--run-gui` scoped) and `gui/test/core/test_settings_window.py` (`TestSettingsWindowStartupTab`).

---

## 2.10 In-App Toast Notification System ✅ Partial (2026-06-10 — §C shipped, 2026-08-07 — §A shipped) {: #210-in-app-toast-notification-system }

**Pain point:** Every operation result — file saved, cache cleared, duplicate found, export finished — triggers a blocking `QMessageBox` that interrupts the user's workflow. For background operations (slideshow daemon ticks, RLHF auto-score, WebDriver status) there is no non-blocking feedback path at all.

### Options

**A — Custom overlay toast widget [Quick Win] ✅ (2026-08-07)**
A borderless, semi-transparent `QLabel` anchored to a corner of `MainWindow`. Shown via a `QPropertyAnimation` on opacity (0→1→0 over ~2.5s). Queued: multiple toasts stack vertically. No third-party dependency.
- Implementation: `QFrame` with `WindowStaysOnTopHint | FramelessWindowHint`; `QPropertyAnimation("windowOpacity")`; `QTimer.singleShot(2000, self.close)`.
- Pros: Zero new dependencies. Full visual control.
- Cons: Must handle window focus without stealing it. Requires custom stacking logic.

**B — pyqt-toast-notification library**
Drop-in `pyqttoast` (pip installable, PySide6 compatible). Supports 7 positions, queueing, icons (SUCCESS/WARNING/ERROR/INFO), and widget-relative positioning.
- Reference: [pyqt-toast-notification GitHub](https://github.com/niklashenning/pyqttoast)
- Pros: Fully featured out-of-the-box. 5-line integration.
- Cons: New pip dependency. Style must match the app's QSS theme.

**C — QStatusBar at main window bottom**
Add a `QStatusBar` to `MainWindow`. Non-critical messages display for 3s and auto-clear. Critical messages stay until cleared.
- Pros: Native Qt widget. Zero new dependencies. Permanent status info (e.g. "Daemon running" badge).
- Cons: Single message at a time — queuing is not native. Less visible than a floating toast.

**D — Notification centre panel**
A collapsible side panel (right edge) accumulating all operation results as a scrollable list. Each item has a timestamp, icon, and dismissal button.
- Pros: Full history. No messages lost. Glanceable.
- Cons: High effort. Requires a panel layout change to `MainWindow`.

**Recommendation:** C first (QStatusBar is trivial, adds permanent status display). A as the floating overlay for success/error feedback. B as an optional drop-in if A proves complex.

---

## 2.11 Image Preview Window Enhancements ✅ Partial (2026-06-10 — §A fullscreen, §B fit modes, §D rotation shipped) {: #211-image-preview-window-enhancements }

**Pain point:** The `ImagePreviewWindow` already has zoom/pan (Ctrl+scroll), left/right arrow navigation, and GIF support. It is missing: fullscreen mode, fit-to-width mode, EXIF metadata panel, rotation, and the "mini-map" navigator that professional viewers show when zoomed in.

### Options

**A — Fullscreen toggle (F11 / F) [Quick Win]**
`QKeySequence(Qt.Key_F11)` shortcut toggles `self.showFullScreen()` / `self.showMaximized()`. Hide the arrow nav buttons in fullscreen; restore on exit. Mouse cursor hides after 3s idle (via `QTimer` + `setCursor(Qt.BlankCursor)`).
- Pros: Single hotkey, trivial to implement.
- Cons: Must guard against focus issues when cursor hides.

**B — Fit-to-width / fit-to-height / 100% zoom modes [Quick Win]**
Add toolbar-style buttons or keyboard shortcuts: `W` = fit to width (fill horizontal), `H` = fit to height (fill vertical), `1` = 100% (actual pixels). Currently only fit-to-window exists.
- Pros: Essential for long vertical images (manga strips). One additional zoom-calculation path.
- Cons: 100% mode may result in scroll area with a very large image for 4K input.

**C — Inline EXIF / file metadata sidebar**
A collapsible `QSplitter` panel on the right showing file metadata: path, dimensions, file size, colour mode, DPI, and any embedded EXIF (using `Pillow.ExifTags` or `piexif`).
- Pros: High value for database workflows. Avoids opening external tools.
- Cons: Requires `piexif` or `Pillow` dependency (likely already present). Reading EXIF adds ~5ms per image.

**D — Rotation controls [Quick Win]**
`R` / `L` hotkeys to rotate the displayed image 90° CW / CCW. State is in-memory (does not write to disk unless user presses "Save Rotation"). Uses `QTransform`.
- Pros: Frequently needed for phone-captured images in portrait.
- Cons: In-memory-only rotation is confusing unless the save state is clearly communicated.

**E — Mini-map (navigator overlay)**
When zoom > 100%, show a small thumbnail in the top-right corner with a semi-transparent rect indicating the current viewport within the full image. Click/drag the rect to pan.
- Pros: Professional viewer feature. Eliminates disorientation when zoomed into 4K images.
- Cons: Requires overlaying a custom widget on top of the scroll area. Medium effort.

**F — Copy to clipboard from context menu and Ctrl+C [Quick Win]**
Already implemented for static images; verify it works for GIFs (copies current frame). Add "Copy path to clipboard" as a second context menu action (copies the file path as a string, not the image data).
- Pros: Already mostly there.
- Cons: Minor gap verification.

**Recommendation:** A + B + D as Quick Wins (all hotkey changes, each ~30 min). C for EXIF-heavy workflows. E is the highest-polish addition.

---

## 2.12 System Tray Integration ✅ Partial (2026-06-10 — §A+B+C shipped) {: #212-system-tray-integration }

**Pain point:** The slideshow daemon runs as a background Rust binary, but the app has no system tray icon. When the main window is minimised, there is no way to check the daemon status, trigger wallpaper rotation, or receive a notification when a long batch job completes.

### Options

**A — QSystemTrayIcon with daemon status [Quick Win]**
Create a `QSystemTrayIcon` in `MainWindow.__init__`. Icon reflects daemon state (green = running, grey = stopped). Context menu: "Show Window", "Stop Daemon", "Next Wallpaper", "Quit".
- Tray icon tooltip shows "Daemon: running | Next wallpaper in 4:23".
- Reference: [PySide6 QSystemTrayIcon docs](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html)
- Pros: Native on all supported platforms (Linux D-Bus StatusNotifierItem, Windows, macOS). Well-supported in Qt 6.5+.
- Cons: Requires an icon asset (SVG/PNG). KDE may require correct D-Bus configuration.

**B — Tray balloon notifications for operation completion**
When a long background operation (ASP batch, crawler, Celery job) completes, call `tray_icon.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 4000)`.
- Pros: Native OS notification. No extra dependencies.
- Cons: balloon notifications are unreliable on some Linux DEs (GTK-based compositors).

**C — Minimise-to-tray instead of taskbar close**
Override `closeEvent` to call `hide()` instead of closing when the tray icon is active. Only quit on "Quit" from the tray menu.
- Pros: Common pattern for always-running tools like slideshow daemons.
- Cons: Must be opt-in (setting) to avoid confusing users who expect the window to close normally.

**D — Tray icon badge (operation count)**
Overlay a numeric badge on the tray icon when there are active operations (e.g., "3" pending crawlers). Implemented by compositing a `QPainter`-drawn number onto the icon `QPixmap`.
- Pros: At-a-glance status without opening the window.
- Cons: Badge rendering on small icons (22×22px on Linux) is finicky. Low priority.

**Recommendation:** A + B first. C as a settings toggle. D is a polish item.

---

## 2.13 Gallery Filtering and Sort Controls ✅ Partial (2026-06-10 — §A + §E) {: #213-gallery-filtering-and-sort-controls }

**Pain point:** Current search is filename substring-only with no sort controls. Users cannot filter by extension, file size, date modified, image dimensions, or tags — all of which are meaningful for a large image database. The `_common_filter_string_list` in `MetaAbstractClassGallery` only does a `query in item.lower()` check.

### Options

**A — Sort control toolbar (name / date / size / type) [Quick Win]**
Add a sort `QComboBox` + ascending/descending `QPushButton` above the gallery. Applies `sorted(paths, key=...)` before calling `start_loading_gallery`.
- Sort keys: name (natural), date modified (`os.path.getmtime`), file size (`os.path.getsize`), extension.
- Pros: Zero new UI dependencies. Immediate quality-of-life improvement.
- Cons: Re-sorting after each page change requires storing the full sorted master list.

**B — Filter chip bar (extension toggles)**
A row of small toggle buttons, one per file extension in the current directory (e.g., `[PNG] [WEBP] [JPG]`). Active chips are highlighted. Filter applied to the display list.
- Pros: Discoverable. No typing required. Works well for format-mixed directories.
- Cons: With many formats (15+), the chip row becomes crowded. Must limit to top-N or use a "More" popover.

**C — Advanced filter panel (collapsible)**
A collapsible panel below the search bar with fields: Min size (MB), Max size, Min width (px), Max height, date range (QDateEdit), and tag includes/excludes. Apply button runs the filter.
- Pros: Covers all power-user filter needs.
- Cons: High effort to implement. Filtering by dimensions requires reading image headers (fast via Rust `image_dimensions`, ~0.5ms each, but adds a scan pass).

**D — Tag-based filtering in gallery tabs**
Integrate the database tag system into the gallery search: type `tag:character:misaka` to filter by tag. Requires the image to be in the database.
- Pros: Bridges the gallery view and database seamlessly.
- Cons: Only works for images already indexed in PostgreSQL. Requires a DB query per filter change.

**E — Search operators (regex, negation, OR)**
Extend `_common_filter_string_list` to support: `-query` (exclude), `"exact phrase"` (quoted), `a|b` (OR). Drop-in with no UI changes.
- Pros: Power-user feature. 30-minute implementation.
- Cons: Must document the syntax (tooltip or placeholder text).

**Recommendation:** A + E first (sort and search operators are trivial, high impact). B for visual filtering. C as a long-form feature sprint.

---

## 2.14 Thumbnail Metadata Overlay ✅ Partial (2026-06-10 — §A shipped) {: #214-thumbnail-metadata-overlay }

**Pain point:** Hovering a thumbnail shows no information. To know the filename, dimensions, or file size of an image, the user must double-click to open the full preview or navigate to an external tool. The `DraggableLabel` / `ClickableLabel` components in `gui/src/components/` have no hover overlay.

### Options

**A — Filename label below thumbnail [Quick Win]**
Render a truncated filename `QLabel` beneath each thumbnail cell. Already partially available in some tabs — standardise across all gallery base classes.
- Pros: Always visible. No interaction required.
- Cons: Takes vertical space. Long filenames must be elided (`Qt.ElideMiddle`).

**B — Hover overlay with file info**
On `enterEvent`, overlay a semi-transparent `QFrame` on the thumbnail with: filename, dimensions (W×H), file size, and modification date. Populated lazily (dimensions via `QImageReader.size()` — no full decode).
- Pros: Full info without opening the preview. Doesn't consume permanent layout space.
- Cons: Overlay must be positioned correctly over the thumbnail label. Requires `enterEvent`/`leaveEvent` on `DraggableLabel`.

**C — Rich tooltip with thumbnail preview**
Use `QToolTip.showText()` with HTML content including an `<img>` tag pointing to the thumbnail path. Qt renders HTML tooltips natively.
- Pros: Zero custom widget code. One-line change.
- Cons: Image in tooltip is re-loaded by Qt (not from LRU cache). Can cause flickering or slow-load on HDDs.

**D — Status bar info on hover**
When a thumbnail is hovered, emit a signal that updates the main window status bar with the file path, size, and dimensions. No overlay widget needed.
- Pros: Minimal code. Works well with the QStatusBar recommendation (§2.10C).
- Cons: Status bar is at the bottom of the window — far from the hovered thumbnail.

**E — EXIF lazy tooltip**
After a 500ms hover delay, fire a background `QRunnable` to read EXIF from the file; update the tooltip with camera make/model, aperture, shutter speed, ISO, date taken.
- Pros: Professional feature for photographers.
- Cons: Requires EXIF library. Tooltip update after async read is non-trivial (must invalidate and reshown tooltip).

**Recommendation:** A immediately (filename label is the minimum viable state). B as the primary hover-info feature. E for database/photography workflows.

---

## 2.15 Undo/Redo for Destructive Operations ✅ (2026-09-05: A + B + C) {: #215-undoredo-for-destructive-operations }
**Shipped:** `send2trash` integration across all delete call sites (Option A), full `QUndoStack` subsystem with `UndoManager`, `FileDeletionCommand` (session trash buffering & instant restoration), `FileRenameCommand` (Option B & C), `Ctrl+Z` / `Ctrl+Shift+Z` / `Ctrl+Y` shortcut dispatch in `MainWindow` and gallery base classes, and test isolation support.

**Pain point:** File deletions across `DeleteTab`, `WallpaperTab`, `SearchTab`, and `ConvertTab` are permanent and cannot be undone. "This cannot be undone!" appears in 6+ QMessageBox dialogs but there is no recovery path. No `QUndoStack` infrastructure exists anywhere in the GUI.

### Options

**A — Move to trash instead of `os.remove` [Quick Win]**
Replace `os.remove(path)` with `send2trash.send2trash(path)` (pip dependency). The OS trash provides a built-in undo path via the file manager.
- `send2trash` works on Linux, macOS, and Windows.
- Pros: One-line change per delete call site. Users can recover via the system file manager.
- Cons: New pip dependency. Trash may not be available on all Linux configurations (no trash on root filesystem XDG mounts). Does not address in-app undo.

**B — QUndoStack for file move operations**
Create a `FileOperationCommand(QUndoCommand)` class. Implement `redo()` as `shutil.move(src, dst)` and `undo()` as `shutil.move(dst, src)`. The delete operation moves files to a per-session trash folder inside `~/.image-toolkit/trash/`.
- Per-session trash is emptied on clean app exit or by "Empty Trash" button in settings.
- Pros: In-app undo/redo. No external dependency. Standard Qt pattern (`QUndoStack`, `QUndoView`).
- Cons: Session trash consumes disk space. Must handle conflicts (file already moved/renamed).

**C — Undo stack limited to renames and tag changes**
Only queue rename and tag-change operations for undo (lower risk than file moves). File deletions remain permanent (with confirmation).
- Pros: Scoped implementation. Lower risk of edge cases.
- Cons: Doesn't address the most dangerous operation (deletion).

**D — "Recycle Bin" tab in the app**
A dedicated `RecycleBinTab` showing files moved there by the app. Each item shows original path, deletion time, and "Restore" / "Permanently Delete" buttons.
- Pros: Explicit in-app recovery UI. Clear mental model.
- Cons: Significant UI effort. Must track metadata (original path) persistently.

---

## 2.16 Command Palette / Quick Launcher ✅ (2026-09-05 — Options A & C shipped) {: #216-command-palette--quick-launcher }

**Shipped: Options A & C.**
- **Option A (Ctrl+K Command Palette)**: Floating quick launcher `CommandPaletteDialog` (`gui/src/components/dialogs/command_palette_dialog.py`) with fuzzy search over all tabs, operations (theme toggle, undo/redo, shortcuts, settings, templates, global search), and category badges.
- **Option C (Ctrl+T Tab Search)**: Tab and runtime module search popup.
- **Tests**: `gui/test/dialogs/test_command_palette.py` (2 unit tests).

### Options

**A — Ctrl+K overlay (VS Code style)**
A floating `QDialog` with a `QLineEdit` (fuzzy search) and a `QListWidget` of matches. Populating it with: tab names, operation shortcuts ("Start Conversion", "Run Duplicate Scan"), and recent directories.
- Implementation: maintain a `command_registry: list[dict]` mapping label → callable. Filter on keypress with `difflib.get_close_matches` or simple `in` check.
- Pros: Keyboard-first. High discoverability for all registered commands.
- Cons: Requires maintaining the command registry as new tabs/operations are added.

**B — Tab search dropdown enhancement**
Replace the "Select Category" `QComboBox` with a `QComboBox` that has `setEditable(True)` and a `QCompleter` that searches across both categories and tab names.
- Pros: Minimal UI change. Reuses existing combo infrastructure.
- Cons: Only navigates tabs — cannot trigger operations.

**C — Global tab search with Ctrl+T**
A narrower variant of A: Ctrl+T opens a small popup showing only tab names, filtered by typing. Pressing Enter switches to the matched tab.
- Pros: Simpler than a full command palette. Covers the most common use case.
- Cons: Less powerful — no operation triggering.

**D — Recent operations history**
Maintain a `deque` of the last 10 operations run (scan, convert, stitch, etc.) with their parameters. Ctrl+K shows these at the top as "recent" commands.
- Pros: Pairs with A to create a muscle-memory-friendly workflow.
- Cons: Requires hooking into all operation entry points.

**Recommendation:** C first (tab navigation covers 80% of the need). A as the full implementation when C is validated.

---

## 2.17 Global Collapsible Log Panel ✅ Partial (2026-06-10 — §D shipped: LogWindow upgraded) {: #217-global-collapsible-log-panel }

**Pain point:** `LogWindow` exists but is instantiated per-tab and opens as a floating child window. Each tab that has logging opens a separate window. There is no unified log view across the app, and `print()` calls from the backend are never captured to any UI element.

### Options

**A — Bottom-anchored collapsible QPlainTextEdit panel**
Add a horizontal `QSplitter` between the tab widget and the window bottom edge. The lower half is a `QPlainTextEdit` in read-only mode. A "Log" toggle button in the header shows/hides it. A custom Python `logging.Handler` subclass calls `plain_text.appendPlainText()` from any thread via `QMetaObject.invokeMethod`.
- Pros: All app logging (Python `logging` module) in one place. No additional windows.
- Cons: Splitter state must be persisted. Panel takes vertical screen space.

**B — Floating, dockable log window**
A `QWidget(Qt.Window)` (like the existing `LogWindow`) but shared across the entire app. Tabs emit signals to a global `LogBus` singleton; the window subscribes and appends.
- Pros: Doesn't consume main window space. Can be undocked and moved to a secondary monitor.
- Cons: Still a separate window. Less discoverable.

**C — Tab-level log integration in the tab bar**
Each tab gets a small "⚠ N" badge on its tab handle when there are unread warning/error messages. Clicking the badge opens a small popover with the last N messages from that tab.
- Pros: Per-tab context. Doesn't pollute a global log with irrelevant messages.
- Cons: QTabBar badge requires custom painting (`QTabBar::paintEvent` override). Complex.

**D — Log level coloring and copy support in LogWindow**
Upgrade the existing `LogWindow` (`gui/src/windows/log_window.py`) in-place: replace `QTextEdit` with `QPlainTextEdit`, add ANSI-colour-level formatting (ERROR=red, WARNING=orange, INFO=white, DEBUG=grey), add "Copy All" and "Save to File" buttons, and auto-scroll with a "Follow" toggle.
- Pros: Minimal change. Immediately improves the existing log window without architecture change.
- Cons: Per-tab windows still not unified.

**Recommendation:** D first (immediate improvement to existing infrastructure, ~2h). A when §5.4 (logging module) is wired up — the two are the natural pairing.

---

## 2.18 Image Rating and Color Labels ✅ (2026-09-05 — Options A, B, C, and D shipped) {: #218-image-rating-and-color-labels }

**Shipped: Options A, B, C, and D.**
- **Option A & C (Star Badges & Color Borders)**: Star rating overlays rendered via `VirtualGalleryDelegate` (`★ 4.5`) and color border styling per image in gallery cards and virtual galleries.
- **Option B (Color Label Menu & Persistence)**: 6 color swatches (red, orange, yellow, green, blue, purple) in right-click context menu and `AppSettings.label(path)` / `AppSettings.star_rating(path)` persistence.
- **Option D (Rating & Label Filter Bar)**: Dedicated `RatingFilterBar` (`gui/src/components/widgets/rating_filter_bar.py`) providing instant gallery filtering by star rating (`All`, `★ 1+` … `★ 5`) and color swatches.
- **Tests**: `gui/test/widgets/test_rating_filter_bar.py` (5 unit tests).

### Options

**A — Star rating overlay on thumbnails**
Render 1–5 clickable star icons below each thumbnail (using `★` / `☆` Unicode or SVG). Click sets the rating. Rating stored as an integer column in the PostgreSQL `images` table.
- Schema: `ALTER TABLE images ADD COLUMN rating SMALLINT DEFAULT 0;`
- Pros: Familiar to photographers. Integrates with §2.13 filter (filter `rating >= 3`).
- Cons: Requires schema migration. Star widget must be small enough not to dominate the thumbnail.

**B — Color label button in context menu [Quick Win]**
Right-click context menu on a thumbnail shows a colour picker (6 colour swatches). Selection stored in a `color_label` column or a special tag (`label:red`).
- Pros: Low UI footprint (no permanent overlay). Fast to implement.
- Cons: Label not visible in gallery until hovered (no permanent indicator).

**C — Coloured border ring on thumbnail as label indicator**
When a thumbnail has a colour label set, its border ring is rendered in that colour. Combined with B for assignment.
- Pros: Immediately visible in gallery without hover.
- Cons: Border colour must work with both dark and light themes. Thin borders (1px) are hard to see at small thumbnail sizes.

**D — Rating filter bar above gallery**
A row of star icons above the gallery: clicking "≥ 3 stars" filters the visible set. Combined with A for assignment.
- Pros: Natural pairing with A. Standard lightroom-style UX.
- Cons: Depends on A being implemented first.

**E — Export by rating/label**
"Export all 5-star images to folder" as a batch operation in the gallery context menu or export tab.
- Pros: High practical value for curating output sets.
- Cons: Depends on A/B.

**Recommendation:** B + C first (context-menu label + visual indicator, no schema migration needed if using tag system). A + D as a full implementation sprint.

---

## 2.19 Gallery Export and Contact Sheet ✅ (2026-09-05 — Options A, B, and C shipped) {: #219-gallery-export-and-contact-sheet }

**Shipped: Options A, B, and C.**
- **Option A & C (Path & Directory Export)**: "Export Paths… (Ctrl+E)" and "Copy Selection to Folder…" in gallery context menus and shortcuts.
- **Option B (Contact Sheet Generator)**: `generate_contact_sheet()` engine (`gui/src/utils/contact_sheet_generator.py`) and `ContactSheetDialog` (`gui/src/components/dialogs/contact_sheet_dialog.py`). Parameterizes columns (1–16), thumbnail box sizes (128/256/384/512px), cell padding, outer margins, background color, and filename captions with threaded generation to PNG/JPEG/PDF. Wired to `AbstractClassTwoGalleries` and `VirtualGallery`.
- **Tests**: `gui/test/dialogs/test_contact_sheet.py` (2 unit tests).

### Options

**A — Export selection as paths list [Quick Win]**
"Export selection → Save as TXT/CSV/JSON" in the gallery context menu. Writes the selected file paths to a file. `QFileDialog.getSaveFileName` for the destination.
- Pros: Zero new dependencies. 30-minute implementation.
- Cons: TXT/CSV only useful for scripting. Not visual.

**B — Contact sheet generator**
Arrange selected thumbnails in a grid and export as a single PNG/PDF. Parameterise: columns, thumbnail size, filename label, background colour.
- Implementation: PIL/Pillow `Image.new` + `paste` loop. Already have Pillow in the venv.
- Pros: Visual proof sheet. Useful for sharing selection overview.
- Cons: Medium effort. Output file can be large for 100+ image selections.

**C — Export to directory (copy/move)**
"Copy selection to folder" / "Move selection to folder" from context menu or toolbar. `QFileDialog.getExistingDirectory` for the destination.
- Pros: Essential file management operation. Common in image managers.
- Cons: Move requires updating the internal path tracking list.

**D — "Send to Convert Tab" button**
A button that pushes the current gallery selection into the `ConvertTab`'s input paths, pre-populating it for batch format conversion.
- Pros: Cross-tab workflow shortcut. Leverages existing conversion infrastructure.
- Cons: Requires cross-tab communication (already done in `database_tab` via `scan_tab_ref` pattern).

**Recommendation:** A + C immediately (both are one-function operations). B as a polish feature. D as a cross-tab workflow improvement.

---

## 2.20 Resizable Sidebar Panels and QSplitter Persistence ✅ Partial (2026-06-10 — §A shipped) {: #220-resizable-sidebar-panels-and-qsplitter-persistence }

**Pain point:** Gallery tabs use a fixed vertical stack layout. A collapsible metadata/tag sidebar would allow users to see image details and assign tags without opening a separate preview window, but no `QSplitter` exists in the core gallery base classes. Additionally, the `QSplitter` instances in `listings_tab.py`, `stitch_tab.py`, and `hybrid_stitch_panel.py` do not persist their sizes across sessions — they reset to defaults on every launch.

### Options

**A — Persist QSplitter sizes in QSettings / vault [Quick Win]**
For every existing `QSplitter`, call `saveState()` on hide/close and `restoreState()` on show. Key: `f"splitter_{tab_class_name}_{splitter_index}"` in `QSettings`.
- Pros: Instant quality-of-life for all existing splitter users. Minimal code per splitter.
- Cons: Must handle the case where the splitter widget count changes (ignore restore if count mismatch).

**B — Right sidebar in gallery base classes**
Add an optional `QSplitter(Qt.Horizontal)` to `AbstractClassTwoGalleries` and `AbstractClassSingleGallery`. The right pane is hidden by default (width = 0) and shows a `QStackedWidget` when toggled. Content: file metadata, tags, rating.
- Toggle via `I` hotkey (info panel, same as many image viewers).
- Pros: Non-intrusive by default. Extensible — any tab can push content to the info pane.
- Cons: Significant refactor of both base classes.

**C — Floating metadata panel (QDockWidget style)**
Use `QWidget(Qt.Tool)` positioned adjacent to the main window. Follows the main window when moved.
- Pros: Doesn't change base class layout.
- Cons: Separate window management. Does not feel integrated.

**D — Advanced Docking System (Qt-ADS)**
Use `PyQtADS` (Python bindings for Qt Advanced Docking System) for full drag-and-drop panel rearrangement.
- Reference: [Qt-Advanced-Docking-System GitHub](https://github.com/githubuser0xFFFF/Qt-Advanced-Docking-System)
- Pros: Professional-grade docking. Users can rearrange panels to their workflow.
- Cons: Heavy dependency. Over-engineered for the current app's needs.

**Recommendation:** A immediately (splitter persistence is a 2-line fix per splitter). B as the primary quality improvement sprint. Skip D.

---

## 2.21 Directory Navigation History (Back / Forward) ✅ (2026-09-05 — Options A & D shipped) {: #221-directory-navigation-history-back--forward }

**Shipped: Options A & D.**
- **Option A & D (Back/Forward History & MRU Dropdown)**: Base class `AbstractGalleryBase` maintains `deque(maxlen=20)` for `_dir_back_stack` and `_dir_forward_stack`. Reusable `create_nav_history_buttons()` provides tactile `◀` Back and `▶` Forward toolbar buttons with dynamic enabled-state tracking and `Alt+Left` / `Alt+Right` navigation across `FormatSubTab`, `CodecSubTab`, `SamplerSubTab`, `MergeTab`, `SimilarityTab`, `VideoExtractorSubTab`, and `ScanMetadataTab`.
- **Tests**: `gui/test/navigation/test_dir_navigation_history.py` (2 unit tests).

### Options

**A — Per-tab navigation history stack [Quick Win]**
Maintain a `deque(maxlen=20)` as a back-stack and a forward-stack per gallery tab instance. "Browse" pushes to the back stack. Back/forward buttons (or `Alt+Left/Right`) pop from the respective stack and reload the gallery.
- Pros: Familiar from file managers and web browsers. Zero dependencies.
- Cons: Requires wiring into every `browse_*` method across tabs.

**B — Breadcrumb path widget**
Replace the `QLineEdit` scan directory path with a breadcrumb widget (horizontally scrollable list of clickable path segments). Clicking any segment navigates up to that directory.
- Pros: Faster navigation to parent directories than clicking Back repeatedly.
- Cons: Custom `QWidget` required. Path segments must be parsed and buttons created dynamically.

**C — Directory tree sidebar**
A collapsible `QTreeView` backed by a `QFileSystemModel` showing the filesystem tree. Clicking a node loads that directory's gallery. Pairs well with §2.20B sidebar.
- Pros: Standard file manager pattern. Users can navigate without the file dialog.
- Cons: `QFileSystemModel` is slow on large filesystems. Must scope it to `ROOT_DIR` or the user's home directory.

**D — Most-recently-used paths in the path field**
Add a dropdown (▼ button beside the path input) showing the 10 most recent paths. Selecting one re-loads that directory. Simpler than a history stack.
- Pros: Covers the most common use case (returning to previous sessions). 
- Cons: No true back/forward; just a MRU list.

**Recommendation:** D first (MRU is fastest to implement, pairs with §2.9 session persistence). A as true back/forward navigation. B as the polish layer.

---

## 2.22 Tag Chip UI and Compound Tag Search ✅ Partial (2026-07-30 — §A TagChipWidget + §D TagCompleter shipped, issue #127 — In review) {: #222-tag-chip-ui-and-compound-tag-search }

**Pain point:** The search and scan metadata tabs use `QListWidget` for tag display (implemented to avoid per-QCheckBox memory cost). While this is correct for large tag sets, the visual style is a plain list item — not a modern chip/badge that makes tag relationships scannable at a glance.

### Options

**A — Chip-style tag badges using QLabel in a flow layout [Quick Win]**
Replace the tag `QListWidget` with a custom flow layout (`FlowLayout`) of small `QLabel` widgets styled as chips (rounded rectangle, coloured background per tag type). Clicking a chip toggles it.
- `FlowLayout` implementation: [Qt flow layout example](https://doc.qt.io/qt-6/qtwidgets-layouts-flowlayout-example.html)
- Pros: Modern visual appearance. Natural word-wrap reflow on resize.
- Cons: Flow layout must handle thousands of tags efficiently (virtualise beyond N=200).

**B — Bubble-style QComboBox with checkboxes**
A `QComboBox` subclass that shows a checklist popup and renders selected items as removable chips in the line edit area. Common in web forms.
- Pros: Compact. Familiar UX.
- Cons: Complex `QComboBox` subclass. Must be keyboard-accessible.

**C — Compound tag search (AND / OR / NOT)**
Extend the tag search `QLineEdit` to support operators: `red_eyes AND blue_hair`, `sword OR staff`, `NOT chibi`. Parser uses a simple recursive descent or `pyparsing`.
- Pros: Expressive. Handles complex tag queries that the current flat search cannot.
- Cons: `pyparsing` dependency (or custom parser). Must display parse errors gracefully.

**D — Tag autocomplete (QCompleter)**
Wire a `QCompleter` populated from `get_all_tags_from_db()` to the tag search field. As the user types, suggestions drop down from the database tag vocabulary.
- Pros: Dramatically speeds up tag entry. Already have `refresh_subgroup_autocomplete` in `database_tab.py` — extend this pattern.
- Cons: Autocomplete list must update when new tags are added mid-session.

**Recommendation:** D first (QCompleter on search fields, ~1h). A for visual upgrade. C for power users who construct complex tag queries.

---

## 2.23 Accessibility and Keyboard Tab Order ✅ Partial (2026-06-10 — §A accessible names on pagination widgets) {: #223-accessibility-and-keyboard-tab-order }

**Pain point:** No `setAccessibleName()` calls, no explicit `setTabOrder()`, and no testing with screen readers. High-contrast mode and font scaling are not addressed. For a power-user tool managing thousands of files, keyboard-only navigation (no mouse) is both an accessibility requirement and a daily-use efficiency gain.

### Options

**A — Accessible names on all interactive widgets [Quick Win]**
Add `widget.setAccessibleName("descriptive name")` and `widget.setAccessibleDescription("...")` to all buttons, inputs, and gallery thumbnails. Required for screen readers (Orca on Linux, NVDA on Windows).
- Pros: Low effort. Required for WCAG 2.1 AA compliance.
- Cons: Must audit every tab (~150 interactive widgets).

**B — Explicit QWidget tab order per tab**
Call `QWidget.setTabOrder(a, b)` to define a logical Tab key traversal order in each tab. Currently Tab order follows widget construction order, which is rarely the logical flow.
- Pros: Keyboard-only users can work efficiently. Easy to validate with Tab key testing.
- Cons: Must re-audit when UI layout changes.

**C — High-contrast theme variant**
Add a `high_contrast.qss` that uses WCAG AA minimum contrast ratios (4.5:1 for normal text, 3:1 for large text). Expose via the Theme setting (§2.8).
- Pros: Essential for visually impaired users.
- Cons: Requires auditing every colour in the theme. Labour-intensive.

**D — Font size scaling**
Add a "Font Scale" spinbox (80%–150%) to the settings window. Apply via `QApplication.instance().setFont(QFont("", base_size * scale))`.
- Pros: Useful for high-DPI displays and users who need larger text.
- Cons: Some fixed-width layouts break at font size > 120%.

**E — Focus ring visibility**
Ensure `QFocusFrame` or QSS `:focus` selectors provide a visible focus ring on all focusable widgets. Currently some buttons and list items have no visible focus indicator.
- Pros: Required for keyboard navigation to be usable.
- Cons: QSS `:focus` rules must be added to both `dark.qss` and `light.qss`.

**Recommendation:** A + B + E are minimum viable accessibility requirements. C + D in a dedicated accessibility sprint.

---

## 2.24 Thumbnail Hover Animations ✅ Partial (2026-06-10 — §A shipped) {: #224-thumbnail-hover-animations }

**Pain point:** Thumbnails are static `QLabel` / `DraggableLabel` widgets with no hover response. Modern image management apps (Eagle, Hydrus) animate thumbnails on hover (subtle scale-up, brightness lift, border highlight) to improve visual responsiveness and make the selection state feel tactile.

### Options

**A — CSS :hover border highlight [Quick Win]**
Add `:hover { border: 2px solid #5865f2; }` to the thumbnail label QSS. Already half-done for selected state. This is a zero-Python change.
- Pros: Instant, no animation needed. Consistent with web-style hover cues.
- Cons: Static border change; no smooth transition.

**B — QPropertyAnimation scale on hover**
Override `enterEvent` and `leaveEvent` in `DraggableLabel`. On enter: `QPropertyAnimation(label, "geometry")` from the current rect to a rect 5% larger (centred). On leave: reverse. Duration: 100ms, easing: `QEasingCurve.OutCubic`.
- Pros: Smooth, tactile feedback. 100ms is imperceptible but noticeable.
- Cons: Geometry animation on a grid cell shifts adjacent items. Must use a fixed-size cell approach (expand within the label's bounding box, not outside it).

**C — Opacity pulse on loading completion**
When a thumbnail finishes loading (signal from `BatchImageLoaderWorker`), briefly animate the label's opacity from 0.0 → 1.0 over 150ms. Gives a "fade-in" feel.
- Pros: Makes asynchronous load visible and smooth.
- Cons: `QGraphicsOpacityEffect` per label; many concurrent effects may impact performance.

**D — Selection check overlay (animated)**
When an image is added to the selection, animate a check mark icon overlaid on the thumbnail (scale 0 → 1, duration 120ms). For deselection, fade out.
- Pros: Clear selection state without relying solely on the border colour.
- Cons: Overlay widget must be positioned over the `DraggableLabel`. Z-order management required.

**Recommendation:** A immediately (CSS-only, free). C for loading polish. B + D as optional animation layer when the virtual scroll (§2.1A) is implemented.

---

## 2.25 Keyboard Shortcut Discovery Overlay ✅ (2026-09-05 — Options A & B shipped with Keycap and Scope badge delegates) {: #225-keyboard-shortcut-discovery-overlay }

**Shipped: Options A & B.**
- **Option A & B (Searchable Cheat Sheet & Keycap Badges)**: Dedicated `ShortcutDiscoveryDialog` (`gui/src/components/dialogs/shortcut_discovery_dialog.py`) opened with `Ctrl+/` or `F1`. Features scope filter pill tabs (`All`, `General`, `Gallery`, `Preview`, `Stitch`, `Convert`, `Merge`), live search with match counts, customized `KeycapBadgeDelegate` rendering `<kbd>`-style rounded keycaps with modifier separation, and `ScopeBadgeDelegate` rendering color-coded scope pills.
- **Tests**: `gui/test/dialogs/test_shortcut_discovery_dialog.py` (4 unit tests).

### Options

**A — Ctrl+/ or F1 shortcut table overlay [Quick Win]**
A modal `QDialog` opened by `Ctrl+/` (or `F1`) showing a two-column table of all registered shortcuts and their descriptions. Populated from a `SHORTCUT_REGISTRY: list[dict]` that tabs register into at construction.
- Pros: Standard pattern (VS Code, Figma, most modern apps). Easy to implement.
- Cons: Registry must be populated — requires auditing all existing `QShortcut` instances.

**B — Contextual shortcut tooltip on button hover**
Add `setToolTip("Open Preview (Enter)")` to every interactive button. The shortcut is discoverable by hovering. Tooltip QSS already styled in the theme.
- Pros: Contextual — only shows relevant shortcuts. Zero new infrastructure.
- Cons: Does not help for non-button shortcuts (arrow keys, Delete, Ctrl+scroll).

**C — Interactive shortcut editor**
Extend the settings window (§2.9) with a "Keyboard Shortcuts" tab that lists all registered shortcuts and allows remapping via `QKeySequenceEdit`. Saved to `~/.config/image-toolkit/keybindings.json`.
- Pros: Power-user feature. Enables personalised workflows.
- Cons: High effort. Requires all shortcuts to use the registry rather than hardcoded `QKeySequence` values.

**D — Tab-level shortcut bar in status bar**
Show the 3–4 most relevant shortcuts for the current tab in the status bar (§2.10C). Changes automatically when the active tab changes.
- Pros: Always visible. Context-sensitive.
- Cons: Status bar space is limited. At most 3 shortcuts fit readably.

**Recommendation:** B immediately (tooltip-based discovery is zero-effort). A as the authoritative shortcut reference. C for the long-term keyboard-first power-user experience (pairs with §2.3B global hotkey table).

---

## 2.26 Inline Rename ✅ (2026-09-05 — Options A & B shipped with Undo/Redo integration) {: #226-inline-rename }

**Shipped: Options A & B with Undo/Redo.**
- **Option A & B (`F2` / Context Menu Rename)**: Pressing `F2` or choosing "Rename..." triggers an input dialog pre-filled with the current basename, sanitizes forbidden filename characters, renames the file via `UndoManager.rename_file_undoable()`, updates `VirtualGalleryModel` paths and overlay metadata (ratings, resolutions, formats, tag counts, cached pixmaps), and emits `path_renamed(old_path, new_path)`.
- **Undo/Redo Recovery**: Fully undoable with `Ctrl+Z` / `Ctrl+Shift+Z`.
- **Tests**: `gui/test/gallery/test_inline_rename.py` (3 unit tests).

### Options

**A — F2 inline edit in gallery thumbnail [Quick Win]**
When a thumbnail has focus (selected), press `F2` to replace the filename label with an in-place `QLineEdit` pre-filled with the current filename (no extension). On `Enter` or focus-out, call `os.rename(old_path, new_path)` and update internal path lists.
- Pros: Standard OS file manager pattern. Low effort if the filename label already exists below the thumbnail.
- Cons: Must handle name conflicts, invalid characters, and extension visibility.

**B — Rename dialog from context menu**
Right-click → "Rename..." opens a `QInputDialog.getText()` pre-filled with the current basename.
- Pros: Simpler than inline edit. Already have `QInputDialog` usage in several tabs.
- Cons: A modal dialog for a rename is heavier UX than pressing F2.

**C — Batch rename with pattern**
"Rename selection with pattern" (e.g., `{date}_{index:03d}_{original}`). Pattern input via a `QDialog` with a preview of the first 5 results.
- Pros: High value for organizing scraped/exported collections with inconsistent names.
- Cons: Pattern engine adds complexity. Requires robust conflict detection.

**D — Rename and update database reference**
After renaming, emit a signal to update the `images.path` column in the database for the renamed file.
- Pros: Keeps database state consistent.
- Cons: Depends on database connection being active. Should be a soft update (best-effort).

**Recommendation:** B first (context menu rename, 30 minutes). A as the primary keyboard interaction. C for batch rename power users. D always when A or B is implemented.

---

## 2.27 Multi-Image Comparison View ✅ (2026-08-22) {: #227-multi-image-comparison-view }

**Shipped: Options A, B, and C.** Dedicated `ImageCompareWindow` (`gui/src/windows/image_compare_window.py`) supporting:
- **Option A (Side-by-side)**: Multi-pane layout in a `QSplitter` with synchronized drag-panning and linked zoom factor across all loaded images (`SynchronizedImagePane`).
- **Option B (A/B Overlay)**: Single-pane view with `Tab`/`Space` image flipping and a real-time crossfade opacity/blend slider.
- **Option C (Difference map)**: Pixel difference computation via `QPainter.CompositionMode_Difference` and numpy RGB channel amplification (1×, 2×, 5×, 10×, 20×).
- **Gallery Entry Points**: Added "Compare Selected (N)… (C)" action to `AbstractClassTwoGalleries` context menu, `C` keyboard shortcut in `_keyboard_nav.py`, shortcut registry binding `gallery.compare_selected`, and `VirtualGallery.compare_selected()` helper.
- **Tests**: `gui/test/windows/test_image_compare_window.py` (7 unit tests).

**Pain point:** The `ImagePreviewWindow` opens one image at a time. Users comparing near-duplicate outputs (e.g., ASP vs. SCANS results, or two LoRA generations) must switch between two separate preview windows manually. A side-by-side view does not exist in the general gallery — only the stitch-specific before/after in §2.6.

### Options

**A — 2-up / 4-up comparison dialog**
A dedicated `QDialog` with a 1×2 or 2×2 grid of `QScrollArea` + `QLabel` cells, each showing one image at the same zoom/pan state (synchronized scroll). Opened by selecting 2–4 images and pressing `C` (or context menu "Compare").
- Pros: Standard lightbox comparison feature. Synchronized scroll makes pixel-level comparison easy.
- Cons: Synchronized scroll requires mapping viewport offsets across all cells. Medium effort.

**B — Overlay / blink comparison**
A single viewer with an "A/B toggle" button (or `Tab` key) that swaps between two selected images. Optionally: animated fade or checkerboard split.
- Pros: Easier to implement than synchronized scroll. Good for comparing overall aesthetics.
- Cons: Cannot compare two regions simultaneously (only sequential).

**C — Difference map overlay**
An additional view mode: `|Image A − Image B|` per pixel, normalised to 0–255 and colour-mapped (e.g., hot colourmap). Shows exactly which regions differ.
- Pros: Precise quality analysis. Especially useful for ASP vs. SCANS comparison.
- Cons: Requires `numpy` computation (fast) but the result image is a synthetic artefact — must be clearly labelled as "difference".

**D — Extend ImagePreviewWindow to multi-pane**
Add an optional second `QScrollArea` pane to the existing `ImagePreviewWindow`, activated when a second image is passed. Avoids creating a new dialog class.
- Pros: Reuses existing infrastructure.
- Cons: `ImagePreviewWindow` is already complex. Adding a second pane changes its layout significantly.

**Recommendation:** B first (overlay toggle, ~1 day). A for pixel-level comparison work. C for ASP quality analysis workflows (pairs with §2.6D).

---

## 2.28 Global Cross-Tab Search ✅ (2026-08-01, issue #45) {: #228-global-cross-tab-search }

**Shipped: Option A (in-memory search across loaded tabs).** `Ctrl+Shift+F` opens a floating popup (`gui/src/windows/main/_global_search.py`, `_GlobalSearchMixin`, mirroring `_tab_search.py`'s Ctrl+T popup shape) that filters over every gallery-like tab's `master_found_files`/`master_image_paths` as-you-type, grouped by tab, and jumps to the selected hit via the same `command_combo` + `_select_tab_by_name` cross-tab-activation pattern DB.8 established. A new per-gallery `jump_to_path(path)` (added to both `AbstractClassTwoGalleries`/`_found_gallery_load.py` and `AbstractClassSingleGallery`/`_geometry_events.py` — no such primitive existed before) isolates the target file by filtering the tab's own search box down to its exact basename, reusing the existing debounced-search machinery instead of adding new pagination/highlight logic. `ConvertTab` doesn't itself expose a path list (it composes `format_subtab`/`codec_subtab`/`sampler_subtab`, each a real gallery) — `_iter_gallery_tabs()` checks those three nested attributes one level down so Convert's subtabs are still searchable; `ExtractorTab`'s existing `__getattr__` delegation to `VideoExtractorSubTab` needed no special-casing. New `general.global_search` entry in the shortcut registry (`Ctrl+Shift+F` default, remappable like every other action). Capped at 200 results so a very large library doesn't build an unbounded popup list.

Options B/C/D (per-tab-input broadcast, Postgres-backed, OS `locate`) not pursued — A covers the in-memory case with zero new dependencies, and C's premise (a running PostgreSQL connection) no longer applies now that `unified_database.md` has retired Postgres in favor of the unified SQLCipher store.

Tests: `gui/test/core/test_global_search.py` (3, incl. the Ctrl+Shift+F key-dispatch and ConvertTab-subtab-discovery cases), `gui/test/image/test_gallery_classes.py` (+4 `jump_to_path` cases across both gallery base classes).

**Pain point:** Each gallery tab has its own search input, and there is no unified way to search across all loaded galleries simultaneously. A user who doesn't know which tab contains a specific file must search each tab manually.

### Options

**A — Ctrl+Shift+F global search overlay**
A floating, translucent `QWidget` (like a command palette but for paths) that searches across `master_found_files` and `master_image_paths` of all instantiated tab instances. Results grouped by tab, with a click jumping to that tab and selecting the image.
- Pros: Zero dependencies. All the data is already in memory.
- Cons: Must query tab instances from `main_window.all_tabs`. Must avoid blocking the main thread for large libraries.

**B — Search all tab search inputs simultaneously**
Ctrl+Shift+F focuses all tab search inputs at once, applying the same query across every active tab. Result counts are shown in each tab's title badge.
- Pros: Simpler than A — reuses per-tab filtering logic.
- Cons: User must switch tabs to see results. Does not aggregate results in one place.

**C — Database-backed global search**
Route global search through the PostgreSQL full-text index on `images.path`. Returns results from all indexed images regardless of which tab they are in, then opens the file in the appropriate tab.
- Pros: Scales to millions of images. Includes files not currently visible in any gallery.
- Cons: Only works for indexed images. Requires a running PostgreSQL connection.

**D — File system index (lightweight, OS-native)**
On Linux, call `locate <query>` or `find` within scanned directories for instant filesystem search. Returns paths directly, not gallery-integrated results.
- Pros: Near-instant on a `locate` index. Zero dependency.
- Cons: `locate` database may be stale. Not integrated with gallery state.

**Recommendation:** A first (in-memory across loaded tabs, highest integration). C for large indexed collections (pairs with §4.3 CLIP search in `new_features.md`).

---

## 2.29 Configurable Keyboard Shortcuts ✅ (2026-06-10) {: #229-configurable-keyboard-shortcuts }

**Pain point:** Every keyboard shortcut in the app (`F2` rename, `Ctrl+E` export, `Del` delete, arrow navigation, etc.) is hardcoded via `QKeySequence` or string literals scattered across 6+ files. Users who prefer different bindings (e.g., Vim-style, or to avoid conflicts with their window manager) have no reconfiguration path. The feature is already referenced as the long-term plan in §2.3B and §2.25C.

### Options

**A — `QKeySequenceEdit` table in settings, JSON persistence [Recommended]**
Add a "Keyboard Shortcuts" tab to `SettingsWindow`. Populate it from a `SHORTCUT_REGISTRY: list[dict]` (each entry: `id`, `description`, `default`, `scope`). Each row shows the action name, current binding, and a `QKeySequenceEdit` for remapping. On save, write to `~/.image-toolkit/keybindings.json`. On startup, `MainWindow.__init__` reads this file and applies any overrides to the corresponding `QShortcut` objects.
- Conflict detection: highlight duplicate bindings in red before saving.
- Reset button per row and global "Restore Defaults" button.
- Scope column shows which tab/context the shortcut applies to.
- Pros: Standard power-user feature. JSON file is user-auditable. `QKeySequenceEdit` is a native Qt widget — no custom code for capture.
- Cons: All existing `QShortcut` objects must be registered into the registry at construction time. Requires one pass through all 6 files that define shortcuts.

**B — Vault-stored shortcuts**
Same as A but persist into the existing vault instead of a plain JSON file.
- Pros: All user configuration in one encrypted store.
- Cons: Shortcuts are not security-sensitive. Plain JSON is preferable (user-editable, survives vault reset). Vault is overkill here.

**C — Per-tab QShortcut override via settings (no registry)**
Each settings tab section shows a flat list of known shortcuts for that tab. Stored per-tab in `QSettings`. No central registry.
- Pros: Easier per-tab scoping.
- Cons: No global conflict detection. Discovery is per-tab only — user cannot see all shortcuts at once.

**D — Application-context shortcuts only (non-configurable tab shortcuts)**
Only make app-global shortcuts configurable (e.g., Command Palette `Ctrl+K`, global search `Ctrl+Shift+F`). Tab-internal shortcuts remain hardcoded.
- Pros: Lower scope. Covers the most commonly conflicting shortcuts.
- Cons: Leaves per-gallery shortcuts (F2, Ctrl+E, Del) unconfigurable — the highest-demand items.

**Recommendation:** A — JSON registry approach. `QKeySequenceEdit` + `SHORTCUT_REGISTRY` is a one-time investment that covers all future shortcuts automatically once the registry discipline is established.

**Update (2026-08-01) — KDE System Settings-style multi-shortcut editor.** The original single-`QKeySequenceEdit`-per-row table is replaced with a two-pane editor matching KDE's own Shortcuts module: a left-hand list of "functionalities" (shortcut scopes -- Gallery, Preview, General -- each with an icon) where selecting one shows its actions on the right, each with an independently-togglable default shortcut plus any number of custom shortcuts (pill + delete button, "+ Add..." to capture a new one), mirroring the reference screenshots exactly (default shortcut near the action name, custom shortcuts to the right). `shortcut_manager.py`'s `ShortcutRegistry` now stores `{"default_enabled": bool, "custom": [str, ...]}` per action instead of one override string, backward-compatible with the old flat-string `keybindings.json` format. Conflict detection on save is scoped per-scope (Gallery and Preview both reusing `Left`/`Right` for unrelated, never-simultaneously-active navigation is not a real conflict -- flagging it cross-scope produced a blocking false-positive dialog every save). The shortcuts groupbox is now built directly into its tab (not the shared `create_tab_scroll_area()` helper, whose `AlignTop` layout + trailing stretch shrank it to content) so it fills the available tab height instead of showing only a few rows. Also added `general.save_tab_config` (default `Ctrl+S`) to the registry -- see §2.16H below for what it does.

**Update (2026-08-04) — `general.load_tab_config` (default `Meta+S`), the load counterpart to Ctrl+S.** `_open_save_tab_config_dialog()` could only *save* a named profile for the active tab; there was no shortcut to load one back in without going through Settings' full "Tab Default Configuration Management" section. `gui/src/windows/main/_load_tab_config.py` (`_LoadTabConfigMixin`) adds Meta+S: resolves the active tab the same way Ctrl+S does (`command_combo.currentText()` + `tabs.tabText(tabs.currentIndex())`), reads that tab class's saved configs from the same `tab_configurations` vault store, and shows a picker dialog (`QListWidget` of saved names, double-click or OK to load) that calls the selected config through `tab_instance.set_config(...)`. Warns if the active tab doesn't implement `set_config`, or informs if it has no saved configs yet, rather than silently no-opping.

---

## 2.30 Accent Color and UI Density Customization ✅ {: #230-accent-color-and-ui-density-customization }

**Status:** Implemented (2026-06-10). Options A (accent colour picker), B (font scale), and C (density toggle) all shipped together.

**Pain point:** The app's dark theme uses a fixed cyan accent (`#00bcd4`) and the light theme uses blue (`#007AFF`). The QSS system already uses `$DARK_ACCENT_COLOR` template variables (via `Template.safe_substitute` in `style.py`), so injecting a custom accent is a matter of overriding the variable before substitution. Users also report discomfort at the default font size on high-DPI displays, and no compact/comfortable density toggle exists.

### Options

**A — Accent colour picker (QColorDialog) in settings [Quick Win]**
Add a colour picker button to the "Preferences" section of settings. On click: `QColorDialog.getColor()`. The chosen hex is stored as `preferences["accent_color_dark"]` / `preferences["accent_color_light"]` in the vault. In `set_application_theme()`, override `THEME_VARS["DARK_ACCENT_COLOR"]` (and the hover/pressed/muted variants computed automatically: hover = darken 15%, pressed = darken 25%, muted = desaturate 80%) before `Template.safe_substitute`. Zero new dependencies.
- Pros: Already-templated QSS means this is ~30 LOC. Live preview if `set_application_theme` is called on dialog accept.
- Cons: Hover/pressed/muted variants must be computed programmatically (`QColor.darker()`/`QColor.lighter()`).

**B — Font scale slider in settings**
A `QSlider` (80–150%, step 10%) in the "Gallery and Display" section. Applies via `QApplication.instance().setFont(QFont("", base_pt * scale))`. Stored as `preferences["font_scale"]`. Restores on startup before first paint.
- Pros: Accessibility improvement for high-DPI users. No QSS changes needed.
- Cons: Some fixed-width layout elements may clip at >120%. Should display a "restart required" note for safety.

**C — Layout density toggle (Compact / Comfortable / Spacious)**
Three presets that adjust `QWidget` padding/spacing in the QSS. Compact: 4px padding, 2px spacing. Comfortable (current): 10px/6px. Spacious: 16px/10px. Applied as a QSS override.
- Pros: Useful on laptops (Compact) vs large monitors (Spacious).
- Cons: Some layouts have hardcoded `setContentsMargins` — QSS padding may not override those. Medium effort.

**D — All three (A + B + C) in a unified "Appearance" settings tab**
Group accent colour, font scale, and density into a single "Appearance" tab in `SettingsWindow` alongside a live preview `QFrame`.
- Pros: Cohesive UX. Avoids scattering appearance controls across multiple sections.
- Cons: Larger change to `SettingsWindow` layout.

**Recommendation:** A immediately (near-free given template infrastructure). B for accessibility. D as the unifying step once A and B are validated.

---

## 2.31 Custom QSS User Theme Override ✅ (2026-06-10) {: #231-custom-qss-user-theme-override }

**Pain point:** Advanced users who want a fully custom visual style must edit `dark.qss` or `light.qss` directly and risk losing changes on update. There is no supported path for injecting personal style overrides without touching tracked files.

### Options

**A — User override file appended after base theme [Quick Win]**
After loading the base dark/light QSS, check for `~/.image-toolkit/user_theme.qss`. If present, read its contents and append to the base QSS string before `QApplication.setStyleSheet`. The override file is pure QSS (no template variables); it can selectively override any widget rule. Documentation hint shown in settings.
- Pros: Zero new dependencies. Non-destructive — base theme still applies first. Users can share override files.
- Cons: Override file must be manually created. No in-app editor.

**B — In-app QSS editor in settings**
A `QPlainTextEdit` in a "Developer" section of settings showing the current full QSS. User can edit and press "Apply" to preview changes live. Saved to `user_theme.qss`.
- Pros: Discoverable and usable without leaving the app.
- Cons: A bad QSS can break the UI. Should have a "Reset to Default" button that clears `user_theme.qss`.

**C — Preset colour palette swatches**
Instead of free-form editing, offer 6–8 preset colour palettes (Dracula, Solarized Dark, Monokai, Catppuccin, etc.) as a dropdown. Each palette overrides only the `$DARK_ACCENT_COLOR` and background variables.
- Pros: Safe — no freeform QSS. Users who don't know CSS can still personalise.
- Cons: Fixed palette selection; no bespoke customisation.

**Recommendation:** A as the power-user override path (trivial implementation). C as a quick-win discovery path for users who don't know QSS.

---

## 2.32 Window Layout and State Profiles ✅ Partial (2026-06-10 — geometry only) {: #232-window-layout-and-state-profiles }

**Pain point:** `SettingsWindow` already has "System Preference Profiles" that save theme + tab configs, but they do not capture window geometry, splitter positions, or the last-used panel sizes. Every launch resets the layout even for users with established workflows. `QSplitter` persistence (§2.20A) addresses individual splitters; this section addresses the complete workspace layout as a named, switchable profile.

### Options

**A — Auto-save geometry and splitter state on close [Quick Win]**
In `MainWindow.closeEvent`, call `QSettings.setValue("window/geometry", self.saveGeometry())` and save the state of all tracked `QSplitter` instances. Restore in `__init__` before `show()`. No profile concept — just last-used state.
- Pros: One-time save/restore, zero UI. Highest-impact change with least effort. Pairs naturally with §2.20A.
- Cons: Only one state remembered (the last session). No named profiles.

**B — Named layout profiles in settings**
Extend the existing "System Preference Profiles" to include window geometry + all splitter states. A profile name stores: `{"geometry": base64(saveGeometry()), "splitters": {"stitch_tab": base64(...), ...}}`. Profiles can be applied from the Settings window or a `File → Layout Profiles` menu.
- Pros: Named profiles enable project-based layouts (e.g., "stitching session" vs "database review").
- Cons: Must hook into all QSplitter instances to collect/restore their state. Medium effort.

**C — Per-tab layout memory**
Each tab class saves and restores its own internal splitter + scroll position in `QSettings` keyed by tab class name. No cross-tab coordination.
- Pros: Scoped — each tab owns its state. Simpler than B.
- Cons: Does not capture main window size or multi-tab interactions.

**Recommendation:** A immediately (matches §2.20A and is essentially the same code path). B as the full profiles upgrade once A validates the save/restore pattern.

---

## 2.33 Extractor Tab Playback Engine — libmpv Integration {: #233-extractor-tab-playback-engine--libmpv-integration }

**Pain point:** The Extractor tab's internal player is built on `QMediaPlayer`/`QGraphicsVideoItem`. Repeated attempts (2026-07) to make the main player itself track the playhead in real time during a drag — subprocess-per-frame extraction, a background dense-keyframe H.264 "scrub proxy," and finally a persistent in-process PyAV decoder feeding an overlay pixmap — all ran into some combination of latency, image quality, or `QMediaPlayer`/`QVideoSink` surface-swap timing bugs (aspect-ratio corruption on release, a stale-frame "flash" between the pre-drag and post-drag frame, and a final regression that only manifested under real interactive dragging, never in scripted reproductions). The conclusion: the class of bug repeatedly hit is inherent to driving `QMediaPlayer`'s own video surface at drag speed, not something a better preview-fetching algorithm alone fixes.

The chosen near-term fix (§4.14, tracked in `new_features.md`) is a YouTube-style storyboard/sprite-sheet scrub preview shown in a small floating widget above the slider, which never touches the main player's surface during the drag at all — see that section for the accepted design. This section instead tracks the complementary, larger initiative: giving the *main player itself* fast, high-quality seeking, by swapping its engine to `libmpv` — the same engine Haruna (the reference UX for this feature) is built on.

### Options

**A — Embed via `python-mpv` + native window ID (`wid`)**
`python-mpv` is a ctypes wrapper around `libmpv`. Hand it the native window handle of a Qt widget (`int(widget.winId())`) and let mpv render into it directly, replacing `QMediaPlayer`/`QGraphicsVideoItem` as the Extractor tab's internal engine. mpv owns seeking, its own demuxer cache, and hr-seek/keyframe-seek tuning — this is literally Haruna's own approach, not an approximation of it.
- Pros: Highest ceiling — inherits 15+ years of tuned scrub-seek behavior for free. No custom decode/overlay code to maintain going forward.
- Cons: New native dependency (`libmpv`/`libmpv2`). Per this project's own history (three prior SIGSEGVs from JPype/JVM colliding with lazily-loaded native GPU/media libs — GTK file dialog, QWebEngineView/Chromium, QMediaPlayer FFmpeg VA-API — see `jvm_native_lib_conflicts` in project memory), a fourth native lib coexisting with the JVM needs a deliberate isolated smoke test before wiring it into the main app. Window embedding (`wid`) is straightforward on X11 but meaningfully more fragile on Wayland (frequently requires falling back through XWayland) — worth confirming the target session type first. This is a genuine engine swap, not a small patch: audio routing, playback-speed control, and the existing AV1/VP9 H.264-proxy workaround (`transcoded_playback.py`) would all need to be re-plumbed through mpv's own APIs (mpv can decode AV1/VP9 natively via ffmpeg, likely obsoleting that proxy entirely) or bridged.

**B — mpv render API into a `QOpenGLWidget`**
Instead of native window embedding, use mpv's render API to draw into an OpenGL context Qt owns (`QOpenGLWidget`), pulling frames via a render callback instead of handing mpv a raw window handle.
- Pros: Avoids the X11/Wayland window-embedding fragility of Option A entirely — works identically on both since Qt owns the surface. More natural fit for compositing mpv's output with Qt-drawn overlays (e.g. the storyboard preview widget, HUD elements) in the same widget.
- Cons: More integration code than `wid` embedding (explicit OpenGL context sharing, render callback wiring). Requires `PyOpenGL` or equivalent alongside `python-mpv`.

**C — Status quo (`QMediaPlayer`) + debounced seeks only**
Keep `QMediaPlayer` as the engine; rely on the storyboard preview (§4.14) for the live-drag visual, and only ever call `QMediaPlayer.setPosition()` when the drag pauses or releases (not on every tick), reusing the existing `videoSink().videoFrameChanged`-gated safe-reveal logic.
- Pros: Zero new dependencies, zero engine-swap risk. Already-fixed bugs (aspect ratio, release flash) stay fixed because the code paths that caused them aren't exercised at drag speed anymore.
- Cons: The main player's seek latency (observed ~100-300ms per real seek) is still whatever `QMediaPlayer` gives you on pause/release — noticeably slower to "settle" than mpv's own seeking, just no longer perceptible as continuous stutter since it doesn't fire on every tick.

---

## 2.34 Custom Theme Engine & Semantic Color System ✅ Locked, unimplemented (2026-08-18 — issues #437-441) {: #234-custom-theme-engine--semantic-color-system }

**Pain point:** The application currently provides a binary Dark/Light theme toggle with fixed accent colors. Users have diverse display calibrations, aesthetic preferences, and accessibility requirements (e.g. high-contrast surfaces, custom typography, or personalized branding). There is currently no unified semantic color customization interface, dynamic color extraction engine, or in-app style editing with live preview.

### Options

**A — Semantic Color Palette & Theme Generator**
A structured visual palette customizer in Settings exposing five core semantic color slots: Primary Accent, Surface/Card Background, Window Background, Text (Primary & Muted), and Border/Dividers. Includes WCAG 2.1 AA auto-contrast validation indicators to guarantee legibility, plus widget styling controls (Corner Radius: Sharp 0px / Subtle 4px / Rounded 8px / Pill 16px; Shadow Elevation; Application Font Family & Scale overrides).
- Pros: Structured, safe, and impossible to break UI layout. High accessibility value.
- Cons: Does not allow arbitrary QSS rule injection for edge-case widgets.

**B — Dynamic Image-Driven Palette Extraction (Material You / PyWal Style)**
An automated color extractor that samples the user's active background art or desktop wallpaper using $k$-means / median-cut quantization, extracting dominant, vibrant, and muted tones to generate a harmonious semantic palette automatically.
- Pros: Seamless aesthetic cohesion between background artwork and UI controls. Zero-friction personalization.
- Cons: Requires fallback handling for low-contrast or monochromatic source images.

**C — In-App Live QSS Stylesheet Editor**
An embedded code editor (`QPlainTextEdit` with syntax highlighting and instant "Apply Live" hot-reloading) targeting `~/.image-toolkit/user_theme.qss`, with automatic syntax validation and a one-click fail-safe "Reset to Default" button.
- Pros: Maximum flexibility for power users to customize any Qt selector, pseudo-class, or transition.
- Cons: Malformed CSS can temporarily distort layout if syntax validation is bypassed.

**Locked (2026-08-18):** Phase 1 targets the host PySide6 GUI and host-owned
tabs; embedded HIE/CSG/ASP surfaces receive adapters later. Theme Studio
controls palette, density, corners, typography, shadows, and motion.
Contrast ratios are warnings rather than save blockers. Invalid token or
QSS previews apply transactionally and roll back to the last valid snapshot.
Raw QSS uses a safe styling mode by default, with an explicit expert toggle
for unrestricted selectors/properties. Shared JSON schema: #437 (foundational,
blocks the rest). Theme Studio UI: #438 (deepseek). QSS editor + export/
import: #441 (deepseek). See `app_theming_2026q3.md` for the full design.

**Recommendation:** Implement A as the default visual customizer, integrate B
as an opt-in background-derived palette action, and provide C in an Advanced
subtab behind the explicit expert toggle.

---

## 2.35 Full-Window Background Canvas & Glassmorphic Layering ✅ Locked, unimplemented (2026-08-18 — issues #437, #439, #440) {: #235-full-window-background-canvas--glassmorphic-layering }

**Pain point:** Application windows and tab content render against solid, opaque background surfaces. Users cannot personalize their workspace with custom background art, photo collections, or modern translucent "glassmorphic" (Mica / acrylic / frosted glass) layered surfaces.

### Options

**A — Full-Window Layered Background Canvas with Frosted Glass Blur**
Renders a user-selected background image beneath the root application window with configurable opacity ($0.10$–$1.0$) and backdrop blur radius ($0$–$30\text{px}$). Content areas, toolbars, and gallery cards render with translucent glassmorphic surfaces (`rgba(255, 255, 255, alpha)` in Light mode / `rgba(30, 30, 30, alpha)` in Dark mode) to ensure foreground text and image thumbnails remain sharp and legible.
- Pros: Modern, immersive visual aesthetic. Works across all tabs uniformly.
- Cons: Backdrop blur requires efficient pixmap caching off the main thread to avoid paint lag during window resizing.

**B — Multi-Image Slideshow Playlist & Cross-Fade Transitions**
Supports selecting a folder or playlist of background images with automatic slideshow rotation on a configurable interval (1m, 5m, 15m, 1h, or on startup), utilizing smooth alpha cross-fade transitions between frames.
- Pros: Keeps the workspace dynamic and pairs directly with the existing Wallpaper/Slideshow daemon.
- Cons: Memory management required to evict cached background pixmaps between transitions.

**C — Fit & Scaling Modes (Cover, Contain, Center, Tile)**
Provides aspect ratio scaling options for single or playlist background images to adapt cleanly across multi-monitor setups, ultrawide displays, and portrait orientations.
- Pros: Clean presentation regardless of display aspect ratio.
- Cons: Minor geometry calculation on resize events.

**Locked (2026-08-18):** Backgrounds support both linked paths and explicit
import into managed app storage. Portable theme packs carry token values
plus background references (`asset_ref`, defined in #437) and must report
missing assets. The host owns one global playlist clock; a per-tab image
override does not create a second timer. Static opacity remains the cheap
default, while blur is opt-in with adaptive-radius and cached-layer
fallbacks. Motion settings must honor a reduced-motion/low-performance
fallback.

**Recommendation:** Ship A + B + C together as an integrated host-only
"Aesthetics & Backgrounds" settings suite. Background canvas + glassmorphic
layering: #440 (Gemini). Palette extraction from the active background:
#439 (opencode). Both depend on #437 (schema, Claude).

---

## 2.36 Dual Navigation Shell & Modular Module Architecture ✅ Locked, unimplemented (2026-09-05 — issues #504, #509-514)

**Runtime architecture finalized 2026-09-05** after a Claude + Codex
brainstorm and user QA session — see
`docs/moon/roadmaps/ui_architecture_2026q3.md` for the accepted
module-catalog/lifecycle/event-bus design, the 6-step delivery
sequence, and open decision gates. That document supersedes the
`ModuleDescriptor`/`ShellLayoutManager` sketch below wherever they
conflict (notably: `MainWindow` stays the composition root rather than
`ShellLayoutManager` absorbing its mixins, and module descriptors are
Page/Workspace/Route-typed rather than 1:1 with a widget).

**Ergonomic pain point:**
The current desktop shell navigates across 25+ tool surfaces by selecting one of 7 top-level categories from a `QComboBox` ("Select Category:") to replace the contents of a single `QTabWidget`. This two-tier dropdown + tab bar mechanism creates a disjointed mental model, lacks iconography and badge indicators, fails to take advantage of wide/ultrawide displays, and tightly couples all tab instances to `MainWindow`. Adding or editing tools requires invasive modifications across `main_window.py` and its mixins.

### Implementation Options

**A — Declarative Module Registry & Dynamic Shell Layout Manager [Recommended]**
Decouple views and tools into declarative `ModuleDescriptor` records:
- Each tool implements metadata: `id`, `title`, `japanese_subtext` (e.g., `ライブラリ`), `category`, `icon_name` (vector SVG key), `view_factory` (lazy widget loader), `shortcut`, and `badge_provider` (e.g. active crawl count).
- `ShellLayoutManager` manages active views in a `QStackedWidget` and dynamically binds to either:
  1. **Vertical Navigation Rail**: Modern left sidebar with category groups, tool icons, tooltips, and collapsible drawer (`Ctrl+B`).
  2. **Top Segmented Ribbon**: Compact horizontal pill controls with category switcher for laptop displays.
- Automatic registration into the Command Palette (`Ctrl+K` / `Ctrl+P`) and runtime layout switching with `Ctrl+Shift+L`.
- *Pros:* Fully modular, plug-and-play architecture; tabs are decoupled and lazily loaded on first activation; caters to both widescreen monitors and compact screens.
- *Cons:* Requires abstracting tab initialization into factory descriptors.

**B — Hardcoded Vertical Sidebar**
Directly replace `QTabWidget` with a fixed left `QListWidget` or custom sidebar inside `MainWindow`.
- *Pros:* Simpler initial PR.
- *Cons:* Loses the top-tab mode entirely for small displays and fails to provide a modular plugin architecture for future extensions.

**Recommendation:** Option A. Establish `ModuleDescriptor` and `ShellLayoutManager` to future-proof the application architecture and provide seamless Rail vs. Top Bar layout switching.

**Optional post-rollout decision — classic-shell fallback.** Enable the new
shell by default. After real-user QA and release acceptance establish its
usability, decide whether the classic category/tab shell remains a preference
for one release cycle or indefinitely. The decision must be based on evidence:
navigation completion, keyboard accessibility, session/config restoration,
memory/startup behavior, and support burden — not a pre-implementation sunset
date.

---

## 2.37 Anime Creative Suite Visual System & Presets

**Ergonomic pain point:**
The default dark theme uses legacy Qt gradients and generic dark gray tones that lack aesthetic cohesion for an image toolkit centered on anime illustrations, manga editing, and generative vision models. Professional creative software (Clip Studio Paint, DaVinci Resolve, Adobe Lightroom) utilizes deep neutral studio slates that preserve color accuracy while offering high-contrast, customizable accents.

### Implementation Options

**A — Preset Theme Library, Danbooru Tag Palettes, & Bilingual Typography [Recommended]**
Expand the Theme Studio token system (`ThemePack`) with:
- **Curated Theme Presets**:
  - *Neo-Tokyo* (Deep Obsidian `#0e0f14` + Neon Cyan `#00f0ff` & Hot Crimson `#ff2a6d`)
  - *Sakura Blossom* (Soft Navy `#121118` + Sakura Pink `#ff70a6` & Violet `#a370f7`)
  - *Evangelion 01* (Dark Slate `#0f111a` + Toxic Purple `#9b5de5` & Acid Green `#00f5d4`)
  - *Catppuccin Mocha* (Pastel Dark `#1e1e2e` + Sapphire Blue `#89b4fa` & Mauve `#cba6f7`)
  - *Manga Ink* (Monochrome Screentone `#121212` + Pure White `#f8fafc` & Slate `#64748b`)
  - *Solarized Anime* (Studio Cyan `#002b36` + Amber Gold `#ffb703` & Teal `#2aa198`)
- **Danbooru/e621 Tag Taxonomy Palette Tokens**: Standardized category badge colors (Character=Green `#55c57a`, Copyright=Purple `#c084fc`, Artist=Red `#f87171`, General=Cyan `#38bdf8`, Meta=Orange `#fb923c`).
- **Anime Studio Bilingual Micro-Typography**: Optional sleek subtext headers (`LIBRARY // ライブラリ`, `EXTRACTOR // 抽出`, `STITCH // 結合`).
- *Pros:* Delivers an authentic, visually striking creative suite atmosphere; makes art assets pop against neutral backdrops.
- *Cons:* Requires theme token mapping across all legacy tab stylesheets.

**B — Custom QSS Only**
Rely solely on user-provided `user_theme.qss` stylesheets.
- *Pros:* Zero built-in preset maintenance.
- *Cons:* Poor out-of-the-box user experience; requires manual CSS coding for non-technical users.

**Recommendation:** Option A. Ship curated presets in Theme Studio with real-time switching and preview.

---

## 2.38 Universal Collapsible Context Inspector Panel

**Ergonomic pain point:**
Image metadata, EXIF tags, resolution chips, rating controls, and tool parameters are scattered across disparate tab layouts. Users frequently need to inspect image details or adjust tool options without obscuring the primary gallery or canvas workspace.

### Implementation Options

**A — Universal Collapsible Right Inspector Panel (`Ctrl+I`) [Recommended]**
Integrate a persistent, context-sensitive right sidebar hosted in a `QSplitter`:
- **Gallery / Database Context**: Displays active image preview thumbnail, full EXIF metadata table, color label picker, star rating, resolution chip, and Danbooru tag chips with click-to-search actions.
- **Tool Context (Stitch / Manga / Editor)**: Displays layer lists, parameter sliders, alignment adjustments, or cluster statistics.
- **System Context**: Displays database health, cache usage, and quick-maintenance buttons.
- **Detachable Floating Mode**: Can be popped out into an independent floating tool window for dual-monitor setups.
- *Pros:* Consistent ergonomic hub across all tools; collapses cleanly (`Ctrl+I`) to maximize viewport space.
- *Cons:* Requires mediator communication between active view selection and inspector provider.

**B — Pop-up Modal Windows Only**
Open independent modal dialogs whenever details or parameters need to be inspected.
- *Pros:* Easy to implement per tab.
- *Cons:* Clutters the desktop with floating windows and breaks keyboard flow.

**Recommendation:** Option A. Implement the universal context inspector in a persistent `QSplitter`.

---

## 2.39 Rich Telemetry Status Bar & System Monitoring

**Ergonomic pain point:**
The bottom `QStatusBar` currently displays plain text notifications. It does not communicate vital system metrics necessary for high-throughput image processing and ML inference, such as PostgreSQL connection latency, GPU/VRAM allocation, or background worker task progress.

### Implementation Options

**A — Interactive Telemetry Status Bar Widgets [Recommended]**
Transform the status bar with compact, theme-aware telemetry chips:
- **Database Engine Chip**: Live ping indicator (`🟢 PostgreSQL + pgvector (12ms)`).
- **GPU & VRAM Gauge**: Real-time VRAM allocation bar (`⚡ GPU: 6.4 / 24.0 GB`) for local PyTorch/CUDA and ComfyUI pipelines.
- **Active Task Progress Ring**: Dynamic spinner for active Celery/QThread background jobs (e.g. `🔄 Crawling: 42/100`).
- **Quick Theme / Layout Popover**: Clickable chip to toggle between Rail and Top Bar or swap active theme presets.
- *Pros:* Instant system observability without opening separate diagnostic panels.
- *Cons:* Light background timer required to sample GPU/process memory (bounded at 2-5s intervals).

**B — Static Text Bar with Separate Dashboard Window**
Keep the status bar simple and require opening the Settings or Cloud Compute window to view metrics.
- *Pros:* Minimal code footprint in `MainWindow`.
- *Cons:* Leaves the user unaware of background job completion, GPU OOM risks, or connection dropouts.

**Recommendation:** Option A.

---

## 2.40 Advanced Gallery Presentation Modes & Custom Thumbnail Overlays

**Ergonomic pain point:**
The standard uniform grid crops anime illustrations with varied aspect ratios (tall manga panels, widescreen wallpapers, square icons) and offers limited control over which metadata indicators appear directly on thumbnail cards.

### Implementation Options

**A — Masonry & Justified Layouts with Toggleable Card Overlays [Recommended]**
Upgrade the gallery engine ([AbstractGalleryBase](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/gui/src/classes/base/gallery_base.py)) to support:
- **Presentation Modes**:
  1. *Uniform Grid* (Fixed square/card bounding box).
  2. *Masonry Layout* (Variable height preserving natural illustration aspect ratios).
  3. *Compact List View* (Dense rows for bulk file management and data triage).
- **Configurable Overlay Badges** (Toggleable in Theme Studio / Gallery Settings):
  - Danbooru Content Rating (`G`, `S`, `Q`, `E`)
  - Resolution & Aspect Ratio chip (`3840×2160 • 16:9`)
  - File Format & Bit Depth pill (`PNG • 24-bit`)
  - Star Rating & Color Label badges
  - Tag Count Chip (`🏷️ 24`)
- *Pros:* Drastically enhances visual browsing of anime art; highly customizable card information density.
- *Cons:* Masonry positioning requires incremental geometry calculations during virtual scrolling.

**B — Fixed Grid Only with Static Tooltips**
Maintain the uniform grid and show metadata solely through mouse hover tooltips.
- *Pros:* Lower rendering complexity.
- *Cons:* Forces cropping of non-square artwork and requires mouse hover to inspect basic properties.

**Recommendation:** Option A.

---

## Effort × Impact Matrix {: #effort--impact-matrix }

*Effort* — **Low**: < 1 day · **Medium**: 1 day – 1 week · **High**: 1 – 2 weeks · **Very High**: 2+ weeks
*Impact* — **Low**: aesthetic polish · **Medium**: discoverable QoL · **High**: significant workflow improvement for most users · **Very High**: fundamental UX upgrade

| **Effort ↓ / Impact →** | Low | Medium | High | Very High |
|---|---|---|---|---|
| **Low (<1d)** | §2.4B right-click context menu · §2.10 toast notifications · §2.14 thumbnail metadata overlay · §2.24 hover animations · §2.25 shortcut discovery overlay · §2.26 inline rename | §2.2B Ctrl+scroll zoom [Quick Win] · §2.5A session path persistence · §2.9 settings extensions · §2.12 system tray · §2.17 log panel · §2.18 image rating + labels · §2.31A QSS user override · §2.35C fit & scaling modes · §2.37B bilingual micro-typography · §2.39A telemetry status bar | §2.3A+C keyboard nav shortcuts · §2.7A progress bar + cancel button [Quick Win] · §2.32A auto-save geometry [Quick Win] · §2.37A anime theme presets | — |
| **Medium (1d–1w)** | §2.19 contact sheet export | §2.2A slider control · §2.5B session restore dialog · §2.6B side-by-side before/after · §2.13 gallery filter+sort · §2.15 undo/redo deletions · §2.20A QSplitter persistence · §2.21 nav history · §2.27 multi-image compare · §2.28 global search · §2.29 configurable shortcuts · §2.30 accent colour + density · §2.34B dynamic palette extraction · §2.35B background playlist slideshow · §2.40B configurable thumbnail overlays | §2.4A multi-select with QItemSelectionModel · §2.8A dark/light theme toggle · §2.8B dynamic colour extraction · §2.12B+C tray preview + context ops · §2.22 tag chip compound search · §2.32B named layout profiles · §2.34A semantic color palette · §2.35A full-window background canvas · §2.36A dual navigation shell & module registry · §2.38A universal context inspector panel · §2.40A masonry gallery layout | §2.6A interactive zoom/pan preview · §2.16A command palette + registry |
| **High (1–2w)** | — | §2.30C density modes (compact/comfortable/spacious) · §2.31B in-app QSS editor · §2.34C advanced in-app QSS editor | §2.23 accessibility audit · §2.29B global keybinding conflict detection | §2.1A QListView virtual scroll (full refactor) |
| **Very High (2w+)** | — | §2.4E drag-and-drop reorder | §2.33A libmpv engine swap (spike, gated on JVM coexistence smoke test) | §4.12C named workspaces (superset of §2.29+§2.30+§2.32) |

---

## Anchor Index

| Section | Anchor |
|---------|--------|
| 2.1 Virtual Scroll Gallery | [#21-virtual-scroll-gallery](#21-virtual-scroll-gallery) |
| 2.2 Thumbnail Size Control | [#22-gallery-thumbnail-size-control](#22-gallery-thumbnail-size-control) |
| 2.3 Keyboard Navigation | [#23-keyboard-navigation](#23-keyboard-navigation) |
| 2.4 Bulk Selection | [#24-bulk-selection-and-operations](#24-bulk-selection-and-operations) |
| 2.5 Session Persistence | [#25-session-persistence](#25-session-persistence) |
| 2.6 Before/After Comparison | [#26-stitch-tab-ux--beforeafter-comparison](#26-stitch-tab-ux--beforeafter-comparison) |
| 2.7 Progress and Cancellation | [#27-progress-and-cancellation](#27-progress-and-cancellation) |
| 2.8 Theme Support | [#28-theme-support](#28-theme-support) |
| 2.9 Settings Window Extensions | [#29-settings-window-extensions](#29-settings-window-extensions) |
| 2.10 In-App Toast Notifications | [#210-in-app-toast-notification-system](#210-in-app-toast-notification-system) |
| 2.11 Image Preview Enhancements | [#211-image-preview-window-enhancements](#211-image-preview-window-enhancements) |
| 2.12 System Tray Integration | [#212-system-tray-integration](#212-system-tray-integration) |
| 2.13 Gallery Filtering and Sort | [#213-gallery-filtering-and-sort-controls](#213-gallery-filtering-and-sort-controls) |
| 2.14 Thumbnail Metadata Overlay | [#214-thumbnail-metadata-overlay](#214-thumbnail-metadata-overlay) |
| 2.15 Undo/Redo for Deletions | [#215-undoredo-for-destructive-operations](#215-undoredo-for-destructive-operations) |
| 2.16 Command Palette | [#216-command-palette--quick-launcher](#216-command-palette--quick-launcher) |
| 2.17 Global Log Panel | [#217-global-collapsible-log-panel](#217-global-collapsible-log-panel) |
| 2.18 Image Rating and Color Labels | [#218-image-rating-and-color-labels](#218-image-rating-and-color-labels) |
| 2.19 Gallery Export and Contact Sheet | [#219-gallery-export-and-contact-sheet](#219-gallery-export-and-contact-sheet) |
| 2.20 Sidebar Panels and QSplitter | [#220-resizable-sidebar-panels-and-qsplitter-persistence](#220-resizable-sidebar-panels-and-qsplitter-persistence) |
| 2.21 Directory Navigation History | [#221-directory-navigation-history-back--forward](#221-directory-navigation-history-back--forward) |
| 2.22 Tag Chip UI and Compound Search | [#222-tag-chip-ui-and-compound-tag-search](#222-tag-chip-ui-and-compound-tag-search) |
| 2.23 Accessibility and Tab Order | [#223-accessibility-and-keyboard-tab-order](#223-accessibility-and-keyboard-tab-order) |
| 2.24 Thumbnail Hover Animations | [#224-thumbnail-hover-animations](#224-thumbnail-hover-animations) |
| 2.25 Keyboard Shortcut Discovery | [#225-keyboard-shortcut-discovery-overlay](#225-keyboard-shortcut-discovery-overlay) |
| 2.26 Inline Rename | [#226-inline-rename](#226-inline-rename) |
| 2.27 Multi-Image Comparison View | [#227-multi-image-comparison-view](#227-multi-image-comparison-view) |
| 2.28 Global Cross-Tab Search | [#228-global-cross-tab-search](#228-global-cross-tab-search) |
| 2.29 Configurable Keyboard Shortcuts | [#229-configurable-keyboard-shortcuts](#229-configurable-keyboard-shortcuts) |
| 2.30 Accent Color and UI Density | [#230-accent-color-and-ui-density-customization](#230-accent-color-and-ui-density-customization) |
| 2.31 Custom QSS User Theme Override | [#231-custom-qss-user-theme-override](#231-custom-qss-user-theme-override) |
| 2.32 Window Layout and State Profiles | [#232-window-layout-and-state-profiles](#232-window-layout-and-state-profiles) |
| 2.33 Extractor Tab Playback Engine — libmpv | [#233-extractor-tab-playback-engine--libmpv-integration](#233-extractor-tab-playback-engine--libmpv-integration) |
| 2.34 Custom Theme Engine & Semantic Colors | [#234-custom-theme-engine--semantic-color-system](#234-custom-theme-engine--semantic-color-system) |
| 2.35 Full-Window Background Canvas & Glassmorphism | [#235-full-window-background-canvas--glassmorphic-layering](#235-full-window-background-canvas--glassmorphic-layering) |
| 2.36 Dual Navigation Shell & Modular Registry | [#236-dual-navigation-shell--modular-module-architecture](#236-dual-navigation-shell--modular-module-architecture) |
| 2.37 Anime Creative Suite Visual System & Presets | [#237-anime-creative-suite-visual-system--presets](#237-anime-creative-suite-visual-system--presets) |
| 2.38 Universal Collapsible Context Inspector | [#238-universal-collapsible-context-inspector-panel](#238-universal-collapsible-context-inspector-panel) |
| 2.39 Rich Telemetry Status Bar | [#239-rich-telemetry-status-bar--system-monitoring](#239-rich-telemetry-status-bar--system-monitoring) |
| 2.40 Advanced Gallery Presentation Modes | [#240-advanced-gallery-presentation-modes--custom-thumbnail-overlays](#240-advanced-gallery-presentation-modes--custom-thumbnail-overlays) |

---

## Document History

*Last updated: 2026-09-05 — §2.36 now records a post-rollout decision gate for the classic-shell fallback. Targets PySide6 (Qt 6.x) desktop application.*

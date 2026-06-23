# GUI/UX Roadmap — Desktop Interface Quality & Ergonomics

*Last updated: 2026-05-31. Targets PySide6 (Qt 6.x) desktop application.*

---

## Table of Contents

- [How to Use This Document](#how-to-use-this-document)
- [2.1 Virtual Scroll Gallery](#21-virtual-scroll-gallery)
- [2.2 Gallery Thumbnail Size Control](#22-gallery-thumbnail-size-control)
- [2.3 Keyboard Navigation](#23-keyboard-navigation-)
- [2.4 Bulk Selection and Operations](#24-bulk-selection-and-operations-)
- [2.5 Session Persistence](#25-session-persistence)
- [2.6 Stitch Tab UX — Before/After Comparison](#26-stitch-tab-ux--beforeafter-comparison)
- [2.7 Progress and Cancellation](#27-progress-and-cancellation-)
- [2.8 Theme Support](#28-theme-support)
- [2.9 Settings Window Extensions](#29-settings-window-extensions)
- [2.10 In-App Toast Notification System](#210-in-app-toast-notification-system-)
- [2.11 Image Preview Window Enhancements](#211-image-preview-window-enhancements-)
- [2.12 System Tray Integration](#212-system-tray-integration-)
- [2.13 Gallery Filtering and Sort Controls](#213-gallery-filtering-and-sort-controls-)
- [2.14 Thumbnail Metadata Overlay](#214-thumbnail-metadata-overlay-)
- [2.15 Undo/Redo for Destructive Operations](#215-undoredo-for-destructive-operations-)
- [2.16 Command Palette / Quick Launcher](#216-command-palette--quick-launcher-)
- [2.17 Global Collapsible Log Panel](#217-global-collapsible-log-panel-)
- [2.18 Image Rating and Color Labels](#218-image-rating-and-color-labels-)
- [2.19 Gallery Export and Contact Sheet](#219-gallery-export-and-contact-sheet-)
- [2.20 Resizable Sidebar Panels and QSplitter Persistence](#220-resizable-sidebar-panels-and-qsplitter-persistence-)
- [2.21 Directory Navigation History](#221-directory-navigation-history-back--forward-)
- [2.22 Tag Chip UI and Compound Tag Search](#222-tag-chip-ui-and-compound-tag-search)
- [2.23 Accessibility and Keyboard Tab Order](#223-accessibility-and-keyboard-tab-order-)
- [2.24 Thumbnail Hover Animations](#224-thumbnail-hover-animations-)
- [2.25 Keyboard Shortcut Discovery Overlay](#225-keyboard-shortcut-discovery-overlay-)
- [2.26 Inline Rename](#226-inline-rename-)
- [2.27 Multi-Image Comparison View](#227-multi-image-comparison-view)
- [2.28 Global Cross-Tab Search](#228-global-cross-tab-search)
- [2.29 Configurable Keyboard Shortcuts](#229-configurable-keyboard-shortcuts-)
- [2.30 Accent Color and UI Density Customization](#230-accent-color-and-ui-density-customization-)
- [2.31 Custom QSS User Theme Override](#231-custom-qss-user-theme-override-)
- [2.32 Window Layout and State Profiles](#232-window-layout-and-state-profiles-)
- [Effort × Impact Matrix](#effort--impact-matrix)
- [Anchor Index](#anchor-index)

---

## Implementation Timeline

> **Legend** — *Node fill:* ✅ complete (green) · 🔄 in-progress/partial (amber) · ⬜ planned (light) — *Node border:* new feature (blue) · augmentation (violet) — *Edges:* `==>` critical prerequisite · `-->` sequential dependency · `-.->` alternative approach · `---` complements

```mermaid
flowchart LR
    classDef c_feat fill:#16a34a,stroke:#2563eb,stroke-width:3px,color:#fff
    classDef c_aug  fill:#16a34a,stroke:#7c3aed,stroke-width:3px,color:#fff
    classDef p_feat fill:#d97706,stroke:#2563eb,stroke-width:3px,color:#fff
    classDef p_aug  fill:#d97706,stroke:#7c3aed,stroke-width:3px,color:#fff
    classDef t_feat fill:#e2e8f0,stroke:#2563eb,stroke-width:2px,color:#1e293b
    classDef t_aug  fill:#e2e8f0,stroke:#7c3aed,stroke-width:2px,color:#1e293b

    subgraph GC["🖼️ Gallery Core"]
        direction TB
        S21["§2.1 Virtual Scroll Gallery"]:::t_feat
        S22["§2.2 Thumbnail Size Control"]:::t_aug
        S23["§2.3 Keyboard Navigation ✅p"]:::p_aug
        S24["§2.4 Bulk Selection ✅p"]:::p_aug
        S213["§2.13 Filter & Sort Controls ✅p"]:::p_aug
        S214["§2.14 Metadata Overlay ✅p"]:::p_aug
        S21 ==> S22
        S21 --> S213
        S21 --> S214
        S23 --- S24
    end

    subgraph WF["⚡ Workflow & Productivity"]
        direction TB
        S25["§2.5 Session Persistence"]:::t_aug
        S27["§2.7 Progress & Cancel ✅p"]:::p_aug
        S215["§2.15 Undo/Redo ✅p"]:::p_aug
        S216["§2.16 Command Palette ✅p"]:::p_feat
        S221["§2.21 Dir Nav History ✅p"]:::p_aug
        S222["§2.22 Tag Chip UI"]:::t_feat
        S227["§2.27 Multi-Image Compare"]:::t_feat
        S228["§2.28 Global Search"]:::t_feat
        S222 --> S228
        S216 --> S228
    end

    subgraph SYS["🔔 Notifications & System"]
        direction TB
        S28["§2.8 Theme Support"]:::t_feat
        S29["§2.9 Settings Window"]:::t_aug
        S210["§2.10 Toast Notifications ✅p"]:::p_feat
        S212["§2.12 System Tray ✅p"]:::p_feat
        S217["§2.17 Log Panel ✅p"]:::p_feat
        S229["§2.29 Configurable Shortcuts ✅"]:::c_aug
        S212 --- S217
    end

    subgraph VIS["🎨 Visual Customisation"]
        direction TB
        S218["§2.18 Image Rating ✅p"]:::p_feat
        S225["§2.25 Shortcut Overlay ✅p"]:::p_feat
        S230["§2.30 Accent Color ✅"]:::c_aug
        S231["§2.31 Custom QSS Theme ✅"]:::c_aug
        S232["§2.32 Layout Profiles ✅p"]:::p_aug
        S230 --- S231
    end

    %% Cross-group dependencies
    S28 --> S230
    S28 --> S231
    S216 --- S229
    S25 --- S232
```

Each node's **fill colour** shows implementation status: green = complete, amber = partially shipped (marked ✅p), light = not yet started. The **border colour** shows element type: blue = new feature, violet = augmentation of existing functionality. **Edge style** encodes relationship: `==>` critical prerequisite (must land first), `-->` sequential dependency, `---` complements (parallel work).

---

## How to Use This Document

Each section describes an ergonomic pain point, all viable implementation options with trade-offs, and a recommendation. Items tagged **[Quick Win]** take under a day. Items tagged **[Research]** require prototyping.

**Critical constraint:** Never use `QWebEngineView` (QtWebEngine/Chromium). Opening URLs must use `QDesktopServices.openUrl()`. All heavy operations must run off the main thread (QThread/QRunnable). See MEMORY.md for the JVM + native dialog SIGSEGV context.

---

## 2.1 Virtual Scroll Gallery

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

## 2.2 Gallery Thumbnail Size Control

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
Four fixed sizes (64/128/192/256px) as toggle buttons in the toolbar. Less flexible but harder to mis-click to an unusable size.
- Pros: Discoverable. Safe range.
- Cons: Limited flexibility.

**D — Per-tab persistent size**
Extend A/B so each tab remembers its own thumbnail size independently (e.g., convert tab prefers larger, database tab prefers smaller).
- Pros: Workflow-aware sizing.
- Cons: More `QSettings` keys to manage.

**Recommendation:** B is the most intuitive (no UI chrome). Combine with A for explicit control. D as a follow-on once A is stable.

---

## 2.3 Keyboard Navigation ✅ Partial (2026-06-10 — §A arrow-key navigation in both gallery base classes)

**Pain point:** Common operations require mouse interaction. Power users expect keyboard shortcuts for gallery navigation, preview, and operations.

### Options

**A — Arrow key gallery navigation**
Left/right/up/down select the adjacent thumbnail. Enter opens the full-size preview. Delete triggers the deletion workflow.
- Pros: Baseline expectation for any image browser. Minimal code (install `QShortcut` on the gallery widget).
- Cons: Requires focus management — shortcuts only fire when gallery has focus.

**B — Global hotkey table in settings**
Let users configure custom bindings for any tab action. Store in `~/.config/image-toolkit/keybindings.json`. Use Qt's `QShortcut` with `Qt.ApplicationShortcut` context.
- Pros: Power-user friendly. Accommodates diverse workflows.
- Cons: Significant UI investment for the settings panel. Conflict detection between shortcuts.

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

## 2.4 Bulk Selection and Operations ✅ Partial (2026-06-10 — §B Shift+click range + §C right-click context menu)

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

## 2.5 Session Persistence

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

**Recommendation:** A immediately. C as a follow-on. B is overkill for now.

---

## 2.6 Stitch Tab UX — Before/After Comparison

**Pain point:** StitchTab shows the output panorama but provides no comparison with the simple stitch fallback. Users can't judge whether ASP actually improved the result without manually opening both outputs.

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

## 2.7 Progress and Cancellation ✅ Partial (2026-06-10 — §A stage progress + §B cancellable workers)

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

---

## 2.8 Theme Support

**Pain point:** App uses the system Qt palette, producing inconsistent look across platforms. Dark-mode OS settings not reliably respected.

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

**A — Wire thumbnail size / page size to gallery base classes at startup**
`main_window.py` should read `preferences["thumbnail_size"]` and `preferences["page_size"]` after vault load and set `tab.thumbnail_size` / `tab.found_page_size` / `tab.page_size` on each gallery tab instance before displaying them. One loop in `MainWindow.__init__` after all tabs are constructed.

**B — Wire LRU cache sizes to gallery base classes at startup**
Same loop as A: read `found_cache_maxsize`, `selected_cache_maxsize`, `initial_cache_maxsize` and call `tab._found_pixmap_cache = LRUImageCache(maxsize=...)` etc. The `LRUImageCache` class supports `maxsize` at construction time.

**C — Wire startup category to MainWindow**
`MainWindow.__init__` already calls `self.on_command_changed(self.command_combo.currentText())`. Before that, set `self.command_combo.setCurrentText(prefs.get("startup_category", "System Tools"))` after reading preferences from vault.

**D — Wire confirm_deletions to deletion workflows ✅ (2026-06-10)**
`_confirm_deletions_enabled()` helper reads `preferences["confirm_deletions"]` from vault in both gallery base classes. `_trash_path` in `AbstractClassTwoGalleries` gates on this preference. `ConvertTab`, `DeleteTab`, and `WallpaperTab` standalone deletion paths still use their own dialogs (partial coverage).

**E — Wire slideshow defaults to WallpaperTab**
After `WallpaperTab` construction in `MainWindow.__init__`, set:
```python
self.wallpaper_tab.interval_min_spinbox.setValue(prefs.get("slideshow_interval_min", 5))
self.wallpaper_tab.interval_sec_spinbox.setValue(prefs.get("slideshow_interval_sec", 0))
self.wallpaper_tab.playback_order_combo.setCurrentText(prefs.get("slideshow_order", "Sequential"))
```

**F — Wire logging settings**
On app startup (before `MainWindow` init), read `preferences["log_level"]` and `preferences["file_logging_enabled"]` and configure the `logging` module: set the root logger level and add/remove the `RotatingFileHandler`. This should go in `main.py` after vault load.

**G — Wire restore_last_dir and recent_dirs_count**
Requires implementing the session persistence feature (§2.5). The vault settings are already stored; they just need to be consumed.

---

## 2.10 In-App Toast Notification System ✅ Partial (2026-06-10 — §C shipped)

**Pain point:** Every operation result — file saved, cache cleared, duplicate found, export finished — triggers a blocking `QMessageBox` that interrupts the user's workflow. For background operations (slideshow daemon ticks, RLHF auto-score, WebDriver status) there is no non-blocking feedback path at all.

### Options

**A — Custom overlay toast widget [Quick Win]**
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

## 2.11 Image Preview Window Enhancements ✅ Partial (2026-06-10 — §A fullscreen, §B fit modes, §D rotation shipped)

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

## 2.12 System Tray Integration ✅ Partial (2026-06-10 — §A+B+C shipped)

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

## 2.13 Gallery Filtering and Sort Controls ✅ Partial (2026-06-10 — §A + §E)

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

## 2.14 Thumbnail Metadata Overlay ✅ Partial (2026-06-10 — §A shipped)

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

## 2.15 Undo/Redo for Destructive Operations ✅ Partial (2026-06-10 — §A shipped)

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

**Recommendation:** A immediately (send2trash is the highest-safety, lowest-effort change). B for in-app undo on rename/move operations. D as a long-term QoL feature.

---

## 2.16 Command Palette / Quick Launcher ✅ Partial (2026-06-10 — §C Ctrl+T tab search shipped)

**Pain point:** Navigating between 20+ tabs requires using the "Select Category" combo and then clicking the tab. There is no way to trigger operations (scan, convert, stitch) or jump to a specific tab by typing. Power users working across multiple categories are slowed by mouse-heavy navigation.

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

## 2.17 Global Collapsible Log Panel ✅ Partial (2026-06-10 — §D shipped: LogWindow upgraded)

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

## 2.18 Image Rating and Color Labels ✅ Partial (2026-06-10 — §B+C shipped)

**Pain point:** The database has a tag system but no first-class rating or label mechanism. Industry-standard image management apps (Lightroom, digiKam, Eagle) use star ratings (1–5) and color labels (red/yellow/green/blue/purple/grey) as the primary curation workflow. These cannot be replicated using free-text tags.

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

## 2.19 Gallery Export and Contact Sheet ✅ Partial (2026-06-10 — §A+C shipped)

**Pain point:** There is no way to export the current gallery selection as a list of paths or as a visual contact sheet (proof sheet). Workarounds require external tools. The `ConvertTab` handles format conversion but not gallery-selection-based export.

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

## 2.20 Resizable Sidebar Panels and QSplitter Persistence ✅ Partial (2026-06-10 — §A shipped)

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

## 2.21 Directory Navigation History (Back / Forward) ✅ Partial (2026-06-10 — §A+D shipped for FormatTab)

**Pain point:** Every gallery tab's "Browse" button opens a `QFileDialog` and loads the new directory, discarding the previous path. There is no back/forward navigation. Users who accidentally navigate away from a directory must re-browse manually.

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

## 2.22 Tag Chip UI and Compound Tag Search

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

## 2.23 Accessibility and Keyboard Tab Order ✅ Partial (2026-06-10 — §A accessible names on pagination widgets)

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

## 2.24 Thumbnail Hover Animations ✅ Partial (2026-06-10 — §A shipped)

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

## 2.25 Keyboard Shortcut Discovery Overlay ✅ Partial (2026-06-10 — §A Ctrl+/ table shipped)

**Pain point:** The app has various keyboard shortcuts scattered across tabs (`Ctrl+C` in preview, `Del` for delete, `Enter` for preview open) but there is no in-app reference for them. Users discover shortcuts accidentally. No `F1` help or `?` overlay exists.

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

## 2.26 Inline Rename ✅ Partial (2026-06-10 — §B shipped: context-menu rename via F2)

**Pain point:** Renaming a file requires the user to leave the app, open a file manager, rename, and return. No inline rename (F2) exists in any gallery tab, despite the `DraggableLabel` and `ClickableLabel` components being potential hosts for in-place `QLineEdit` editing.

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

## 2.27 Multi-Image Comparison View

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

## 2.28 Global Cross-Tab Search

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

## 2.29 Configurable Keyboard Shortcuts ✅ (2026-06-10)

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

---

## 2.30 Accent Color and UI Density Customization ✅

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

## 2.31 Custom QSS User Theme Override ✅ (2026-06-10)

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

## 2.32 Window Layout and State Profiles ✅ Partial (2026-06-10 — geometry only)

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

## Effort × Impact Matrix

*Effort* — **Low**: < 1 day · **Medium**: 1 day – 1 week · **High**: 1 – 2 weeks · **Very High**: 2+ weeks
*Impact* — **Low**: aesthetic polish · **Medium**: discoverable QoL · **High**: significant workflow improvement for most users · **Very High**: fundamental UX upgrade

| **Effort ↓ / Impact →** | Low | Medium | High | Very High |
|---|---|---|---|---|
| **Low (<1d)** | §2.4B right-click context menu · §2.10 toast notifications · §2.14 thumbnail metadata overlay · §2.24 hover animations · §2.25 shortcut discovery overlay · §2.26 inline rename | §2.2B Ctrl+scroll zoom [Quick Win] · §2.5A session path persistence · §2.9 settings extensions · §2.12 system tray · §2.17 log panel · §2.18 image rating + labels · §2.31A QSS user override | §2.3A+C keyboard nav shortcuts · §2.7A progress bar + cancel button [Quick Win] · §2.32A auto-save geometry [Quick Win] | — |
| **Medium (1d–1w)** | §2.19 contact sheet export | §2.2A slider control · §2.5B session restore dialog · §2.6B side-by-side before/after · §2.13 gallery filter+sort · §2.15 undo/redo deletions · §2.20A QSplitter persistence · §2.21 nav history · §2.27 multi-image compare · §2.28 global search · §2.29 configurable shortcuts · §2.30 accent colour + density | §2.4A multi-select with QItemSelectionModel · §2.8A dark/light theme toggle · §2.8B dynamic colour extraction · §2.12B+C tray preview + context ops · §2.22 tag chip compound search · §2.32B named layout profiles | §2.6A interactive zoom/pan preview · §2.16A command palette + registry |
| **High (1–2w)** | — | §2.30C density modes (compact/comfortable/spacious) · §2.31B in-app QSS editor | §2.23 accessibility audit · §2.29B global keybinding conflict detection | §2.1A QListView virtual scroll (full refactor) |
| **Very High (2w+)** | — | §2.4E drag-and-drop reorder | — | §4.12C named workspaces (superset of §2.29+§2.30+§2.32) |

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

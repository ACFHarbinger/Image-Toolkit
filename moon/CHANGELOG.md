# Image Toolkit — Changelog

*Completed items archived from the Master Roadmap. Ordered from most recent phase to earliest.*

---

## GUI/UX Phase 1 — Quick Wins (Completed 2026-05-31)

| Item | Summary |
|------|---------|
| G1.9 Session persistence | `_save_last_dir` / `_load_last_dir` helpers added to both `AbstractClassTwoGalleries` and `AbstractClassSingleGallery`. Each tab class stores its last browsed directory in `QSettings("ImageToolkit","ImageToolkit")` under `session/<ClassName>/last_dir`. The saved path is restored on next launch, eliminating the need to re-browse to the previous directory after an app restart. |
| G1.10 OS dark mode follow | `MainWindow.__init__` now reads `QGuiApplication.styleHints().colorScheme()` when the vault stores no explicit theme preference. Falls back to `"dark"` when the OS reports `Unknown`. Connects `colorSchemeChanged` signal to auto-switch themes when the user toggles dark/light mode in the OS while the app is running (only takes effect when no vault override is set). |
| G1.11 Ctrl+scroll thumbnail zoom | `MarqueeScrollArea` intercepts wheel events with `Qt.ControlModifier` and emits a `ctrl_wheel(int)` signal (positive = scroll up = zoom in, negative = scroll down = zoom out). Both gallery base classes connect this signal lazily on the first layout-change tick, keeping concrete tab code untouched. Each Ctrl+scroll step changes `thumbnail_size` by ±16 px (clamped to 64–512 px) and reloads the current gallery page at the new size. |

## MAL Auto-Fill — Entity Association Bug Fix (2026-05-31)

| Item | Summary |
|------|---------|
| Root cause | Jikan returns HTTP 500 for `/anime/{id}/characters` on adult/hentai content. The original code called `resp.raise_for_status()` inside `_jikan_get`, which threw `requests.HTTPError`. This was caught by the outer `except Exception: pass`, silently swallowing all character data. Akane Nanao was not matched because the characters list was empty, not because the name matching was wrong. |
| `_jikan_get` non-raising | `_jikan_get` now checks `resp.ok` and returns `None` (not raises) for any 4xx/5xx. Callers treat `None` as "endpoint unavailable" rather than a fatal error. |
| `characters_available` flag | `fetch_mal_anime_data` now includes `"characters_available": bool`. If the endpoint returned 500, the flag is `False`. `_on_mal_finished` calls `_auto_associate_entities` which shows an `information` dialog explaining that character/voice-actor data is restricted for 18+ content and inviting the user to add them manually via Select Entities. |
| Reversed-word fallback | `_auto_associate_entities._try_add` now tries three name forms: (1) as-is, (2) words reversed (`"Nanao Akane"` ↔ `"Akane Nanao"`), (3) comma-swap (`"Last, First"` → `"First Last"`). All four test cases now match: `"T-Rex"`, `"Akane Nanao"`, `"Nanao Akane"`, `"Nanao, Akane"`. |

## MAL Auto-Fill — Entity Auto-Association (2026-05-31)

| Item | Summary |
|------|---------|
| Jikan multi-endpoint fetch | `fetch_mal_anime_data` now makes two additional rate-limited requests (0.4 s gap each): `/anime/{id}/characters` for character names + Japanese voice-actor names, and `/anime/{id}/staff` for director/producer/etc. names. Studios and producers are read from the main endpoint response. All names are normalised from Jikan's `"Last, First"` format to `"First Last"` via `_normalize_name`. |
| Entity auto-association | `_on_mal_finished` now calls `_auto_associate_entities(data)` which: builds a case-insensitive name → entity-id index from `entities.json`; tries both the normalised and the `"Last, First"` form of each incoming name; adds every matched entity ID to `assoc_entities_ids` without duplicates; refreshes the Associated Entities display. The five entity lists checked are: studios, producers, characters, voice_actors, staff. Non-matching names are silently skipped. |

## GUI/UX Phase 2 — Core QoS (Continued 2026-05-31)

| Item | Summary |
|------|---------|
| G2.8 Arrow-key gallery navigation | `AbstractClassTwoGalleries.keyPressEvent` extended: Left/Right/Up/Down move `_focused_found_idx` (column-aware via `_current_found_cols`); Enter/Space emits `path_double_clicked` on the focused label, delegating to whatever preview handler the concrete tab has wired. Focus is scrolled into view via `ensureWidgetVisible`. |
| G2.10 Recent-dirs MRU helpers | `_add_recent_dir(path)` / `_get_recent_dirs()` added to both gallery base classes (backed by `QSettings`). Every browsed directory can be pushed to a per-class, capped-at-10 MRU list. Concrete tabs can now build a recent-dirs dropdown by calling `_get_recent_dirs()` and `_add_recent_dir()` on each browse. |
| G2.20A QSplitter persistence | `_persist_splitter(splitter, key)` module-level utility added to `listings_tab.py`. Restores state from `QSettings` on creation; saves on every `splitterMoved`. Applied to all three splitters in `listings_tab`: directory-import dialog, `ContentListingsSubTab`, and `EntityListingsSubTab`. |
| G2.26B F2 Rename | `_rename_focused_file()` added to `AbstractClassTwoGalleries` (F2 renames whichever file is focused by the arrow-key cursor `_focused_found_idx`). `_rename_selected_file()` added to `AbstractClassSingleGallery` (F2 renames the most-recently-selected item). Both: open `QInputDialog.getText` pre-filled with the stem; sanitise illegal filesystem characters; guard against name conflicts; call `os.rename`; patch `found_files`, `master_found_files`, `selected_files`, and the label/card widget map so the UI reflects the new path without a reload. |
| G2.19A Export selection as paths | `_export_selection_as_paths()` added to both `AbstractClassTwoGalleries` and `AbstractClassSingleGallery`. Triggered by Ctrl+E. Exports `selected_files` if any are selected, otherwise exports all loaded files (`found_files` / `gallery_image_paths`). Saves to user-chosen `.txt` / `.csv` via `QFileDialog` (native dialog disabled to avoid JVM RTTI conflict on Linux). |
| G2.24A Thumbnail hover border | `DraggableLabel` and `ClickableLabel` now paint a 2-px cyan (`#00bcd4`) border overlay via `paintEvent` when the cursor is over them (`WA_Hover` + `enterEvent`/`leaveEvent` toggle). Non-destructive: drawn on top of whatever the current stylesheet state is, so selected/found/loading styles are unaffected. |
| G2.16A–C+E Settings wiring | `_apply_startup_preferences()` extended: §A+C as before (thumbnail/page size, startup category); §B replaces each gallery tab's `_found_pixmap_cache`, `_selected_pixmap_cache`, `_initial_pixmap_cache` with new `LRUImageCache` instances sized from vault prefs; §E sets `WallpaperTab` slideshow spinboxes and order combo from vault prefs. Items D (confirm_deletions), F (logging), G (restore_last_dir) remain. |
| G2.17D LogWindow upgrade | `LogWindow` rewritten: `QPlainTextEdit` (monospace, readable font), five colour-coded levels (ERROR=red, WARNING=orange, INFO=grey-white, DEBUG=grey, SUCCESS=green), ISO timestamp prefix on each line, Copy All / Save to File / Clear buttons, Follow toggle for auto-scroll. |
| G2.21A Directory nav history | `_push_dir_history`, `_dir_go_back`, `_dir_go_forward` added to both gallery base classes using a `deque(maxlen=20)`. Concrete tabs call `_push_dir_history(current_path)` before loading a new directory; `Alt+Left` / `Alt+Right` (or toolbar Back/Forward buttons, once wired in concrete tabs) can navigate the stack. |

### Image Preview Window — Quick Wins (2026-05-31)

| Item | Summary |
|------|---------|
| G2.11A Fullscreen toggle | `F` / `F11` toggles `showFullScreen()` ↔ `showMaximized()`. Context menu label dynamically reads "Fullscreen (F11)" or "Exit Fullscreen (F11)" depending on current state. |
| G2.11B Zoom modes | `W` = fit-to-width (zoom = viewport_width / image_width); `H` = fit-to-height; `1` = 100% actual pixels. All three are also accessible from the right-click context menu. |
| G2.11D Rotation | `R` rotates 90° clockwise; `L` rotates 90° counter-clockwise. Rotation state (`_rotation_degrees`) is maintained per preview session; applied via `QTransform().rotate(...)` before scaling. Context menu entries for both directions. GIFs are not rotated (QMovie doesn't support `QTransform` scaling). |

### Listings Tab — Summary/Review Split (2026-05-31)

| Item | Summary |
|------|---------|
| Summary writable | Summary field is now fully editable — the placeholder text clarifies that it can be auto-filled from MAL or typed manually. The previously applied `setReadOnly(True)` and grey styling are removed; the field uses the standard theme style like all other inputs. |
| Summary + Review fields | `_DetailPanel` now has two text fields: **Summary** (read-only, grey background, 75 px tall — auto-filled by MAL with the official synopsis) and **Review / Notes** (editable, user's personal review). Old entries that stored everything in `"review"` still load correctly; new saves write both `"summary"` and `"review"` keys. The `_on_mal_finished` slot now targets `f_summary` instead of `f_review`, so MAL auto-fill never overwrites a personal review. |

### Listings Tab — Rating Split & MAL Enhancements (2026-05-31)

| Item | Summary |
|------|---------|
| QDoubleSpinBox style fix | Added `QDoubleSpinBox` to the input-field selector in both `dark.qss` and `light.qss`. Previously the Community Rating field inherited the OS native spinbox chrome because the global stylesheet didn't cover it. |
| Dual ratings | `_DetailPanel` in `ContentListingsSubTab` now has two separate rating fields: **My Rating** (`QSpinBox`, 0–10, integer stars) and **Community Rating (MAL)** (`QDoubleSpinBox`, 0.00–10.00). Old single-`rating` keys in stored JSON are transparently migrated to `personal_rating` on first load. Card thumbnails display personal rating as gold stars and MAL community score as a purple badge. |
| MAL web link auto-fill | `_on_mal_finished` now populates `f_web_link` with the anime's MAL page URL from `anime["url"]` in the Jikan response, but only when the field is currently empty (avoids overwriting a manually entered link). |
| MAL score as float | Jikan client returns `score` as a raw `float` (e.g., `7.85`) instead of a rounded `int`, matching MAL's own precision. |

---

## Phase 3 — ASP Advanced Pipeline (Completed 2026-05-30)

| Item | Summary |
|------|---------|
| P3.1 EfficientLoFTR drop-in | Replaced original LoFTR with EfficientLoFTR for faster keypoint matching with equivalent accuracy. |
| P3.2 JamMa O(N) Mamba matcher | Mamba-based O(N) sequence matching integrated (pending CUDA rebuild for latest toolkit). |
| P3.3 ToonCrafter ghost fill | `anim/anim_fill.py` — ToonCrafter-based synthetic frame generation for deghosting in high-overlap zones. |
| P3.4 SRStitcher diffusion fusion | `anim/sr_stitcher.py` — diffusion-based seam and border inpainting for final-quality outputs. |
| P3.5 SEA-RAFT fine-tune pipeline | Fine-tuning pipeline for SEA-RAFT optical flow on domain-specific scroll sequences. |
| P3.6 EfficientLoFTR fine-tune pipeline | Fine-tuning pipeline for EfficientLoFTR on scroll-frame keypoint pairs. |

---

## Phase 2 — ASP Intermediate Pipeline (Completed 2026-05)

| Item | Summary |
|------|---------|
| P2.1 SEA-RAFT optical flow | SEA-RAFT flow for robust large-displacement inter-frame motion estimation. |
| P2.2 Real-ESRGAN super-resolution | `anim/super_res.py` — Real-ESRGAN 4× upscale post-processing mode. |
| P2.3 ALIKED + LightGlue matching | ALIKED feature detector paired with LightGlue for accurate keypoint matching. |
| P2.4 BiRefNet seam routing | BiRefNet foreground mask integrated into seam DP cost (`sem_cost`) to route seams away from character regions. |
| P2.5 Soft-seam diffusion blending | Diffusion-based soft seam blending for smooth panorama transitions. |
| P2.6 Per-segment photometric correction | Per-foreground-segment gain correction using BiRefNet segmentation masks. |
| P2.8 RoMa v2 matcher | RoMa v2 dense matcher added as a high-accuracy fallback tier. |
| P2.9 Segment-guided matching | Matching restricted to background segments to reduce noise from dynamic foreground content. |

---

## Phase 1 — ASP Foundation Pipeline (Completed 2026-04)

| Item | Summary |
|------|---------|
| P1.1 Animation phase clustering | Temporal clustering to separate distinct animation phases (scene transitions vs. scroll). |
| P1.2 Variable-step renderer | Renderer adapted to handle non-uniform inter-frame scroll steps. |
| P1.3 Confidence-weighted median | Temporal median weighted by per-frame quality confidence scores. |
| P1.4 EfficientLoFTR initial integration | First integration of EfficientLoFTR as the primary feature matcher. |
| P1.5 Grid sampling | Uniform grid keypoint sampling as a fallback when detector-based sampling is sparse. |
| P1.6 StabStitch BA regularisation | Bundle adjustment regularisation borrowed from StabStitch for video stabilisation priors. |
| P1.7 Auto-MFSR | Automatic multi-frame super-resolution triggered on low-resolution inputs. |
| P1.8 Auto-inpaint | Automatic inpainting triggered on detected border artefacts. |
| P1.9 Bidirectional midplane | Bidirectional midplane estimation for symmetric canvas placement. |

---

## RAM Reduction Campaign (Tier 1–5, Completed)

| Item | Summary |
|------|---------|
| Gallery LRU caches | `AbstractClassTwoGalleries` and `AbstractClassSingleGallery` — all three caches converted to bounded `LRUImageCache` (OrderedDict-backed, QImage storage). WallpaperTab, ImageExtractorTab, ReverseSearchTab fixed. |
| QPixmap threading violation | `ImageLoaderWorker` now emits `QImage` from worker thread instead of `QPixmap` (QPixmap is main-thread only). |
| DuplicateScanWorker chunked compare | SIFT/SSIM use `_chunked_compare(chunk_size=500)` to cap live descriptors in memory. |
| `_loaded_results_buffer` → QImage | `scan_metadata_tab.py` buffer stores `QImage` instead of `QPixmap`. |
| Tag checkboxes → QListWidget | Both `scan_metadata_tab.py` and `search_tab.py` use virtual `QListWidget` instead of individual `QCheckBox` widgets. |
| `source_path_to_widget` cleanup | Map entries popped on page changes in `image_extractor_tab.py` to prevent unbounded growth. |
| ML model `unload()` on finish | Siamese, GAN, SD3 wrappers call `unload()` after inference completes to free GPU memory. |
| Weak-reference lambda captures | `abstract_class_two_galleries.py` signal closures use `weakref.ref` to prevent circular reference memory leaks. |
| PostgreSQL server-side cursors | `bulk_export_cursor` pattern for unbounded queries; avoids loading full result sets into Python memory. |
| N+1 tag query elimination | `get_tags_for_images_bulk` batch fetch replaces per-image tag queries. |

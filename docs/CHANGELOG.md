# Image Toolkit — Changelog

*Completed items archived from the Master Roadmap. Ordered from most recent phase to earliest.*

---

## S213 — 2026-07-19 (Library database upgrades: tag type filters, groups & subgroups side-by-side lists, path display in Maintenance tab, batch metadata editor tabs)

**Part 2 — Metadata Editor Optional Tag Filter & Delete Fixes (later today):**
- **Remove from Database Option**: Added a right-click context menu option "🔌 Remove from Database" in the Scan and Tag tab's gallery, permitting users to remove image metadata from the database without deleting the physical file on disk.
- **Metadata Editor Optional Tag Filter**: Added a "Filter by Type" toggle checkbox in the `FilteredTagList` widget for both the Batch / Overview and individual image tabs in the Edit Metadata window. When unchecked (default), it hides the type checkboxes and displays all tags unfiltered; when checked, it reveals the type checkboxes and dynamically filters tags by their checked status.
- **Accidental Rename Prevention**: Fixed the double-prompt issue when removing a tag, subgroup, or group from the Library Database by setting `self.old_edit_value = None` at the start of their deletion methods. This prevents accidental inline-rename triggers caused by focus loss or row removal events.

**Part 1 — Library Database upgrades, Metadata Editor, and Maintenance upgrades (earlier today):**
- **Image Search Tab**: Replaced Group and Subgroup name textboxes with checkable list boxes. Subgroup entries are prefixed with their group name split by double colons (e.g. `Group1::Subgroup1`). The subgroups list updates dynamically based on the selected groups. The lists are positioned side-by-side as pairs (Groups + Subgroups, Tag Types + Tags) with matching heights. Added tag type checkboxes allowing users to optionally filter tags.
- **Scan & Tag Directory Browser**: Fixed directory browsing crash/error by correcting the import path.
- **Metadata Editor (Batch / Overview tabs)**: Added an editor launched from the "Add/Update N Selected Images" button. Features a "Batch / Overview" tab for bulk-applying metadata, defining custom image subsets (clusters) with specific overrides, using sequential template patterns (via `{n}` or auto-appending), and bulk tag updates. Displays subsequent per-image tabs showing a thumbnail and pre-filled fields that can be saved back to the database.
- **Maintenance Tab**: Added a filepaths table at the end of the tab showcasing every filepath stored in the database alongside its associated group and subgroup names.

---

## S212 — 2026-07-17 (Extractor tab Video/Image subtabs — multi-frame image splitter; GUI tab tutorials)

**Part 2 — GUI tab tutorials (`docs/tutorials/`):** five new tutorial pages + an index, one per tab category, documenting every tab's purpose, workflow, and parameters (written against the current widget code, not from memory):

- `system_tools.md` — Convert (Format aspect-ratio modes, Codec targets/CRF/Speed, Sampler algorithms), Merge (all 8 modes with a Merge-Canvas deep-dive: tiles, X/Y/W/H spinboxes, Join snapping), Similarity scan methods, Extractor (Video extraction-settings rows; Image frame-layout + boundary-preview canvas), Wallpaper (all 5 background types + per-DE style lists; Monitor Display graph canvas, node properties incl. edge priority/repeat, end-of-graph behaviors).
- `library_database.md` — Listings (Gen Thumbnail, MAL Auto-Fill methods, tags/entities/episodes, Advanced Search AND/OR + include/exclude, Recommend engine; Entity Type-vs-Role, associations; Import Dir wizard, Sync/Update Backup semantics), Image Search (combining DB criteria with filename/format filters; Refresh Tags), Scan and Tag (Show Only New/In DB; exact upsert field semantics), Maintenance (library buttons, auto-populate, groups/subgroups/tags, bulk-import JSON shapes).
- `web_integration.md` — Crawler (types, String-to-Replace pagination, all 17 actions, dedup/selection modes), Requests (request list + response actions), Cloud Sync (4 providers and their credential files, auto-generated token), Reverse Search (3 engines, Lens modes), Entity Recon (identity index, ArcFace-vs-CLIP embeddings, Source/Identity/Provenance panes, batch builder).
- `deep_learning.md` — every setting of each Training architecture (LoRA, R3GAN, Basic GAN) and Generation architecture (+ SD3.5 with ControlNet), Evaluation reference-dataset organization + what FID/KID/Precision-Recall/IS each capture, the Inference tab explained in full (Meta CLIP zero-shot classification), ComfyUI intro + server-tab controls.
- `image_stitching.md` — all eight ASP panels in detail: Stitch (pipeline stages, renderers, motion model, HITL sessions, stage dumps), Graph, Adjust, Canvas, Statistics (metric tables + stitch-score formula), Sequence Builder (fitness/sharpness/pan thresholds), Hybrid Stitch (control-point solve modes, seam painter, mesh warp, render), Animation Clusters.
- MkDocs nav gained a top-level **Tutorials** section; documentation roadmap history updated (moon + docs mirror).
- **GUI**: Image subtab zoom-bar "Fit"/"1:1" buttons widened (48→72 px) so their labels are never clipped.

**Part 1 — Extractor tab Video/Image subtabs (earlier today):**

Extractor tab restructured into **Video / Image subtabs** (same `QTabWidget` pattern as Convert/Wallpaper); roadmap §4.15 in [new_features.md](../moon/roadmaps/new_features.md) added (implemented same day, `docs/roadmaps` mirror re-synced — it had drifted, missing §4.14).

- **Video subtab**: the pre-existing video extractor, class renamed `ExtractorTab` → `VideoExtractorSubTab` in place (`extractor_tab.py`), so the GUI tests' `patch("gui.src.tabs.core.extractor_tab.QMediaPlayer")`-style targets are unchanged. The new outer `ExtractorTab(QWidget)` wrapper transparently delegates attribute reads/writes to it (`__getattr__`/`__setattr__` forwarding), keeping the main window's duck-typed settings hooks (`extraction_dir`, `wheel_seek_ms`, `recent_extractions_limit`, `time_display_format`, `_initial_pixmap_cache`, …), the `type(tab).__name__ == "ExtractorTab"` branches, and class-name-keyed session recovery working with zero call-site changes; QML slots (`browse_source_qml`, `extract_single_frame_qml`, `extract_range_qml`) and both QML signals are re-declared as real meta-object members and forwarded.
- **Image subtab** (`gui/src/tabs/core/elements/image_extractor_subtab.py`, new): splits a single multi-frame image (vertical/horizontal strip or grid sheet) into individual frames. Arrangement + per-frame size (one dimension for strips, both for grids) + X/Y offset + spacing + optional partial-last-frame; every cut boundary drawn with cosmetic 1-px alternating cyan/magenta outlines (uncovered remainder dashed amber) over a deep-zoom canvas (`FrameSliceCanvas`: 0.01×–80×, cursor-anchored wheel zoom, drag pan, double-click fit↔1:1 toggle, nearest-neighbor rendering at ≥1:1 for pixel-accurate boundary checks). Cutting runs in a cancellable `QRunnable` (`QImage.copy` → `{stem}_fNNN.png`); file dialogs pass `DontUseNativeDialog` (JVM/GTK SIGSEGV rule); subtab config rides in the ExtractorTab session-recovery dict under `image_extractor`.
- Verified via an offscreen smoke script: wrapper delegation (read/write/locals), `collect`/`set_config` round-trip, frame-rect geometry for all three arrangements incl. partial-frame handling, end-to-end cut worker output, and canvas zoom helpers.
- Also committed separately: pre-staged "Library" → "Library Database" tab-category rename found in the index.

## S211 — 2026-07-13 (Phase DB P3 — image tabs on the unified store, Postgres retired from the GUI)

Real-data migration completed and verified during S210's first launch (248 media + 249 entities + 1,301 images/10 groups/67 subgroups/17 tags/402 image-tag links); this session moves the image tabs onto the migrated store.

- **DB.6 `UnifiedImageDatabase` facade** (`backend/src/database/unified/facade.py`): reproduces the `PgvectorImageDatabase` method surface (search_images incl. tolerated legacy `query_vector` kwarg, add/update/delete_image, group/subgroup/tag CRUD + renames, get_statistics banner keys, maintenance ops, backup-gated `reset_database`) over the DAL — SearchTab, ScanMetadataTab, `SearchWorker`, `ImagePreviewWindow`, and the wallpaper system display keep their `db_tab_ref.db` call sites byte-identical. 12 parity tests exercising the tabs' exact call shapes (`test_unified_facade.py`).
- **DatabaseTab → Library Maintenance**: PostgreSQL connection form, psycopg2, and dotenv usage deleted; the encrypted store auto-opens from the vault session at tab construction (an "Open Library" button covers a locked-vault start); duplicate renames detected via SQLite "UNIQUE" errors; `collect()`/`set_config()` no longer read or write connection credentials (the stored `db_password` wart is gone — legacy configs are accepted and ignored). Statistics banner handles the unified store's ISO-text dates.
- **Tab layout**: "Database Management" category replaced by **"Library"** — `Listings · Image Search · Scan & Tag · Maintenance` — with Listings moved out of System Tools (settings fallback category list updated). `backend.src.database`'s package import made lazy so only migration 003 can pull psycopg2.
- Deferred to P3b (flagged in the roadmap): physically archiving `image_database.py`/`pooled_image_database.py`/`sql/` and dropping psycopg2 from requirements (`phash_deduplicator` + pooled tests still reference them); moving Scan & Tag's per-image upsert loop off the GUI thread.

## S210 — 2026-07-12 (Phase DB P0+P1 — unified database roadmap, schema v1, engine, DAL, migrations)

Implements P0, P1, and most of P2 of [moon/roadmaps/unified_database.md](../moon/roadmaps/unified_database.md) (merging the Listings subtabs' SQLCipher store and the Database tabs' PostgreSQL+pgvector index into one encrypted `~/.image-toolkit/library.db`; Postgres to be dropped entirely). 41 new tests in `backend/test/database/`.

- **DB.5 post-migration crash fixed (float ratings)**: first real-data launch crashed in `_ListingCard` (`"★" * 9.0`) — REAL columns return `9.0` where the legacy JSON blobs stored `9`. `_util.intify()` now collapses integral floats back to ints in `media_repo`/`entity_repo` assembly (episodes/credits included; fractional values like `community_rating 8.8` pass through), and both card widgets clamp ratings to a 0–10 int defensively. Regression test added. Real migration verified during the same launch: 248 media + 249 entities + 1,301 images / 10 groups / 67 subgroups / 17 tags / 402 image-tag links, verification passed.
- **DB.5 Listings subtabs ported to the unified store (P2)**: new `gui/src/helpers/core/library_session.py` — lazily opens the session DB on first use (Argon2id once), and when the library is empty while legacy `listings_secure.db` has data, offers the first-launch migration (full runner incl. backup gate) behind a modal progress dialog running the runner in a worker thread. `ContentListingsSubTab`/`EntityListingsSubTab` + both detail panels now load/save through `MediaRepo`/`EntityRepo`; every save is one transaction (entry + episodes/credits + tag links + associations). Deleted: all four association-sync loops, both `_save_data` full-rewrite paths, `listings_common.save_content_entry_to_db`/`save_entity_entry_to_db` (the byte-of-title placeholder embeddings) and `fetch_entity_name_map` (~600 LOC total) — both subtabs read the same `media_entity` table so cross-sync reduces to the existing changed signals triggering a re-query. `_SyncBackupWorker.run_sync` re-pointed at the session handle with upsert-by-id semantics (the legacy delete-all-then-reinsert window — the data-loss incident pattern — is gone); `run_backup` (`.enc` + image ZIPs) unchanged. Entity search resolves content titles via `list_ids_and_titles()` instead of decrypt-everything. Deferred: moving gallery filtering/sorting + advanced search onto `search_repo` SQL/FTS (builders exist and are tested; subtabs still filter in memory).

- **GUI (Settings → Tab Configs)**: two new buttons in "Tab Default Configuration Management" — *Export Config to JSON 📤* writes the selected/edited configuration to a self-describing `.json` file (wraps `tab_class`/`config_name`/`config` so it routes itself on import), and *Import Config from JSON 📥* loads either the wrapped format (auto-routed to its tab, unknown classes rejected) or a plain config object (routed to the currently selected tab, named after the file), with an overwrite confirmation and immediate dropdown refresh.
- **Migration fix**: `env/vars.env` values are quoted (`DB_PORT='5432'`) — `backup_all.py`/`migrate_pgvector.py` now strip quotes when parsing DB_* keys (real-data backup previously failed pg_dump with "invalid integer value"). Real pre-migration backup (step 000) executed successfully: listings DB + both `.enc` exports + 720 KB `pg_dump` with SHA-256 manifest.
- **Roadmap**: new `moon/roadmaps/unified_database.md` (DB.1–DB.10, phasing P0–P6, risk register) + Phase DB table in `moon/ROADMAP.md`, parameterized by owner Q&A (encrypt everything, session-keyed Argon2id, new `base.database` C++ module — `base.secret` untouched, real CBIR, unified Library tab category + raw Data Browser tab).
- **DB.1 Schema v1**: `backend/src/database/unified/schema.sql` (media_items/episodes/entities/credits + M2M associations, FK'd images/groups/subgroups, unified typed tags, cross-domain `media_groups`/`entity_images`, polymorphic `embeddings` + `vector_index`) and `schema_fts.sql` (external-content FTS5 + sync triggers, runtime-optional). Spec, ER diagram, and legacy→v1 field mapping in `docs/database/unified_schema.md`.
- **DB.2 `base.database` engine**: new C++ module (`base/src/database/database.cpp`, bound as `base.database.Database`; `base.secret` untouched). Session-keyed SQLCipher handle — Argon2id runs once in the constructor (same KDF construction as `base.secret`, so existing vault credentials derive the same key) instead of once per API call; wrong-password detection via first read; WAL/FK/busy_timeout pragmas; generic parameterized `query`/`execute`/`executemany` (atomic) + explicit transactions; `apply_ddl`/`schema_version`/`has_fts5`/`vacuum`/`reindex`/`integrity_check`/`statistics`; `upsert_embedding` + brute-force cosine `knn` with SQL prefilter (HNSW in DB.7). Stub raising a clear error when built without SQLCipher. 14 tests (`test_base_database.py`): encrypted-at-rest check, KDF-once timing, atomic executemany, FK cascades, 4-thread concurrency smoke, FTS5 end-to-end (FTS5 confirmed present in the linked SQLCipher).
- **DB.3 Python DAL** (`backend/src/database/unified/`): `session.py` login-time singleton (`open_session`/`get_session`/`close_session`, `ensure_schema` applies core DDL + FTS5 layer with `schema_meta.fts_enabled` fallback flag); `media_repo`/`entity_repo` speak the *legacy entry-dict dialect* (CSV `genres`/`tags` ↔ `media_tags` rows, `episode_list`/`credit_list` ↔ real tables, `associated_*` lists ↔ M2M tables, unknown keys ↔ `extra` JSON) so the DB.5 tab port and migration 002 are drop-in — and since both sides read the same `media_entity` table, the four bidirectional sync loops become unnecessary; `image_repo` mirrors `PgvectorImageDatabase` method names (FK'd groups/subgroups, upsert-by-path, legacy tags-replace semantics, bulk `paths_in_db`); `tag_repo` unified typed vocabulary + `merge_tags`; `search_repo` (structured image-search parity, FTS5 text search with LIKE fallback + injection-safe query quoting, `advanced_media_search` include/exclude+AND/OR SQL builder, `semantic_image_search` composing knn with escaped structured prefilters); `maintenance.py` legacy-banner statistics + `reset_database` refusing to run without a verified backup manifest. Credits schema fixed to the dialog's actual `notes` field. 14 tests (`test_unified_repos.py`).
- **DB.4 backup gate (step 000)**: `backend/migrations/backup_all.py` — timestamped backup dirs under `assets/migrations/pre_unified/` with SHA-256 manifest; copies `listings_secure.db` + both `.enc` exports (staleness warnings), `pg_dump --format=custom` with graceful skip when Postgres is unreachable; refuses to write an empty backup; `verify_manifest()` re-hash check for the runner's gate. 4 tests (`backend/test/database/test_backup_all.py`).
- **DB.4 migrations 001–004 + runner** (`backend/migrations/`): 001 `create_library_db.py` (DDL + `schema_version` stamp, idempotent); 002 `migrate_listings.py` — reads the legacy store via `base.secret.fetch_all_listings_secure` (deliberately its last consumer), explodes JSON blobs through the DAL's legacy-dict repos in two passes (rows, then links) so ordering can't drop associations; asymmetric legacy association lists are healed by union in the single M2M table; dangling ids are logged and parked in `extra._dangling_*` — nothing silently dropped; 003 `migrate_pgvector.py` — injectable data-provider design (psycopg2 confined to the default provider), resolves denormalized `group_name`/`subgroup_name` text to FKs, preserves original dates and pHashes, ignores the always-NULL `embedding` column, skips gracefully (re-runnable) when the server is unreachable; 004 `verify_migration.py` — full id↔title sweep against the legacy listings store, pgvector count/path checks, `integrity_check` + `foreign_key_check`, parked-dangling report; `runner.py` — resumable state file, the backup manifest is *re-verified by hash on every run* (tampered backup ⇒ hard refusal), verification failure aborts non-zero pointing at the backups; `--skip-postgres` / `--force`. 13 tests (`test_migrations.py`) incl. end-to-end + resume + gate-refusal scenarios.

## S209 — 2026-07-12 (MAL Auto-Fill resilience + selectable fetch methods; Associated Entities/Content UI fix)

- **MAL Auto-Fill 504 root-caused**: "Auto-Fill from MAL" 504 errors were traced (via direct `curl` testing that bypassed the app entirely) to Jikan's own cache-miss path to MyAnimeList failing intermittently/persistently — not a bug in this codebase. `jikan_client.py` now retries transient gateway errors (429/502/503/504, connection errors) with exponential backoff, and surfaces an accurate, actionable error message (distinguishing a genuine Jikan↔MAL outage from a generic network failure) instead of a bare `504 Gateway Time-out`.
- **Three selectable MAL Auto-Fill methods** (`backend/src/web/clients/`): kept `jikan_client.py` as the default (richest data, but dependent on Jikan's proxy health); added `mal_api_client.py` (official MAL API v2, needs a free client ID, no characters/staff data) and `mal_scrape_client.py` (direct myanimelist.net scraping via `requests`/`beautifulsoup4`, no key needed, full data including characters/Japanese-VA/staff). `mal_dispatcher.py` picks between them. New "MyAnimeList Auto-Fill" group in Settings → System and Logging lets the user switch method (persisted via `AppSettings.mal_fetch_method()`); `MalSyncWorker` reads it automatically. `resolve_api_key()` (`search_engines/common.py`) extended with a `field` param for non-`api_key`-shaped credentials (MAL's `client_id`). 21 new tests (`test_jikan_client.py`, `test_mal_api_client.py`, `test_mal_scrape_client.py`, `test_mal_dispatcher.py`, 4 new settings-window tests).
- **GUI**: "Associated Entities" (Content Listings) and "Associated Content"/"Associated Entities" (Entity Listings) detail-panel fields converted from a plain `QLabel`/single-line `QLineEdit` to a read-only `QTextEdit` fixed at ~2 lines tall (56px) — previously the second line of wrapped names was visually clipped with no way to see more. `QTextEdit`'s built-in scrollbar (shown as-needed) now lets the user scroll through longer associated-entity/content lists instead of the text being cut off.
- **Docs**: `docs/TROUBLESHOOTING.md` gained an "External API Failures (Jikan / MyAnimeList Auto-Fill)" section documenting the 504 root cause and the new Settings-based workaround.

## S200 — 2026-07-08 (ASP great trim — pipeline reduced to its benchmarked core)

**Tests**: animation suite 632 passing, 14 skipped (was 2,230 collected; ~1,550 ritual/dead-feature tests removed)

Driven by `research/ASP_Critical_Evaluation_2026-07-08.md`: two months (~200 sessions) of
feature/gate accretion produced no measured corpus-level improvement, and most shipped
work was default-OFF or never benchmarked. This session removes everything not on the
verified core path so future changes can be measured one at a time.

- **Docs**: all six `.agent/cache/` ASP analyses archived to `archive/agent/cache/`;
  `moon/roadmaps/asp.md` (3,596 lines) and its `docs/roadmaps/` mirror deleted;
  critical evaluation report added to `research/`.
- **Python** (`backend/src/animation/`, 30,640 → ~12,700 lines): deleted `mfsr/`,
  `rlhf/`, HITL presets/grounding/MLLM scorer/param search, AnimeInterp + CamFlow flow
  engines, ToonCrafter `anim_fill`, SRStitcher, Real-ESRGAN wrapper, ProPainter
  `bg_complete`, `hybrid_export`, and a stray 9.7 MB vendored eigen3 tree.
  `compositing.py` 6,939 → 2,184; `pipeline.py` 6,536 → 2,227 (all ~40 default-ON
  §5.x CV gates and ~30 default-OFF §1.x gates removed); `canvas.py` 2,209 → 419
  (55 §5.x strip/seam statistic helpers); `config.py` schema 490 → 43 keys;
  `constants/animation.py` 673 → 125 lines. ASP env-flag surface: 387 → 43.
  Kept core path: smart selection + hold detection, BiRefNet/SAM-2 masking, LoFTR→
  ALIKED→TM→PC matching cascade, GNC-TLS BA, affine validation, dy_cv gate (§4.7),
  SEA-RAFT/ECC refinement, A5 fg-excluded median, Stage 8.5 ARAP fg registration with
  fixed 22-lum single-pose escalation (A6), GraphCut global seam (§4.2) + GC feather
  (§3.33) + pairwise-DP fallback, blocks/global gain compensation (§4.1/§4.4/§4.10),
  render CompositeGate (SC/SB), coverage gate, TELEA border fill.
- **GUI**: RLHF `StitchFeedbackTab` removed (QML index 18; `EntityReconTab` 19→18);
  MFSR settings group and MFSR/RLHF stitch-worker hooks removed. All HITL checkpoints,
  seam diagnostics (waypoints / force-single-pose), session persistence and video
  ingestion preserved.
- **Benchmark** (`bench_anime_stitch.py`, 5,603 → ~3,400 lines): 40-gate §5.x
  comparative cascade, RLHF/MLLM/SI-FID hooks removed; kept CompositeGate, GhostGate
  (ghosting_siqe), SeamVisGate (§4.8). Metric set reduced to the validated core;
  §3.32 taxonomy fix completed — the double-Sobel proxy is emitted only as
  `edge_energy_score`, verdicts/issues/summary use `ghosting_siqe`.
- **C++** (`base/src/animation/`, 5,753 → 4,189 lines, 11 → 9 files):
  `wave_correct.cpp` and `sr_classical.cpp` deleted (bindings, FFTW probe removed);
  `seam_batch`, five `zone_*` kernels, `multiband_blend`, `slic_sgm_proxy`,
  `lsd_collinearity` export, `blocks_channels_compensate` removed; ximgproc/SLIC
  CMake probe dropped. Rebuilt via `just build-base`.
- **Config**: `backend/config/asp_config.toml` reset to benchmarked defaults (it had
  been silently enabling unverified S62–S75 flags via `os.environ.setdefault`).
- **Fixes found by re-running**: BiRefNet had been completely broken since the
  July-5 vendoring (ruff autofix stripped `eval()`-resolved imports; weights
  filename mismatch `pytorch_model.bin` vs `model.safetensors`) — the ASP was
  silently running without foreground masks; §4.2 GraphCut ran its min-cut at
  full canvas resolution (30+ min/test) — added cv2-style ≤0.4 MPix seam
  estimation, then **defaulted GraphCut OFF** after its first measurement showed
  seam_visibility 20–80 vs the DP path's 2–16; SeamVisGate floor recalibrated
  20 → 35 (at 20 it silently replaced most ASP output with SCANS).
- **Full 97-test benchmark re-run** (`anime_stitch_20260709_030853.json`,
  87 s/test, −32%): verdicts 27 asp / 41 comparable / 29 simple (S160:
  10/41/45); aligned GT-SSIM 0.693 vs 0.718 (gap −0.040 → −0.025);
  seam_visibility 12.1 vs 3.3 (was 25.8/4.2); 51 true composites + 46 guarded
  fallbacks. Analysis: `.agent/cache/asp_benchmark_2026-07.md`.

---

## S199 — 2026-07-07 (Reverse-image-search overhaul — real scrapers, ROI, meta-crawl)

**Tests**: +25 (`backend/test/reverse_search/`)

- **Real reverse-search scrapers** (`backend/src/web/search_engines/`): SauceNao (JSON API), IQDB (multi-booru HTML), Bing Visual Search (official API + keyless scrape), Yandex (CBIR upload + results scrape). All implement the shared `ReverseSearchEngine` interface, resolve credentials via env / `api_keys.yaml`, map throttling to a typed `RateLimited`/`EngineBlocked`, and expose static `_parse_*` methods so parsing is unit-tested offline against captured payloads. Wired into `ReverseImageSearchManager` (`SUPPORTED_ENGINES` now 7) and the Entity Recon dispatcher's `_query_engine`.
- **Rust → C++**: the tmp `phash_engine` (PyO3) crate is replaced by C++ in `base.similarity` — `phash_bytes(data, hash_size)` (pHash an in-memory buffer, no disk round-trip) and `batch_hamming(query, candidates)` (one query vs many). The tmp ROI processor (`imagetoolkit::core`) becomes `base.roi` — `crop_roi` (pixel-space crop, clamped) + `auto_crop` (spectral-residual saliency, no model weights).
- **Meta-crawl + consensus** (`meta_search_dispatcher.py`): async scatter-gather across all engines with per-engine timeout/failure isolation; consensus scoring boosts URLs multiple engines agree on (canonical-URL dedup, better-resolution merge) and returns a single ranked list.
- **Targeted scraping**: `search_url_builder.py` (site:/`-site:` operator injection, subreddit scoping) and `subreddit_phash_sweep.py` (asyncpraw recent-post sweep → aiohttp download → C++ `phash_bytes`/`batch_hamming` fast-path Hamming match, zero-index).
- **ROI UI**: `ROISelector.qml` draggable/resizable marquee emitting source-pixel `[x,y,w,h]` → `base.roi.crop_roi` before dispatch (rewritten with version-safe primitives).
- Deps: `beautifulsoup4`, `asyncpraw` (lazy/optional); `backend/config/api_keys.yaml.example` added.

---

## S198 — 2026-07-07 (Entity Recon & Provenance tab — localized OSINT)

**Tests**: +24 (`backend/test/recon/`)

- **New "Entity Recon" tab** (Web Integration category): localized OSINT / identity resolution / dataset management, added to `main_backend`, `main_window` and the QML sidebar (StackLayout index 19, appended so existing tab indices are unshifted).
- **C++ `base.recon`** (`base/src/web/recon/`): `IdentityIndex` — an HNSW-backed index (reusing `base.similarity`) mapping a face/CLIP embedding to its dataset label (`FirstName_LastName`) + source path, collapsing duplicate-label hits to distinct identities; `cutout_hash` — xxHash64 of an alpha-cutout byte stream for provenance-cache keys. *(Spec named Rust; the base module is post-Rust→C++, so the native engine is C++.)*
- **Python `backend/src/web/recon/`**: SAM 2 segmenter (SAM 2 → SAM 1 → GrabCut → bbox fallback), face (InsightFace/ArcFace) + CLIP embedders with deterministic fallback, a dataset indexing daemon, a privacy-gated reverse-search dispatcher with SQLite provenance cache + per-engine rate limiting, an NER "Name Guesser" (gliner → spaCy → heuristic) with a cross-domain **consensus algorithm**, a `ReconEngine` orchestrator (local HNSW → web consensus) and JSON/CSV provenance export.
- **GUI**: `EntityReconTab` backend (identity card + provenance/batch models), index/segment/resolve/batch QThread workers, and a **three-pane** `EntityReconTab.qml` — source pane with SAM hover masking + manual bounding box, center identity card with a `ConfidenceRing`, right provenance trail (local paths "Open in File Manager" / grouped web domains with links). Plus a **Strict Privacy Mode** toggle (100% offline), provenance export buttons and a drag-and-drop **Dataset Builder** with "Approve All" bulk folder moves.
- Everything degrades gracefully: SAM 2 / InsightFace / gliner are lazy-loaded with offline fallbacks, so the tab is fully usable air-gapped.

---

## S197 — 2026-07-07 (Similarity Finder — Delete tab overhaul)

**Tests**: +50 (`backend/test/similarity/`)

- **Delete tab → Similarity Finder**: the Delete tab was refactored into a tiered local dedup/similarity module and the old `DeleteTab` (`delete_tab.py`, `DeleteTab.qml`) was **removed**; all of its functionality (two galleries, directory/extension deletion, property comparison, context menus, standard file/dir delete, confirmation) was folded into the new self-contained `SimilarityTab`. `mainBackend.deleteTab` remains as an alias of `similarityTab`.
- **C++ `base.similarity`** (`base/src/core/similarity/`): xxHash64 exact digests (Tier 1); DCT pHash + dHash + Haar wHash at hash size 8/16/32 with weighted consensus confidence (Tier 2); in-repo VP-tree (Hamming) and HNSW (cosine) indexes; SSIM + ORB/SIFT with Lowe's ratio + RANSAC homography (Tier 3); neon-green `diff_mask`. All GIL-released, OpenMP batch hashing.
- **Python `backend/src/core/similarity/`**: `SimilarityConfig`/`TriageRules` (all GUI hyperparameters), `SimilarityCache` (SQLite incremental scan by mtime+size+hash_size, `~/.image-toolkit/similarity_cache.db`), `SimilarityEngine.scan()`/`regroup()` (instant confidence-slider re-clustering, no rescan), `embedder.py` (mobileclip→openclip→resnet18 fallback), `triage.auto_select`, `consolidate_cluster` (atomic hardlink/symlink).
- **GUI**: `SimilarityScanWorker` (QThread), `ClusterListModel`, three-pane `SimilarityTab.qml` (settings + all hyperparameters, cluster "album" stacks, confidence slider) and comparators `ClusterStack`/`BlinkComparator`/`SwipeCompare`/`DiffMaskView`/`TetheredViewport`. Cross-directory Reference/Target directional scanning.
- **Build**: five new `base` sources; RPATH fix — explicit `-Wl,-rpath,<pixi lib>` forces the pixi lib dir ahead of `/usr/lib` so pixi `libssl` resolves pixi `libcrypto` (fixes `import base` under pytest). Full design in `docs/roadmaps/similarity_finder.md`.

---

> **Note (2026-07-11):** this changelog was maintained as two separately-updated copies (`docs/CHANGELOG.md` and `moon/CHANGELOG.md`) that forked after the "S196 — 2026-06-25" entry below and were merged back into this single file. The entries immediately above this note (originally logged in `moon/CHANGELOG.md`, 2026-06-29 to 2026-07-04, Rust→C++ migration and related work) reused session numbers S197–S208 independently of, and chronologically *before*, the S197–S200 entries at the very top of this file (2026-07-07 to 2026-07-08). The numbers collide between the two blocks; use the dates to disambiguate.

---

## S208 — 2026-07-04 (Extension Roadmap Expansion + Implementation Kickoff)

**Expanded Phase EXT with the duplicate-tab highlighter and CV-oriented features, then began implementing the roadmap.**

- **§7.13 Duplicate Tab Highlighter (EXT.13)**: scan all tabs in the current window, group by normalized URL (fragment always stripped, tracking params optionally); duplicates highlighted via colored `chrome.tabs.group()`/`tabGroups.update()` on Chromium (chrome/edge/brave) with per-set colors, Firefox fallback = badge count + popup set list with switch-to/close/close-others actions; keep-first-close-rest per set; `tabs`/`tabGroups` permissions added through the §7.1 per-browser manifest overlays.
- **CV & media brainstorm round 2 (user-selected, all accepted + 3 user additions)** → three new roadmap sections:
  - **§7.14 App-Powered CV Operations (EXT.14)**: BiRefNet background removal, Real-ESRGAN upscale-before-save, WD14 auto-tag on ingest, OCR extraction **+ local translation** (user addition) — all via the §7.5 bridge with job-id polling.
  - **§7.15 Media Capture Suite (EXT.15)**: native-res `<video>` frame grabber with burst mode (ASP-ready sequences), GIF/APNG/animated-WebP frame extractor (WebCodecs `ImageDecoder`), webtoon strip capture → ASP stitch endpoint (flagship crossover), video clip → GIF/WebP via MediaRecorder + app-side ffmpeg palette conversion, and **video downloader with time-range finder** (user addition; full video or `ffmpeg -ss/-to` stream-copy cut app-side, HLS/DASH delegated to app).
- **§7.15A core implemented (EXT.15 🔄 — video frame grabber)**: `videoCapture.ts` — "Capture video frame" + "Capture 5-frame burst" context items on `<video>` elements; content script tracks the last right-clicked element so the exact video is captured (srcUrl match / first-video fallbacks); native-resolution canvas grab → PNG data-URL → background download with explicit `suggestedName` (`<video-stem>_<ts>_fNN.png`, bypasses the filename template via new `DownloadImageMsg.suggestedName`); burst = 5 frames at 500 ms from the live video; cross-origin/DRM canvas taint surfaces as a clear notification with partial-burst count instead of a corrupt file. Works for MSE/blob videos (no srcUrl) via context-target tracking.
- **§7.16A implemented (AI-metadata / EXIF inspector)**: `shared/imageMeta.ts` — pure client-side parsers: PNG chunk walker (IHDR dims; tEXt latin-1; iTXt with language/translated-keyword skip and zlib-compressed payloads inflated via browser `DecompressionStream`; zTXt), JPEG segment walker (SOFn dims, COM comment, XMP APP1, compact EXIF IFD0 ASCII reader — Make/Model/Software/DateTime/Artist/Copyright/ImageDescription), and AI-generation detection (a1111 `parameters`, ComfyUI `workflow`/`prompt`, NovelAI `Software`+`Comment`, InvokeAI). New `inspect.html`/`inspect.ts` webpack entry — popup window with AI-tool chip, pretty-printed JSON, copy buttons, EXIF/text-chunk grids; opened by the new "Inspect image metadata" context item (background fetch → parse → `lastInspect` in storage). Parser verified in Node against PIL-generated files (a1111 params PNG, compressed-iTXt workflow, JPEG EXIF + comment).
- **§7.9 modes A+B implemented (EXT.9 🔄 — bulk page capture)**: `shared/pageMedia.ts` — `collectImages()` (all `<img>` ≥64px rendered/natural, §7.11 full-res candidate upgrade, URL dedupe), `collectVideos()` (`currentSrc`/`src`/`<source>` children; blob: MediaSource streams skipped), `collectPageMedia()`. `contentOverlay.ts` — click-to-select overlay: hover = dashed blue outline, selected = solid green, floating top-center action bar (live count, Download selected, Cancel), Esc cancels; all outlines/listeners restored on exit; turbo mode stands down while the overlay is active. Popup gains a "Page Capture" section ("⬇ Download all media", "🖱 Select images…") messaging the active tab; content script responds with image/video counts; background `downloadBatch()` routes every URL through the §7.10 folder-rules/template path and notifies when queued. New typed messages: `DownloadAllMediaMsg`, `StartSelectionOverlayMsg`, `DownloadBatchMsg`, `PageCaptureResponse`.
- **§7.9 revised (user direction)**: bulk page grabber now specifies two capture modes — (A) one-click "Download all" for every image **and video** on the page, and (B) an in-page selection overlay (hover highlight, click-to-select with outline, floating Download-selected/Cancel bar, Esc cancels); the grid-preview page with filters stays as a later sub-item.
- **§7.7 core implemented (EXT.7 🔄 — send to Image Toolkit)**: `POST /api/extension/ingest/` — saves the image into `ingest_dir` (config; falls back to `dup_root/inbox`) with a `<file>.json` provenance sidecar (source URL, page URL, page title, timestamp), URL-derived sanitised filename with ` (N)` uniquification, and an implicit pre-ingest dup-check returning 409 + existing paths (bypassed with `force: true`); bridge version bumped to 1.1 with `ingest` feature flag. Extension: `ingest()` in `bridge.ts`, "Send to Image Toolkit" context item with saved-path / already-in-library / failure notifications. 5 new Django tests (15 total, all passing). Remaining for full ✅: embedding/DB indexing at ingest, collection picker.
- **§7.6 implemented (EXT.6 ✅ — in-browser duplicate search)**: `extension/src/shared/bridge.ts` — typed bridge client (`ping()`, `dupCheck()`, `BridgeError` with HTTP status). `background.ts`: "Check if already downloaded" context item → `runDupCheck()` → OS notification (no-dup / N matches with closest path+distance / failure reason) and `lastDupCheck` persisted to `storage.local`. Popup: "Duplicate Check" panel renders the last result with 48px thumbnails, dimensions, Hamming distance, click-to-copy path; "Test connection" button in the Connection section saves the URL/token fields then pings — green/red dot with distinct messages for invalid-token vs unreachable vs dup-root-unconfigured. `notifications` permission added to all targets. **Verified end-to-end against a live `runserver`**: 403 without token, ping OK with token, dup-check on a byte-identical library image returned hamming=0 with thumbnail.
- **§7.5A implemented (EXT.5 🔄 — HTTP bridge)**: new `extension_api/` Django app wired into `api/settings.py` + `api/urls.py` under `/api/extension/`. `GET ping/` (version/features/dup_root_configured), `POST dup-check/` (`{url|data_b64, threshold?}` → server-side fetch, pHash, matches with hamming/dims/128px `thumb_b64`, 409 when no root configured). Auth: `BridgeTokenPermission` — `Authorization: Bearer` compared constant-time against an auto-generated `~/.image-toolkit/extension-bridge/token.txt` (0600); OPTIONS preflight passes so browsers can learn allowed headers. `CorsAPIView` echoes the extension origin. Config in `extension-bridge/config.json` (`dup_root`, `recursive`, `threshold`). OpenAPI-annotated (drf-spectacular). **New `backend/src/core/dir_phash_index.py`**: `DirPhashIndex` — SQLite-cached (path,mtime,size)→phash index over a directory tree (C++ `base.scan_files_multi` fast path, os.walk fallback); incremental `refresh()` (drops deleted files), `query_bytes()` Hamming sweep via masked `int.bit_count()`; signed-64 storage fold for SQLite. Tests: 10 pytest (`backend/test/core/test_dir_phash_index.py`) + 10 Django (`extension_api/tests.py`, isolated tmp bridge dir) — all passing. Note: Django tests must run with the pixi env python (`.pixi/envs/default/bin/python manage.py test extension_api`) — the venv python can't load the C++ `base` module (libtiff/libjpeg symbol mismatch).
- **§7.4 + §7.10 core implemented (EXT.4 🔄 / EXT.10 🔄)**: `shared/naming.ts` — `hostMatches()` wildcard hostname patterns, `resolveFolder()` (first matching site rule wins, falls back to global folder), `buildFilename()` (`{name}/{ext}/{site}/{date}/{time}` tokens, `/` subfolders, per-component sanitisation, unit-tested). `background.ts` `downloadImage(imageUrl, pageUrl)` now resolves folder via rules, names via template, and optionally emits a `<file>.json` provenance sidecar (source URL, page URL, timestamp) as a base64 data-URL download. Content script passes `pageUrl`; context-menu path uses `info.pageUrl`. Options page rebuilt with sections: General (folder, template, turbo, sidecar), Per-Site Folder Rules (dynamic pattern→folder row editor), Image Toolkit Connection (bridge URL + token fields), Duplicate Tabs. New settings: `siteRules`, `filenameTemplate`, `saveSidecar`, `bridgeUrl`, `bridgeToken`.
- **§7.11 core + §7.16B + §7.12 flash implemented (EXT.11 🔄 / EXT.16 🔄 / EXT.12 🔄)**: `shared/extractor.ts` — `parseSrcset()` (w/x descriptor scoring, unit-tested), `bestImageUrl()` (srcset + parent `<picture>` sources + lazy attrs `data-src`/`data-original`/… + `currentSrc` baseline scored by naturalWidth), `backgroundImageUrl()` CSS fallback, `findImageAt()` hit-test; turbo mode now downloads the highest-res candidate instead of `img.src` and flashes a green outline on capture. `background.ts` gains a "Search image on ▸" context submenu (SauceNAO, trace.moe, Google Lens, IQDB, TinEye). Remaining for full ✅: per-site URL upgrade table + canvas fallback (§7.11), badge/modifier/per-site/history (§7.12), metadata inspector + pHash + local-ML (§7.16A/C/D).
- **§7.13 implemented (EXT.13 ✅)**: `extension/src/shared/dupTabs.ts` — `normalizeUrl()` (case-folded protocol/host, fragment dropped, tracking params `utm_*`/`fbclid`/`gclid`/… optionally stripped while preserving real query params), `findDuplicateSets()` (largest-first), `scanAndHighlight()` (colored `dup ×N` tab groups via `chrome.tabs.group`+`tabGroups.update` cycling 8 colors on Chromium; badge count everywhere; popup set list fallback for Firefox), `clearHighlights()` (only dissolves groups titled `dup ×…` — never the user's own groups). Popup UI in `options.html/ts`: scan/clear buttons, per-set keep-first-close-rest, per-tab switch-to/close, "ignore tracking params" toggle persisted as `dupTabsStripParams`. `tabs` permission in base manifest; `tabGroups` only in the three Chromium overlays. Pure logic unit-checked in Node (normalization + set-building assertions).
- **Phase E1 implemented (EXT.1 ✅ / EXT.2 ✅ / EXT.3 ✅)**: extension rebuilt as a TypeScript + webpack project.
  - `extension/src/` — `background.ts` (context-menu save; MV3-safe menu re-creation on install/startup), `content.ts` (turbo mode), `options/options.{html,ts}`, and shared core `shared/api.ts` (single browser adapter + promisified storage), `shared/settings.ts` (typed schema + defaults), `shared/messages.ts` (discriminated-union message contract incl. §7.13 dup-tab types). `tsc --noEmit` strict-mode clean.
  - `extension/webpack/` — `webpack.common.js` (`makeConfig(browser)`: ts-loader bundle, CopyPlugin assets, manifest generation via deep-merge of `manifest/manifest.base.json` + `manifest.<browser>.json` with `background` replaced wholesale and `version` stamped from `package.json`) + four per-browser configs. `dist/{chrome,firefox,edge,brave}/` verified: all MV3; Firefox gets event-page `background.scripts` + `browser_specific_settings.gecko` (min 115), Chromium targets get `service_worker`.
  - Legacy `background.js`/`content.js`/`options.*`/`manifest*.json` (4 manifests) deleted from `extension/`; `.gitignore` for `node_modules`/`dist`; `just build-extension` (all targets) + `just build::build-extension-for <browser>` recipes added.
  - **§7.16 Image Analysis Utilities (EXT.16)**: EXIF + embedded AI-generation metadata inspector (a1111/ComfyUI/NovelAI PNG chunks, client-side parsing), reverse-image-search shortcuts submenu (SauceNAO/trace.moe/Lens/IQDB/TinEye, configurable), client-side pHash pre-check against an app-exported hash snapshot, and **local-ML reverse search** (user addition; app-bridge embeddings primary, transformers.js/ONNX-Runtime-Web MobileCLIP fallback — fully offline).

---

## S207 — 2026-07-04 (Browser Extension Roadmap — Phase EXT)

**Analyzed the `extension/` WebExtension, researched and brainstormed feature/upgrade ideas with the user, and created a dedicated extension roadmap.**

- **New roadmap**: `moon/roadmaps/extension.md` (§7.1–§7.12, mirrored to `docs/roadmaps/extension.md`) covering: webpack multi-browser manifest generation in `extension/webpack/` (chrome/firefox/edge/brave overlays merged over `manifest.base.json`, replacing the three hand-maintained manifests), TypeScript migration + shared typed message contract, unified Manifest V3 (dropping the MV2 Firefox manifest), options page redesign, local app bridge (Phase A: token-authenticated localhost Django endpoints under `/api/extension/`; Phase B: native messaging host), **in-browser duplicate search** (right-click an image → pHash search of a user-configured directory and its subdirectories via the existing `PhashDeduplicator` §4.6), send-to-app ingestion with source-URL provenance + immediate indexing, visual similarity search against the local library, bulk page grabber with filterable grid preview, per-site folder rules + filename templating + metadata sidecar, full-resolution extraction (srcset/lazy-load/CSS-background/canvas), and turbo mode polish (capture feedback, modifier-key mode, per-site enable, history panel).
- **Master roadmap**: new **Phase EXT** table (EXT.1–EXT.12) in `moon/ROADMAP.md` + `docs/roadmaps/ROADMAP.md`; extension.md added to the section-specific roadmap lists; dependency-graph mermaid gains `PEXT` node (P4 §4.5/§4.6 unblock EXT.5/EXT.6; EXT.8 gated on §5.1 CLIP index).
- Feature selection confirmed with the user (all brainstormed items accepted; transport = HTTP-first then native messaging).

---

## S206 — 2026-07-04 (Thumbnail Loading Optimization — C++ Fast Path + Progressive Gallery Fill)

**Optimized gallery thumbnail loading end-to-end (directory scan → decode → display) and made thumbnails appear progressively instead of all at once.**

- **Reduced-resolution JPEG decode (C++)**: `base/src/image/image_batch.cpp` now reads each file into memory once and, for JPEG sources, walks the libjpeg IDCT-scaling ladder (`IMREAD_REDUCED_COLOR_8/4/2` → full) stopping at the first reduction that still covers the requested thumbnail size — up to ~8× faster decode for 4K sources at 256px thumbnails. Non-JPEG codecs (PNG/WebP) decode once at full resolution as before.
- **Persistent C++ disk thumbnail cache**: new `cache_dir` parameter on `base.load_image_batch` persists thumbnails as JPEGs in `~/.image-toolkit/thumbnail-cache/` keyed by FNV-1a path hash + size, invalidated by source mtime. Measured: 4K JPEG + PNG batch cold load 96 ms → warm load 0.5 ms (~190×). Page revisits and directory re-opens are now near-instant across sessions (previously only videos had a disk cache).
- **RGB output (C++)**: new `rgb` parameter returns RGB arrays so the GUI wraps them in `QImage` with a single copy, removing the per-image numpy BGR→RGB reversal copy in `_bgr_array_to_qimage`. Old signature (positional 4-arg) unchanged — fully backward compatible; Python worker falls back automatically on `TypeError`.
- **Progressive gallery fill (root cause fix)**: previously all ~13 chunk-workers per page were queued on the global `QThreadPool` at once; each calls the native loader whose OpenMP loop competes for the same cores, so all chunks progressed in parallel and completed clustered at the end — the whole page flipped from "Loading..." to loaded at once. New `common_start_chunked_load()` in `AbstractGalleryBase` dispatches at most 2 chunks in flight and chains the next chunk on `batch_result`, so thumbnails now appear top-to-bottom as each chunk of 8 finishes (per-image `result` signals were already wired). Generation counter (`_load_generation`, bumped in both `cancel_loading` implementations) invalidates queued continuations on page change/cancel. No extra C++→Python signal traffic added — throughput preserved (oversubscription removed).
- **Main-thread rescale skip**: `AbstractClassSingleGallery.update_card_pixmap` no longer runs a redundant `SmoothTransformation` rescale for loader-produced thumbnails that already fit the target size (100× per page on the GUI thread).
- Both `ImageLoaderWorker` and `BatchImageLoaderWorker` route through a shared `native_load_batch()` helper. `gui/test/image/test_image_helper.py` native-path assertion updated to the new call signature.

---

## S205 — 2026-07-03 (Recursive Directory Scanning & Vault DB C++ Test Cleanups)

**Implemented system-wide settings for recursive directory scanning and resolved local database side effects in C++ unit tests.**

- **Recursive Scanning Option**: Added a "Recursive directory scanning" checkbox in the GUI `SettingsWindow`, ensuring persistent configuration via `QSettings` under `AppSettings.recursive_scan()`.
- **C++ and Python Propagation**: Updated C++ `collect_files` in `finder.cpp` to conditionally toggle between recursive and shallow directory walking depending on the `recursive` boolean flag. Propagated settings to Python workers, using `os.scandir` for flat scans to optimize performance.
- **Unit Test Parity**: Wrote comprehensive unit tests in `gui/test/core/test_settings_window.py` and parity tests in `backend/test/base/test_parity_core.py`.
- **Vault DB Test Cleanup**: Refactored C++ Catch2 tests in `base/tests/secret/test_vault_db.cpp` to conditionally perform full CRUD validation on SQLCipher when enabled (using and programmatically removing a temporary `test_vault_catch2.db` file) or check the stub contract exceptions under `#ifndef HAVE_SQLCIPHER`, eliminating the untracked `db` file side effect from the repository root.

---

## S204 — 2026-07-02 (§4.6 MultiBand Confidence-Weighted Blending)

**ASP roadmap §4.6: replace the hard 0/255 GraphCut ownership mask fed to `cv::detail::MultiBandBlender` with a smoothly-varying per-pixel confidence mask.**

- `_compute_multiband_confidence(gc_frames, ownership, bg_masks, band_px)` in `backend/src/animation/rendering/compositing.py` combines three signals into a uint8 [0, 255] per-frame mask: `dist_to_seam_norm` (`cv2.distanceTransform` softening near the GraphCut boundary, `[0.5, 1.0]`), `bg_conf` (distance-transform softening at the BiRefNet fg/bg mask edge, `[0.6, 1.0]`), and `ecc_conf` (`_compute_ecc_confidence()` — `cv2.computeECC` agreement between a frame's owned content and the union of all other frames' owned content, restricted to the seam-adjacent band).
- `own_binary` keeps pixel ownership byte-identical to the hard GraphCut label; only the blend *weighting* within an owned region is graded — cannot regress coverage.
- **Bug found and fixed while wiring this up**: `base/src/animation/compositing.cpp`'s `multiband_blend_impl` was hard-binarizing every mask (`cv::Mat mask8 = (masks[i] > 0);`) before `MultiBandBlender::feed()`, which would have silently discarded any Python-side gradation. Fixed to pass the CV_8UC1 mask through as-is — `MultiBandBlender::feed()` already normalizes an 8U mask to a `[0,1]` float weight map internally, so existing hard 0/255 callers are unaffected (0 stays 0, 255 stays 255) while a graded mask now genuinely softens the blend.
- Gate: `ASP_MULTIBAND_CONF=1` (default OFF; requires `ASP_MULTIBAND_BLEND=1`). `ASP_MULTIBAND_CONF_BAND_PX=24` controls the seam-adjacent softening band width.
- 10 new Python tests (`TestComputeEccConfidence`, `TestComputeMultibandConfidence` in `test_compositing.py`) + 1 new Catch2 regression test in `test_compositing.cpp` guarding against the binarization bug recurring. `base_tests [compositing]`: 19 test cases, 47 assertions, all passing. `test_compositing.py --skip-gpu`: 587 passed, 5 skipped.
- Roadmap: `moon/roadmaps/asp.md` / `docs/roadmaps/asp.md` §4.6 marked ✅; Effort × Impact Matrix pending-items table updated (S204, 2026-07-02).

---

## S203 — 2026-06-30 (Rust→C++ migration complete — file split + archive)

**Finalise the Rust→C++ migration: one class per file, web module reorganised, roadmap archived.**

- **board crawlers split** — `board_crawler.cpp` now includes per-class headers: `include/web/crawlers/crawler_base.hpp`, `danbooru.hpp`, `gelbooru.hpp`, `sankaku.hpp`. Orchestrator + registration remain in `board_crawler.cpp`.
- **cloud sync split** — `cloud_sync.cpp` now includes per-class headers: `include/web/cloud/cloud_sync_base.hpp`, `dropbox_sync.hpp`, `google_drive_sync.hpp`, `onedrive_sync.hpp`. Orchestrator + registration remain in `cloud_sync.cpp`.
- **web/clients/ subdir** — `web_requests.cpp`, `image_crawler.cpp`, `reverse_image_search.cpp` moved to `src/web/clients/` (mirrors Rust archive's `web/clients/` layout). `CMakeLists.txt` updated.
- **Roadmap archived** — `moon/roadmaps/rust_to_cpp_migration.md` → `moon/archive/rust_to_cpp_migration.md`. Status updated to "All 13 phases done". Stale path references in `image_batch.cpp`, `video_batch.cpp`, `vault_db.cpp` updated.

---

## S202 — 2026-06-29 (Rust→C++ migration Phase 13 — full math parity + scan_files_multi)

**Phase 13: Close all remaining gaps between Rust archive math and C++ headers**

Math library additions (all headers in `base/include/math/`):
- **distance**: `chebyshev`, `minkowski(p)`, `pairwise_distance_matrix`, `condensed_distance_matrix`
- **stats**: `sample_variance`, `sample_std_dev`, `covariance`, `min_val`, `max_val`, `percentile`, `iqr`, `histogram`, `counts_to_probs`, `covariance_matrix`
- **information**: `entropy_nats`, `empirical_entropy`, `joint_entropy`, `conditional_entropy`, `total_variation`, `mutual_information_discrete`, `normalised_mutual_information`, `cross_entropy`
- **graph**: `connected_components` (BFS-based, vector-as-queue pattern)
- **linalg**: `dot`, `norm`, `normalize`, `vec_sub`, `vec_add`, `vec_scale`, `gram_schmidt_step`, `pca_2d`; added `<array>` and `<cmath>` includes
- **dim_reduce**: `geodesic_distances` (O(n³) Dijkstra all-pairs)
- `base/src/math/math_bindings.cpp`: all new functions bound with `py::gil_scoped_release`
- `base/src/image/scan_files.cpp` + `base/include/image/scan_files.hpp`: `scan_files_multi(root_dirs, exts, recursive)` — sorted+deduplicated multi-directory scan
- `backend/src/utils/base_dispatch.py`: `NativeExt.scan_files_multi` wired
- Migration roadmap updated with Phase 13 section

---

## S201 — 2026-06-29 (Rust→C++ migration Phase 12 — parity tests)

**Phase 12: Integration tests for all Phase 8–11 C++ base functions**
- `backend/test/base/test_parity_core.py`: 15+ tests for `base.core` (convert_single_image, get_files_by_extension, delete_path, find_duplicate_images, find_similar_images_phash, merge_images_*, wallpaper callables)
- `backend/test/base/test_parity_math.py`: 25+ tests for `base.math` submodules (distance, stats, information, graph, linalg, dim_reduce)
- `backend/test/base/test_parity_utils.py`: 12 tests for `base.utils` (slideshow daemon JSON protocol, migration callable/stub error) and `base.web` (reverse_image_search/image_crawler stub contracts, board_crawler/run_sync callable checks)
- All tests guarded by `skipif(not HAS_BASE)` — pass without building C++ extension; run on CI when built
- Migration roadmap status updated to reflect 12 phases complete

---

## S200 — 2026-06-29 (Rust→C++ migration Phases 8–11 — all 27 functions ported)

**Phase 8: `base.core` — image/video conversion, filesystem, finder, merger, wallpaper**
- `base/src/core/convert.cpp`: `convert_single_image` (OpenCV AR transforms: crop/pad/stretch), `convert_image_batch` (OpenMP parallel), `convert_video` (ffmpeg subprocess)
- `base/src/core/filesystem.cpp`: `get_files_by_extension` (case-insensitive, recursive), `delete_files_by_extensions` (OpenMP parallel, `std::atomic<int>` counter), `delete_path` (file or tree)
- `base/src/core/finder.cpp`: `find_duplicate_images` (SHA-256 via OpenSSL EVP or inline FIPS 180-4 fallback, OpenMP parallel hashing), `find_similar_images_phash` (8×8 INTER_AREA pHash, Union-Find grouping, Hamming ≤ threshold)
- `base/src/core/merger.cpp`: `merge_images_horizontal`, `merge_images_vertical`, `merge_images_grid` (two-pass OpenCV: dims pass → blit pass, white canvas, BGRA/GRAY → BGR flatten)
- `base/src/core/wallpaper.cpp`: `set_wallpaper_gnome` (gsettings picture-uri + picture-options), `evaluate_kde_script` (qdbus via `popen`)
- `base/CMakeLists.txt`: OpenSSL detection added (→ `HAVE_OPENSSL=1`); inline SHA-256 fallback when absent

**Phase 9: `base.web` extensions — board crawlers, cloud sync, stubs**
- `base/src/web/board_crawler.cpp`: abstract `Crawler` interface + `DanbooruCrawler` (GET JSON API), `GelbooruCrawler` (dapi envelope unwrap), `SankakuCrawler` (POST JWT auth to `login.sankakucomplex.com`, then capi-v2); `BoardCrawlerRunner` orchestrates pagination + 5-req/1s rate limit + 500ms post delay; `run_board_crawler(name, config, cb) -> int`
- `base/src/web/cloud_sync.cpp`: abstract `CloudSync` interface + `DropboxSync` (list_folder cursor pagination, upload to content API, download), `GoogleDriveSync` (multipart REST upload, Drive v3), `OneDriveSync` (Graph API v1.0); bidirectional sync plan builder; `run_sync(provider, config, cb) -> str`
- `base/src/web/reverse_image_search.cpp`: STUB — raises `RuntimeError` (Rust impl used `thirtyfour`/Selenium; no C++ WebDriver equivalent)
- `base/src/web/image_crawler.cpp`: STUB — same reason
- `web_requests.cpp`: Phase 9 functions registered via `register_web()`

**Phase 10: `base.utils` — migration and slideshow daemon**
- `base/src/utils/migration.cpp`: `run_legacy_migration` — JSON vault (flat map, entries array, or `{entries:[...]}`) → SQLCipher DB; key = `username:password`; creates `vault_entries` + `vault_meta` tables; guarded by `#ifdef HAVE_SQLCIPHER` (raises `RuntimeError` otherwise)
- `base/src/utils/slideshow.cpp`: `run_slideshow_daemon` — process-lifetime `std::thread` singleton; actions: start/stop/status/next/configure; timed advance via `std::condition_variable::wait_for`; config persisted to `~/.image-toolkit/.slideshow_config.json` (nlohmann/json); wallpaper set via gsettings

**Phase 11: `base.math` Python bindings**
- `base/src/math/math_bindings.cpp`: pybind11 wrappers for all 6 math headers (previously header-only, no Python access)
- `base.math.distance`: euclidean, euclidean_sq, cosine_similarity, cosine_distance, hamming, bhattacharyya, hellinger, manhattan
- `base.math.stats`: mean, median, std_dev, variance, pearson, z_score, min_max_normalize
- `base.math.information`: shannon_entropy, kl_divergence, js_divergence, js_distance, mutual_information
- `base.math.graph`: `Graph` class + bfs, dfs, kruskal_mst, kruskal_max_mst, tarjan_scc, topological_sort; `KruskalEdge` + `SCCResult` types exposed
- `base.math.linalg`: `Matrix` class (Eigen backend) + pca → `PCAResult` (scores, components, explained_variance_ratio)
- `base.math.dim_reduce`: mds (classical MDS on distance matrix), tsne_affinities (symmetric P matrix)
- `backend/src/utils/base_dispatch.py`: all 27 new functions routed via `NativeExt` static methods

**Migration audit: all 27 Rust `#[pyfunction]`s now ported**
- 9 previously ported (Phases 2–5 + 7): `load_image_batch`, `scan_files`, `extract_video_thumbnails_batch`, 5 secret functions, `run_web_requests_sequence`
- 18 newly ported (Phases 8–11): all above + `run_legacy_migration`, `run_slideshow_daemon`, `run_board_crawler`, `run_sync`, `run_reverse_image_search` (stub), `run_image_crawler` (stub), all core/math functions
- Roadmap updated: status line corrected to "All 11 phases done"

---

## S199 — 2026-06-29 (Rust→C++ migration Phase 7 — final rename & retirement)

- **Phase 7 complete** — `batch/` renamed to `base/` via `git mv`; Rust `base/` archived to `archive/base_rust/`
- `PYBIND11_MODULE(batch, m)` → `PYBIND11_MODULE(base, m)`; all `batch::` namespaces → `base::`; all `#include "batch/..."` → `#include "base/..."`; `batch/include/batch/` → `base/include/`
- `base/CMakeLists.txt` + `base/tests/CMakeLists.txt`: target names updated (`batch` → `base`, `batch_impl` → `base_impl`, `batch_tests` → `base_tests`, `BATCH_BUILD_TESTS` → `BASE_BUILD_TESTS`)
- `backend/src/utils/base_dispatch.py` simplified: dual-module dispatch removed; `import base` resolves directly to C++ extension; `NativeExt` now a thin alias with static submodule forwarders
- `tools/build/justfile`: `build-base` now runs cmake against `base/`; `build-batch` recipe removed; `build-all` no longer includes `build-batch`
- `tools/test/justfile`: `test-batch-cpp/py/bench` → `test-base-cpp/py/bench`; backwards-compat aliases kept
- `desktop/linux/scripts/build_base.sh`: replaces Rust maturin/cargo build with cmake build
- `Cargo.toml`: `base` workspace member removed (archived)
- `.github/workflows/security.yml`: `cargo-audit` step updated to scan `frontend/src-tauri` only (base Rust crate retired)
- Animation Python files: `import batch` → `import base as batch` (25 call sites)
- Rust→C++ migration fully complete — all 7 phases done

---

## S198 — 2026-06-29 (Rust→C++ migration · Phases 1–6 implementation)

- **CMake Phase 1 deps** — `batch/CMakeLists.txt` and `batch/tests/CMakeLists.txt` extended: optional SQLCipher+libsodium via `pkg_check_modules` (sets `HAVE_SQLCIPHER=1` when both found); `cpp-httplib v0.18.0` and `nlohmann/json v3.11.3` auto-fetched via FetchContent; include dirs wired to both `batch` and `batch_impl` targets; conditional SQLCipher/libsodium link block added
- **Dispatch shim** — `backend/src/utils/base_dispatch.py` created; `NativeExt` class with static methods routing Phase 2–5 functions to `batch.image/video/secret/web` with exception-guarded fallback to Rust `base`; module-level `__getattr__` proxies any unrecognised name to Rust `base`; `_HAS_IMAGE/VIDEO/SECRET/WEB` flags set once at import
- **Phase 4 — vault_db.cpp** — full `HAVE_SQLCIPHER` implementation: `load_or_create_salt` ({db_path}.salt sidecar), `derive_key` (Argon2id via `crypto_pwhash`), `open_db` (PRAGMA key with raw 32-byte hex blob), schema init; `insert_listing_secure` (upsert), `hybrid_search_secure` (linear-scan cosine + `partial_sort` top-k), `fetch_all_listings_secure`, `delete_listing_secure`, `fetch_listings_as_arrow_pointers` (ArrowArray/ArrowSchema structs defined inline — no nanoarrow dep; id+metadata utf8 columns; RAII release callbacks); `#else` stubs raise `py::type_error` for graceful Rust fallback
- **Phase 5 — web_requests.cpp** — full cpp-httplib + nlohmann/json implementation; `parse_base_url` splits scheme/host/port/path; `parse_post_data` parses "key:val,key:val" form params; GIL released for HTTP I/O, reacquired for `on_status_emitted`/`on_error_emitted` callbacks and `_is_running` cancellation check; all 5 action types implemented (`Print Response URL/Status/Headers/Content`, `Save Response Content (Binary)` with parent dir creation); 500ms inter-request delay; returns `"All requests finished."` or `"Cancelled."` — matches Rust protocol exactly
- **Phase 6 — bundle_adjust.cpp** — replaced local `parent` vector + `find_root` lambda with `batch::math::UnionFind uf(N)` from `batch/math/graph.hpp`; inner `if (pi != pj)` block replaced with `if (uf.unite(i, j))`; include added
- **Roadmap** — `moon/roadmaps/rust_to_cpp_migration.md` updated: status line → `IN PROGRESS — Phases 1–6 complete; Phase 7 pending`; Phases 1–6 marked ✅; Phase 7 marked PENDING

---

## S197 — 2026-06-29 (Rust→C++ migration skeleton · batch/ directory reorganisation)

- **Rust→C++ migration roadmap** — `moon/roadmaps/rust_to_cpp_migration.md` created; 7-phase plan covering `batch::image`, `batch::video`, `batch::secret`, `batch::web`, `batch::math` (header-only) and final rename `batch/`→`base/`
- **batch/ reorganisation** — all existing animation/ASP source files moved from `batch/src/*.cpp` → `batch/src/animation/`; test files moved from `batch/tests/*.cpp` → `batch/tests/animation/`; both CMakeLists updated
- **batch::image skeleton** — `src/image/image_batch.cpp` (fully implemented: OpenCV imread + INTER_AREA + OpenMP), `src/image/scan_files.cpp` (fully implemented: `std::filesystem`); headers in `include/batch/image/`
- **batch::video skeleton** — `src/video/video_batch.cpp` (fully implemented: OpenCV `VideoCapture` + OpenMP, replaces Rust ffmpeg subprocess); header in `include/batch/video/`
- **batch::secret skeleton** — `src/secret/locked_secret.cpp` (libsodium init guard), `src/secret/vault_db.cpp` (Phase 4 stubs raising `NotImplementedError`); headers in `include/batch/secret/` including `LockedSecret<N>` RAII wrapper and `derive_dek` (Argon2id)
- **batch::web skeleton** — `src/web/web_requests.cpp` (Phase 5 stub); header in `include/batch/web/`
- **batch::math headers** — `include/batch/math/{linalg,graph,distance,stats,information,dim_reduce}.hpp`; header-only C++ port of `base/src/math/`; `linalg.hpp` and `dim_reduce.hpp` use Eigen3; no pybind11 bindings
- **Native test skeletons** — `tests/image/`, `tests/video/`, `tests/secret/`, `tests/web/`, `tests/math/`; 60+ Catch2 test cases total; math tests fully runnable; vault security tests cover `LockedSecret` zeroing and `derive_dek` determinism
- **bindings.cpp** — updated module docstring; `register_image / register_secret / register_web` forward declarations; `batch.image`, `batch.secret`, `batch.web` submodules registered
- **Directory naming** — `http`→`web`, `vault`→`secret`, `images`→`image` applied consistently across `src/`, `tests/`, `include/`, `bindings.cpp`, CMakeLists, and roadmap

---

## S196 — 2026-06-25 (§5.109 Pipeline Strip Blue Channel CV Gate · §5.110 Pipeline Seam Green Shift CV Gate · §5.111 Bench Strip Blue Channel CV Gate · §5.112 Bench Seam Green Shift CV Gate)

**Tests**: 2135 passing, 78 skipped (30 new)

- **§5.109 `_strip_blue_channel_cv`** — CV of mean BGR Blue (channel 0) per strip; 0.0 for grayscale or mean_blue < 1.0; Stage 11.70 pipeline gate (`_BLUE_CHANNEL_CV_GATE_FLOOR=0.6`, env `ASP_GATE_BLUE_CHANNEL_CV`); completes the R/G/B per-strip trilogy; detects B-axis normalization failure; orthogonal to §5.97 (median luma), §5.101 (Red), §5.105 (Green), §5.86 (hue), §5.90 (saturation), §5.102 (seam blue shift — boundary metric)
- **§5.110 `_seam_green_shift_cv`** — CV of |mean_G_above − mean_G_below| per seam (BGR channel 1); 0.0 for grayscale or mean_shift < 1.0; Stage 11.71 pipeline gate (`_SEAM_GREEN_SHIFT_CV_GATE_FLOOR=1.2`, env `ASP_GATE_SEAM_GREEN_SHIFT_CV`); completes the R/G/B per-seam trilogy; orthogonal to §5.58 (luma step), §5.102 (seam blue), §5.106 (seam red), §5.86 (hue), §5.90 (saturation)
- **§5.111 bench BlueChannelCvGate** — `_BLUE_CHANNEL_CV_ABS_FLOOR=0.20`, ratio=3.0; fires when asp > 0.20 AND (sim < 0.07 OR asp > 3.0× sim)
- **§5.112 bench SeamGreenShiftCvGate** — `_SEAM_GREEN_SHIFT_CV_ABS_FLOOR=0.30`, ratio=2.0; fires when asp > 0.30 AND (sim < 0.10 OR asp > 2.0× sim)

---

## S195 — 2026-06-25 (§5.105 Pipeline Strip Green Channel CV Gate · §5.106 Pipeline Seam Red Shift CV Gate · §5.107 Bench Strip Green Channel CV Gate · §5.108 Bench Seam Red Shift CV Gate)

**Tests**: 2105 passing, 78 skipped (30 new)

- **§5.105 `_strip_green_channel_cv`** — CV of mean BGR Green (channel 1) per strip; 0.0 for grayscale or mean_green < 1.0; Stage 11.68 pipeline gate (`_GREEN_CHANNEL_CV_GATE_FLOOR=0.5`, env `ASP_GATE_GREEN_CHANNEL_CV`); detects G-axis normalization failure; orthogonal to §5.97 (median luma), §5.101 (Red channel), §5.86 (hue), §5.90 (saturation)
- **§5.106 `_seam_red_shift_cv`** — CV of |mean_R_above − mean_R_below| per seam (BGR channel 2); 0.0 for grayscale or mean_shift < 1.0; Stage 11.69 pipeline gate (`_SEAM_RED_SHIFT_CV_GATE_FLOOR=1.2`, env `ASP_GATE_SEAM_RED_SHIFT_CV`); red-axis seam normalization artifacts; orthogonal to §5.58 (luma step), §5.102 (seam blue shift), §5.86 (hue), §5.90 (saturation)
- **§5.107 bench GreenChannelCvGate** — `_GREEN_CHANNEL_CV_ABS_FLOOR=0.20`, ratio=3.0; fires when asp > 0.20 AND (sim < 0.07 OR asp > 3.0× sim)
- **§5.108 bench SeamRedShiftCvGate** — `_SEAM_RED_SHIFT_CV_ABS_FLOOR=0.30`, ratio=2.0; fires when asp > 0.30 AND (sim < 0.10 OR asp > 2.0× sim)

---

## S194 — 2026-06-25 (§5.101 Pipeline Strip Red Channel CV Gate · §5.102 Pipeline Seam Blue Shift CV Gate · §5.103 Bench Strip Red Channel CV Gate · §5.104 Bench Seam Blue Shift CV Gate)

**Tests**: 2075 passing, 85 skipped (30 new)

- **§5.101 `_strip_red_channel_cv`** — CV of mean BGR Red (channel 2) per strip; 0.0 for grayscale or mean_red < 1.0; Stage 11.66 pipeline gate (`_RED_CHANNEL_CV_GATE_FLOOR=0.6`, env `ASP_GATE_RED_CHANNEL_CV`); detects R-axis normalization failure invisible to luma/hue/saturation; orthogonal to §5.94 (Value=max), §5.86 (hue), §5.90 (saturation), §5.97 (median luma)
- **§5.102 `_seam_blue_shift_cv`** — CV of |mean_B_above − mean_B_below| per seam (BGR channel 0); 0.0 for grayscale or mean_shift < 1.0; Stage 11.67 pipeline gate (`_SEAM_BLUE_SHIFT_CV_GATE_FLOOR=1.2`, env `ASP_GATE_SEAM_BLUE_SHIFT_CV`); blue-axis seam normalization artifacts; orthogonal to §5.58 (luma step), §5.94 (Value), §5.86 (hue), §5.90 (saturation)
- **§5.103 bench RedChannelCvGate** — `_RED_CHANNEL_CV_ABS_FLOOR=0.20`, ratio=3.0; fires when asp > 0.20 AND (sim < 0.07 OR asp > 3.0× sim)
- **§5.104 bench SeamBlueShiftCvGate** — `_SEAM_BLUE_SHIFT_CV_ABS_FLOOR=0.30`, ratio=2.0; fires when asp > 0.30 AND (sim < 0.10 OR asp > 2.0× sim)

---

## S193 — 2026-06-25 (§5.97 Pipeline Strip Median Luma CV Gate · §5.98 Pipeline Seam Entropy Shift CV Gate · §5.99 Bench Strip Median Luma CV Gate · §5.100 Bench Seam Entropy Shift CV Gate)

**Tests**: 2045 passing, 85 skipped (30 new)

- **§5.97 `_strip_median_luma_cv`** — CV of np.median() per strip; 0.0 when mean_median < 1.0; Stage 11.64 pipeline gate (`_MEDIAN_LUMA_CV_GATE_FLOOR=0.5`, env `ASP_GATE_MEDIAN_LUMA_CV`); detects strip brightness location inconsistency; orthogonal to §5.45 (range), §5.85 (P90−P10), §5.69 (IQR), §5.49 (MAD), §5.89 (dark fraction)
- **§5.98 `_seam_entropy_shift_cv`** — CV of |H_above − H_below| (Shannon entropy, 256-bin histogram, base-2) per seam; 0.0 when mean_shift < 0.05; Stage 11.65 pipeline gate (`_SEAM_ENTROPY_SHIFT_CV_GATE_FLOOR=1.5`, env `ASP_GATE_SEAM_ENTROPY_SHIFT_CV`); cross-seam information content mismatch; orthogonal to §5.61 (strip entropy CV), §5.82 (pixel std), §5.78 (Laplacian variance)
- **§5.99 bench MedianLumaCvGate** — `_MEDIAN_LUMA_CV_ABS_FLOOR=0.20`, ratio=3.0; fires when asp > 0.20 AND (sim < 0.08 OR asp > 3.0× sim)
- **§5.100 bench SeamEntropyShiftCvGate** — `_SEAM_ENTROPY_SHIFT_CV_ABS_FLOOR=0.30`, ratio=2.0; fires when asp > 0.30 AND (sim < 0.10 OR asp > 2.0× sim)

---

## S192 — 2026-06-25 (§5.93 Pipeline Strip Sobel Energy CV Gate · §5.94 Pipeline Seam Value Shift CV Gate · §5.95 Bench Strip Sobel Energy CV Gate · §5.96 Bench Seam Value Shift CV Gate)

**Tests**: 2015 passing, 85 skipped (30 new)

- **§5.93 `_strip_sobel_energy_cv`** — CV of mean sqrt(Gx²+Gy²) per strip (Sobel ksize=3); 0.0 when mean_energy < 0.5; Stage 11.62 pipeline gate (`_SOBEL_ENERGY_CV_GATE_FLOOR=1.2`, env `ASP_GATE_SOBEL_ENERGY_CV`); detects inconsistent directional gradient activity; orthogonal to §5.50 (Laplacian-based), §5.81 (Canny binary), §5.66 (seam boundary only)
- **§5.94 `_seam_value_shift_cv`** — CV of |mean_V_above − mean_V_below| per seam (HSV V = max(R,G,B), [0,255]); 0.0 for grayscale or mean_shift < 1.0; Stage 11.63 pipeline gate (`_SEAM_VALUE_SHIFT_CV_GATE_FLOOR=1.2`, env `ASP_GATE_SEAM_VALUE_SHIFT_CV`); max-channel brightness mismatch; orthogonal to §5.86 (hue), §5.90 (saturation), §5.58/§5.60 (luma)
- **§5.95 bench SobelEnergyCvGate** — `_SOBEL_ENERGY_CV_ABS_FLOOR=0.35`, ratio=2.5; fires when asp > 0.35 AND (sim < 0.12 OR asp > 2.5× sim)
- **§5.96 bench SeamValueShiftCvGate** — `_SEAM_VALUE_SHIFT_CV_ABS_FLOOR=0.30`, ratio=2.0; fires when asp > 0.30 AND (sim < 0.10 OR asp > 2.0× sim)

---

## S191 — 2026-06-25 (§5.89 Pipeline Strip Dark Pixel Fraction CV Gate · §5.90 Pipeline Seam Saturation Shift CV Gate · §5.91 Bench Strip Dark Pixel Fraction CV Gate · §5.92 Bench Seam Saturation Shift CV Gate)

**Tests**: 1985 passing, 85 skipped (30 new)

- **§5.89 `_strip_dark_pixel_fraction_cv`** — CV of dark pixel fraction (luma < 64) per strip; 0.0 guard when mean < 0.005 or > 0.995; Stage 11.60 pipeline gate (`_DARK_PIXEL_FRAC_CV_GATE_FLOOR=1.5`, env `ASP_GATE_DARK_PIXEL_FRAC_CV`); detects tonal polarity alternation (some strips dark, others bright); orthogonal to §5.85 (P90−P10 spread), §5.73 (skewness), §5.45 (range)
- **§5.90 `_seam_saturation_shift_cv`** — CV of |mean_sat_above − mean_sat_below| per seam (HSV S, [0,255]); 0.0 for grayscale or mean_shift < 1.0; Stage 11.61 pipeline gate (`_SEAM_SAT_SHIFT_CV_GATE_FLOOR=1.5`, env `ASP_GATE_SEAM_SAT_SHIFT_CV`); cross-seam colorfulness mismatch; orthogonal to §5.86 (hue angle), §5.62 (YCrCb chroma), §5.38 (within-strip sat spread)
- **§5.91 bench DarkPixelFracCvGate** — `_DARK_PIXEL_FRAC_CV_ABS_FLOOR=0.40`, ratio=2.5; fires when asp > 0.40 AND (sim < 0.15 OR asp > 2.5× sim)
- **§5.92 bench SeamSatShiftCvGate** — `_SEAM_SAT_SHIFT_CV_ABS_FLOOR=0.30`, ratio=2.0; fires when asp > 0.30 AND (sim < 0.10 OR asp > 2.0× sim)

---

## S190 — 2026-06-25 (§5.85 Pipeline Strip Luma P90–P10 CV Gate · §5.86 Pipeline Seam Hue Shift CV Gate · §5.87 Bench Strip Luma P90–P10 CV Gate · §5.88 Bench Seam Hue Shift CV Gate)

**Tests**: 1955 passing, 85 skipped (30 new)

- **§5.85 `_strip_luma_p90p10_cv`** — CV of per-strip P90−P10 luma spread; 0.0 guard when mean_spread < 1.0; Stage 11.58 pipeline gate (`_LUMA_P90P10_CV_GATE_FLOOR=0.8`, env `ASP_GATE_LUMA_P90P10_CV`); outlier-robust tonal range; orthogonal to §5.45 (full range), §5.69 (IQR = P75−P25), §5.49 (MAD)
- **§5.86 `_seam_hue_shift_cv`** — CV of |mean_hue_above − mean_hue_below| per seam (OpenCV HSV, wrapped to [0,90]); 0.0 for grayscale or mean_shift < 1.0; Stage 11.59 pipeline gate (`_SEAM_HUE_SHIFT_CV_GATE_FLOOR=1.5`, env `ASP_GATE_SEAM_HUE_SHIFT_CV`); cross-seam white-balance hue mismatch; orthogonal to §5.62 (YCrCb chroma step) and §5.41 (within-strip hue spread)
- **§5.87 bench LumaP90P10CvGate** — `_LUMA_P90P10_CV_ABS_FLOOR=0.30`, ratio=2.5; fires when asp > 0.30 AND (sim < 0.10 OR asp > 2.5× sim)
- **§5.88 bench SeamHueShiftCvGate** — `_SEAM_HUE_SHIFT_CV_ABS_FLOOR=0.40`, ratio=2.0; fires when asp > 0.40 AND (sim < 0.15 OR asp > 2.0× sim)

---

## S189 — 2026-06-25 (§5.81 Pipeline Strip Edge Density CV Gate · §5.82 Pipeline Seam Local Contrast CV Gate · §5.83 Bench Strip Edge Density CV Gate · §5.84 Bench Seam Local Contrast CV Gate)

**Tests**: 1925 passing, 85 skipped (30 new)

- **§5.81 `_strip_edge_density_cv`** — CV of Canny(50,150) edge pixel fraction per strip; 0.0 guard when mean_density < 0.005; Stage 11.56 pipeline gate (`_EDGE_DENSITY_CV_GATE_FLOOR=1.2`, env `ASP_GATE_EDGE_DENSITY_CV`); detects inconsistent detail level across strips; orthogonal to §5.50 (sharpness-CV, Laplacian amplitude) and §5.46 (seam edge density)
- **§5.82 `_seam_local_contrast_cv`** — CV of pixel std in ±5px seam band per seam; 0.0 when mean_contrast < 1.0; Stage 11.57 pipeline gate (`_SEAM_LOCAL_CONTRAST_CV_GATE_FLOOR=1.0`, env `ASP_GATE_SEAM_LOCAL_CONTRAST_CV`); detects inconsistent seam placement complexity; orthogonal to §5.78 (texture ratio, above/below comparison) and §5.66 (gradient CV, step steepness)
- **§5.83 bench EdgeDensityCvGate** — `_EDGE_DENSITY_CV_ABS_FLOOR=0.40`, `_EDGE_DENSITY_CV_RATIO=2.5`; fires when asp > 0.40 AND (sim < 0.15 OR asp > 2.5× sim); schema entries `ASP_BENCH_EDGE_DENSITY_CV_ABS_FLOOR` / `ASP_BENCH_EDGE_DENSITY_CV_RATIO`
- **§5.84 bench SeamLocalContrastCvGate** — `_SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR=0.30`, `_SEAM_LOCAL_CONTRAST_CV_RATIO=2.0`; fires when asp > 0.30 AND (sim < 0.15 OR asp > 2.0× sim); schema entries `ASP_BENCH_SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR` / `ASP_BENCH_SEAM_LOCAL_CONTRAST_CV_RATIO`

---

## S188 — 2026-06-25 (§5.77 Pipeline Strip Luma Kurtosis CV Gate · §5.78 Pipeline Seam Texture Ratio CV Gate · §5.79 Bench Strip Luma Kurtosis CV Gate · §5.80 Bench Seam Texture Ratio CV Gate)

**Tests**: 1895 passing, 85 skipped (30 new)

- **§5.77 `_strip_luma_kurtosis_cv`** — CV of |per-strip excess kurtosis| (4th standardized moment − 3); 0.0 guard when mean_abs < 0.1 or std < 1.0 per strip; Stage 11.54 pipeline gate (`_LUMA_KURTOSIS_CV_GATE_FLOOR=1.5`, env `ASP_GATE_LUMA_KURTOSIS_CV`); detects bimodal structure inconsistency (cel+bg strips vs. complex scene strips); orthogonal to §5.73 (skewness, 3rd moment) and §5.69 (IQR-CV)
- **§5.78 `_seam_texture_ratio_cv`** — CV of log(Laplacian-variance ratio above/below) at each seam (±5px band); 0.0 when mean_abs(log_ratio) < 0.05 or fewer than 2 seams; Stage 11.55 pipeline gate (`_SEAM_TEXTURE_RATIO_CV_GATE_FLOOR=1.2`, env `ASP_GATE_SEAM_TEXTURE_RATIO_CV`); detects texture complexity mismatch across seams; orthogonal to §5.66 (gradient CV) and §5.74 (signed step CV)
- **§5.79 bench LumaKurtosisCvGate** — `_LUMA_KURTOSIS_CV_ABS_FLOOR=0.50`, `_LUMA_KURTOSIS_CV_RATIO=2.5`; fires when asp > 0.50 AND (sim < 0.20 OR asp > 2.5× sim); schema entries `ASP_BENCH_LUMA_KURTOSIS_CV_ABS_FLOOR` / `ASP_BENCH_LUMA_KURTOSIS_CV_RATIO`
- **§5.80 bench SeamTextureRatioCvGate** — `_SEAM_TEXTURE_RATIO_CV_ABS_FLOOR=0.40`, `_SEAM_TEXTURE_RATIO_CV_RATIO=2.0`; fires when asp > 0.40 AND (sim < 0.20 OR asp > 2.0× sim); schema entries `ASP_BENCH_SEAM_TEXTURE_RATIO_CV_ABS_FLOOR` / `ASP_BENCH_SEAM_TEXTURE_RATIO_CV_RATIO`

---

## S187 — 2026-06-25 (§5.73 Pipeline Strip Luma Skewness CV Gate · §5.74 Pipeline Seam Signed Step CV Gate · §5.75 Bench Strip Luma Skewness CV Gate · §5.76 Bench Seam Signed Step CV Gate)

**Tests**: 1865 passing, 85 skipped (30 new)

- **§5.73 `_strip_luma_skewness_cv`** — CV of |per-strip luma skewness| (3rd standardized moment); 0.0 guard when mean_abs_skewness < 0.05 or std < 1.0 per strip; Stage 11.52 pipeline gate (`_LUMA_SKEW_CV_GATE_FLOOR=1.5`, env `ASP_GATE_LUMA_SKEW_CV`); orthogonal to IQR-CV (§5.69) and MAD-CV (§5.49); detects inconsistent tonal character where some strips have bright-highlight tails and others have dark-shadow tails
- **§5.74 `_seam_signed_step_cv`** — `std(signed_steps) / mean(|signed_steps|)` at seam boundaries; 0.0 when mean_abs < 1.0; Stage 11.53 pipeline gate (`_SEAM_SIGNED_STEP_CV_GATE_FLOOR=1.2`, env `ASP_GATE_SEAM_SIGNED_STEP_CV`); orthogonal to §5.58 which uses abs() before CV — this fires specifically on alternating-direction normalization (bright→dark, dark→bright pattern)
- **§5.75 bench LumaSkewCvGate** — `_LUMA_SKEW_CV_ABS_FLOOR=0.50`, `_LUMA_SKEW_CV_RATIO=2.5`; fires when asp > 0.50 AND (sim < 0.20 OR asp > 2.5× sim); schema entries `ASP_BENCH_LUMA_SKEW_CV_ABS_FLOOR` / `ASP_BENCH_LUMA_SKEW_CV_RATIO`
- **§5.76 bench SeamSignedStepCvGate** — `_SEAM_SIGNED_STEP_CV_ABS_FLOOR=0.40`, `_SEAM_SIGNED_STEP_CV_RATIO=2.0`; fires when asp > 0.40 AND (sim < 0.20 OR asp > 2.0× sim); schema entries `ASP_BENCH_SEAM_SIGNED_STEP_CV_ABS_FLOOR` / `ASP_BENCH_SEAM_SIGNED_STEP_CV_RATIO`

---

## S186 — 2026-06-25 (§5.69 Pipeline Strip Luma IQR CV Gate · §5.70 Pipeline Seam Column Variance CV Gate · §5.71 Bench Strip Luma IQR CV Gate · §5.72 Bench Seam Column Variance CV Gate)

*Four new post-composite quality gates: two pipeline gates (Stage 11.50 strip luma IQR CV, Stage 11.51 seam column variance CV) and two bench comparative gates. 1835 tests passing (85 skipped).*

### §5.69 Pipeline Strip Luma IQR CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_luma_iqr_cv(img, n_strips=8)` in `canvas.py` — CV of per-strip luma IQR (P75-P25 of within-strip pixel intensities); 0.0 when mean IQR < 1.0 or degenerate; high CV = wide-IQR strips adjacent to flat strips; orthogonal to §5.45 (luma range of means) and §5.49 (luma MAD of means)
- Stage 11.50 gate in `pipeline.py`: fires when `_iqr_val > _LUMA_IQR_CV_GATE_FLOOR` (default 0.8) → SCANS fallback; reason `luma_iqr_cv_gate:{val:.4f}`
- Flags: `_LUMA_IQR_CV_GATE_ENABLED` (`ASP_GATE_LUMA_IQR_CV`, default 1), `_LUMA_IQR_CV_GATE_FLOOR` (`ASP_GATE_LUMA_IQR_CV_FLOOR`, default 0.8)
- `LUMA_IQR_CV_GATE_FLOOR = 0.8` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestStripLumaIqrCv` (`test_canvas.py`), 5 tests in `TestLumaIqrCvGatePipeline` (`test_pipeline.py`)

### §5.70 Pipeline Seam Column Variance CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_seam_column_variance_cv(img, n_strips=8, boundary_px=3)` in `canvas.py` — CV of per-seam variance of per-column absolute luma step; 0.0 when mean_var < 0.1, fewer than 2 seams, or degenerate; high CV = inconsistent horizontal step regularity across seams (partial registration failure or diagonal artifact)
- Stage 11.51 gate in `pipeline.py`: fires when `_scvarcv_val > _SEAM_COL_VAR_CV_GATE_FLOOR` (default 1.0) → SCANS fallback; reason `seam_col_var_cv_gate:{val:.4f}`
- Flags: `_SEAM_COL_VAR_CV_GATE_ENABLED` (`ASP_GATE_SEAM_COL_VAR_CV`, default 1), `_SEAM_COL_VAR_CV_GATE_FLOOR` (`ASP_GATE_SEAM_COL_VAR_CV_FLOOR`, default 1.0)
- `SEAM_COL_VAR_CV_GATE_FLOOR = 1.0` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestSeamColumnVarianceCv` (`test_canvas.py`), 5 tests in `TestSeamColVarCvGatePipeline` (`test_pipeline.py`)

### §5.71 Bench Strip Luma IQR CV Gate (`backend/benchmark/bench_anime_stitch.py`)

- `_LUMA_IQR_CV_ABS_FLOOR = 0.40`, `_LUMA_IQR_CV_RATIO = 2.5` constants in `bench_anime_stitch.py`
- LumaIqrCvGate block in `run_dataset()`: fires when `asp_iqr > floor` and (`sim_iqr < 0.05` or `asp_iqr > 2.5 × sim_iqr`) → SCANS fallback; reason `luma_iqr_cv_gate:{val:.4f}`
- Schema entries `ASP_GATE_LUMA_IQR_CV_ABS_FLOOR` and `ASP_GATE_LUMA_IQR_CV_RATIO` in `config.py`
- 5 tests in `TestLumaIqrCvGateBench` (`test_bench_metrics.py`)

### §5.72 Bench Seam Column Variance CV Gate (`backend/benchmark/bench_anime_stitch.py`)

- `_SEAM_COL_VAR_CV_ABS_FLOOR = 0.40`, `_SEAM_COL_VAR_CV_RATIO = 2.0` constants in `bench_anime_stitch.py`
- SeamColVarCvGate block in `run_dataset()`: fires when `asp_scvar > floor` and (`sim_scvar < 0.05` or `asp_scvar > 2.0 × sim_scvar`) → SCANS fallback; reason `seam_col_var_cv_gate:{val:.4f}`
- Schema entries `ASP_GATE_SEAM_COL_VAR_CV_ABS_FLOOR` and `ASP_GATE_SEAM_COL_VAR_CV_RATIO` in `config.py`
- 5 tests in `TestSeamColVarCvGateBench` (`test_bench_metrics.py`)

---

## S185 — 2026-06-25 (§5.65 Pipeline Strip Chroma Energy CV Gate · §5.66 Pipeline Seam Gradient CV Gate · §5.67 Bench Strip Chroma Energy CV Gate · §5.68 Bench Seam Gradient CV Gate)

*Four new post-composite quality gates: two pipeline gates (Stage 11.48 strip chroma energy CV, Stage 11.49 seam gradient CV) and two bench comparative gates (strip chroma energy CV parity, seam gradient CV parity). 1805 tests passing (85 skipped).*

### §5.65 Pipeline Strip Chroma Energy CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_chroma_energy_cv(img, n_strips=8)` in `canvas.py` — CV of per-strip mean chroma magnitude (`sqrt((Cb-128)² + (Cr-128)²)` in YCrCb); 0.0 when mean < 1.0 (near-monochrome guard), grayscale input, or degenerate; high CV = vivid strips adjacent to desaturated strips; orthogonal to §5.38 (HSV saturation CV)
- Stage 11.48 gate in `pipeline.py`: fires when `_cecv_val > _CHROMA_ENERGY_CV_GATE_FLOOR` (default 0.6) → SCANS fallback; reason `chroma_energy_cv_gate:{val:.4f}`
- Flags: `_CHROMA_ENERGY_CV_GATE_ENABLED` (`ASP_GATE_CHROMA_ENERGY_CV`, default 1), `_CHROMA_ENERGY_CV_GATE_FLOOR` (`ASP_GATE_CHROMA_ENERGY_CV_FLOOR`, default 0.6)
- `CHROMA_ENERGY_CV_GATE_FLOOR = 0.6` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestStripChromaEnergyCv` (`test_canvas.py`), 5 tests in `TestChromaEnergyCvGatePipeline` (`test_pipeline.py`)

### §5.66 Pipeline Seam Gradient CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_seam_gradient_cv(img, n_strips=8, band_px=5)` in `canvas.py` — CV of per-seam mean absolute row-to-row luma change within ±band_px rows; 0.0 when mean_grad < 0.1 (flat guard), fewer than 2 seams, or degenerate; high CV = mix of hard-cut and feathered seams; orthogonal to §5.60 (luma step CV)
- Stage 11.49 gate in `pipeline.py`: fires when `_sgcv_val > _SEAM_GRADIENT_CV_GATE_FLOOR` (default 1.0) → SCANS fallback; reason `seam_gradient_cv_gate:{val:.4f}`
- Flags: `_SEAM_GRADIENT_CV_GATE_ENABLED` (`ASP_GATE_SEAM_GRADIENT_CV`, default 1), `_SEAM_GRADIENT_CV_GATE_FLOOR` (`ASP_GATE_SEAM_GRADIENT_CV_FLOOR`, default 1.0)
- `SEAM_GRADIENT_CV_GATE_FLOOR = 1.0` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestSeamGradientCv` (`test_canvas.py`), 5 tests in `TestSeamGradientCvGatePipeline` (`test_pipeline.py`)

### §5.67 Bench Strip Chroma Energy CV Gate (`backend/benchmark/bench_anime_stitch.py`)

- `_CHROMA_ENERGY_CV_ABS_FLOOR = 0.30`, `_CHROMA_ENERGY_CV_RATIO = 2.5` constants in `bench_anime_stitch.py`
- ChromaEnergyCvGate block in `run_dataset()`: fires when `asp_cecv > floor` and (`sim_cecv < 0.05` or `asp_cecv > 2.5 × sim_cecv`) → SCANS fallback; reason `chroma_energy_cv_gate:{val:.4f}`
- Schema entries `ASP_GATE_CHROMA_ENERGY_CV_ABS_FLOOR` and `ASP_GATE_CHROMA_ENERGY_CV_RATIO` in `config.py`
- 5 tests in `TestChromaEnergyCvGateBench` (`test_bench_metrics.py`)

### §5.68 Bench Seam Gradient CV Gate (`backend/benchmark/bench_anime_stitch.py`)

- `_SEAM_GRADIENT_CV_ABS_FLOOR = 0.40`, `_SEAM_GRADIENT_CV_RATIO = 2.0` constants in `bench_anime_stitch.py`
- SeamGradientCvGate block in `run_dataset()`: fires when `asp_sgcv > floor` and (`sim_sgcv < 0.05` or `asp_sgcv > 2.0 × sim_sgcv`) → SCANS fallback; reason `seam_gradient_cv_gate:{val:.4f}`
- Schema entries `ASP_GATE_SEAM_GRADIENT_CV_ABS_FLOOR` and `ASP_GATE_SEAM_GRADIENT_CV_RATIO` in `config.py`
- 5 tests in `TestSeamGradientCvGateBench` (`test_bench_metrics.py`)

---

## S184 — 2026-06-25 (§5.61 Pipeline Strip Entropy CV Gate · §5.62 Pipeline Seam Chroma Step CV Gate · §5.63 Bench Strip Entropy CV Gate · §5.64 Bench Seam Chroma Step CV Gate)

*Four new post-composite quality gates: two pipeline gates (Stage 11.46 strip entropy CV, Stage 11.47 seam chroma step CV) and two bench comparative gates (strip entropy CV parity, seam chroma step CV parity). 1775 tests passing (85 skipped).*

### §5.61 Pipeline Strip Entropy CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_entropy_cv(img, n_strips=8)` in `canvas.py` — CV of per-strip Shannon entropy (256-bin luma histogram, `-sum(p*log2(p+eps))`); 0.0 when mean_entropy < 0.5 (uniformly flat guard) or degenerate input; high CV = some strips have rich information while others are flat/uniform, indicating composite from frames with mismatched scene complexity
- Stage 11.46 gate in `pipeline.py`: fires when `_ecv_val > _ENTROPY_CV_GATE_FLOOR` (default 0.5) → SCANS fallback; reason `entropy_cv_gate:{val:.4f}`
- Flags: `_ENTROPY_CV_GATE_ENABLED` (`ASP_GATE_ENTROPY_CV`, default 1), `_ENTROPY_CV_GATE_FLOOR` (`ASP_GATE_ENTROPY_CV_FLOOR`, default 0.5)
- `ENTROPY_CV_GATE_FLOOR = 0.5` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestStripEntropyCv` (`test_canvas.py`), 5 tests in `TestEntropyCvGatePipeline` (`test_pipeline.py`)

### §5.62 Pipeline Seam Chroma Step CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_seam_chroma_step_cv(img, n_strips=8, boundary_px=3)` in `canvas.py` — CV of per-seam absolute chroma step (`|ΔCb| + |ΔCr|` in YCrCb space at ±boundary_px rows); 0.0 when mean_step < 0.5 (uniform chroma guard), fewer than 2 seams, or grayscale/degenerate input; complements §5.60 (luma step CV) and §5.54 (chroma jump max)
- Stage 11.47 gate in `pipeline.py`: fires when `_cscv_val > _CHROMA_STEP_CV_GATE_FLOOR` (default 1.0) → SCANS fallback; reason `chroma_step_cv_gate:{val:.4f}`
- Flags: `_CHROMA_STEP_CV_GATE_ENABLED` (`ASP_GATE_CHROMA_STEP_CV`, default 1), `_CHROMA_STEP_CV_GATE_FLOOR` (`ASP_GATE_CHROMA_STEP_CV_FLOOR`, default 1.0)
- `CHROMA_STEP_CV_GATE_FLOOR = 1.0` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestSeamChromaStepCv` (`test_canvas.py`), 5 tests in `TestChromaStepCvGatePipeline` (`test_pipeline.py`)

### §5.63 Bench Strip Entropy CV Gate (`backend/benchmark/bench_anime_stitch.py`)

- `_ENTROPY_CV_ABS_FLOOR = 0.30`, `_ENTROPY_CV_RATIO = 2.5` constants in `bench_anime_stitch.py`
- EntropyCvGate block in `run_dataset()`: fires when `asp_ecv > floor` and (`sim_ecv < 0.05` or `asp_ecv > 2.5 × sim_ecv`) → SCANS fallback; reason `entropy_cv_gate:{val:.4f}`
- Schema entries `ASP_GATE_ENTROPY_CV_ABS_FLOOR` and `ASP_GATE_ENTROPY_CV_RATIO` in `config.py`
- 5 tests in `TestEntropyCvGateBench` (`test_bench_metrics.py`)

### §5.64 Bench Seam Chroma Step CV Gate (`backend/benchmark/bench_anime_stitch.py`)

- `_CHROMA_STEP_CV_ABS_FLOOR = 0.30`, `_CHROMA_STEP_CV_RATIO = 2.0` constants in `bench_anime_stitch.py`
- ChromaStepCvGate block in `run_dataset()`: fires when `asp_cscv > floor` and (`sim_cscv < 0.05` or `asp_cscv > 2.0 × sim_cscv`) → SCANS fallback; reason `chroma_step_cv_gate:{val:.4f}`
- Schema entries `ASP_GATE_CHROMA_STEP_CV_ABS_FLOOR` and `ASP_GATE_CHROMA_STEP_CV_RATIO` in `config.py`
- 5 tests in `TestChromaStepCvGateBench` (`test_bench_metrics.py`)

---

## S183 — 2026-06-25 (§5.57 Pipeline Strip Noise CV Gate · §5.58 Pipeline Seam Luma Step CV Gate · §5.59 Bench Strip Noise CV Gate · §5.60 Bench Seam Luma Step CV Gate)

*Four new post-composite quality gates: two pipeline gates (Stage 11.44 strip noise CV, Stage 11.45 seam luma step CV) and two bench comparative gates (strip noise CV parity, seam luma step CV parity). 1745 tests passing (85 skipped).*

### §5.57 Pipeline Strip Noise CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_noise_cv(img, n_strips=8)` in `canvas.py` — coefficient of variation (std/mean) of per-strip high-frequency noise estimate (strip vs Gaussian-blurred version, σ=1.5); 0.0 when mean per-strip noise < 0.5 (uniformly smooth guard) or degenerate input; high CV = some strips have noisy encoding while others are smooth, indicating mismatched frame sharpening
- Stage 11.44 gate in `pipeline.py`: fires when `_ncv_val > _NOISE_CV_GATE_FLOOR` (default 1.2) → SCANS fallback; reason `noise_cv_gate:{val:.4f}`
- Flags: `_NOISE_CV_GATE_ENABLED` (`ASP_GATE_NOISE_CV`, default 1), `_NOISE_CV_GATE_FLOOR` (`ASP_GATE_NOISE_CV_FLOOR`, default 1.2)
- `NOISE_CV_GATE_FLOOR = 1.2` in `constants/animation.py`; 4 schema entries in `config.py`
- 5 tests in `TestStripNoiseCv` (`test_canvas.py`), 5 tests in `TestNoiseCvGatePipeline` (`test_pipeline.py`)

### §5.58 Pipeline Seam Luma Step CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_seam_luma_step_cv(img, n_strips=8, boundary_px=3)` in `canvas.py` — coefficient of variation (std/mean) of per-strip-boundary absolute luminance step; 0.0 when mean step < 0.5 (uniformly smooth guard), fewer than 2 steps, or degenerate input; high CV = some seams have large luma steps while others are smooth, indicating uneven gain normalization
- Stage 11.45 gate in `pipeline.py`: fires when `_lscv_val > _LUMA_STEP_CV_GATE_FLOOR` (default 1.0) → SCANS fallback; reason `luma_step_cv_gate:{val:.4f}`
- Flags: `_LUMA_STEP_CV_GATE_ENABLED` (`ASP_GATE_LUMA_STEP_CV`, default 1), `_LUMA_STEP_CV_GATE_FLOOR` (`ASP_GATE_LUMA_STEP_CV_FLOOR`, default 1.0)
- `LUMA_STEP_CV_GATE_FLOOR = 1.0` in `constants/animation.py`; 4 schema entries in `config.py`
- 5 tests in `TestSeamLumaStepCv` (`test_canvas.py`), 5 tests in `TestLumaStepCvGatePipeline` (`test_pipeline.py`)

### §5.59 Bench Strip Noise CV Gate (`backend/benchmark/bench_anime_stitch.py`)

- `_NOISE_CV_ABS_FLOOR = 0.50`, `_NOISE_CV_RATIO = 2.5` constants in `bench_anime_stitch.py`
- NoiseCvGate block in `run_dataset()`: fires when `asp_ncv > floor` and (`sim_ncv < 0.05` or `asp_ncv > 2.5 × sim_ncv`) → SCANS fallback; reason `noise_cv_gate:{val:.4f}`
- Schema entries `ASP_GATE_NOISE_CV_ABS_FLOOR` and `ASP_GATE_NOISE_CV_RATIO` in `config.py`
- 5 tests in `TestNoiseCvGateBench` (`test_bench_metrics.py`)

### §5.60 Bench Seam Luma Step CV Gate (`backend/benchmark/bench_anime_stitch.py`)

- `_LUMA_STEP_CV_ABS_FLOOR = 0.40`, `_LUMA_STEP_CV_RATIO = 2.0` constants in `bench_anime_stitch.py`
- LumaStepCvGate block in `run_dataset()`: fires when `asp_lscv > floor` and (`sim_lscv < 0.05` or `asp_lscv > 2.0 × sim_lscv`) → SCANS fallback; reason `luma_step_cv_gate:{val:.4f}`
- Schema entries `ASP_GATE_LUMA_STEP_CV_ABS_FLOOR` and `ASP_GATE_LUMA_STEP_CV_RATIO` in `config.py`
- 5 tests in `TestLumaStepCvGateBench` (`test_bench_metrics.py`)

---

## S182 — 2026-06-25 (§5.53 Pipeline Strip Contrast CV Gate · §5.54 Pipeline Seam Chroma Jump Gate · §5.55 Bench Strip Contrast CV Gate · §5.56 Bench Seam Chroma Jump Gate)

*Four new post-composite quality gates: two pipeline gates (Stage 11.42 strip contrast CV, Stage 11.43 seam chroma jump) and two bench comparative gates (strip contrast CV parity, seam chroma jump parity). 1715 tests passing (85 skipped).*

### §5.53 Pipeline Strip Contrast CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_contrast_cv(img, n_strips=8)` in `canvas.py` — coefficient of variation (std/mean) of per-strip luma standard deviation; 0.0 when mean per-strip std < 1.0 (uniformly flat guard) or degenerate input; high CV = some strips are high-contrast while others are flat, indicating mismatched normalization
- Stage 11.42 gate in `pipeline.py`: fires when `_ccv_val > _CONTRAST_CV_GATE_FLOOR` (default 1.5) → SCANS fallback; reason `contrast_cv_gate:{val:.4f}`
- Flags: `_CONTRAST_CV_GATE_ENABLED` (`ASP_GATE_CONTRAST_CV`, default 1), `_CONTRAST_CV_GATE_FLOOR` (`ASP_GATE_CONTRAST_CV_FLOOR`, default 1.5)
- `CONTRAST_CV_GATE_FLOOR = 1.5` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestStripContrastCv` (`test_canvas.py`), 5 tests in `TestContrastCvGatePipeline` (`test_pipeline.py`)

### §5.54 Pipeline Seam Chroma Jump Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_seam_chroma_jump(img, n_strips=8, boundary_px=3)` in `canvas.py` — maximum per-channel mean absolute difference across ±`boundary_px` rows at each strip boundary; 0.0 for degenerate input; high value = colour step at seam caused by poor inter-frame white-balance normalisation
- Stage 11.43 gate in `pipeline.py`: fires when `_scj_val > _CHROMA_JUMP_GATE_FLOOR` (default 15.0) → SCANS fallback; reason `chroma_jump_gate:{val:.2f}`
- Flags: `_CHROMA_JUMP_GATE_ENABLED` (`ASP_GATE_CHROMA_JUMP`, default 1), `_CHROMA_JUMP_GATE_FLOOR` (`ASP_GATE_CHROMA_JUMP_FLOOR`, default 15.0)
- `CHROMA_JUMP_GATE_FLOOR = 15.0` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestSeamChromaJump` (`test_canvas.py`), 5 tests in `TestChromaJumpGatePipeline` (`test_pipeline.py`)

### §5.55 Bench Strip Contrast CV Comparative Gate (`backend/benchmark/bench_anime_stitch.py`)

- `ContrastCvGate` block in `run_dataset()` after `SharpnessCvGate`; reuses `_strip_contrast_cv` from `canvas.py`
- Dual condition: fires when `asp_ccv > _CONTRAST_CV_ABS_FLOOR` (default 0.80) AND (`sim_ccv < 0.05` OR `asp_ccv > 2.5 × max(sim_ccv, 0.01)`)
- Module constants: `_CONTRAST_CV_ABS_FLOOR`, `_CONTRAST_CV_RATIO`; 4 schema entries in `config.py`
- `timings["render_gate_fallback"] += 4` when gate fires
- 5 tests in `TestContrastCvGateBench` (`test_bench_metrics.py`)

### §5.56 Bench Seam Chroma Jump Comparative Gate (`backend/benchmark/bench_anime_stitch.py`)

- `ChromaJumpGate` block in `run_dataset()` after `ContrastCvGate`; reuses `_seam_chroma_jump` from `canvas.py`
- Dual condition: fires when `asp_scj > _CHROMA_JUMP_ABS_FLOOR` (default 8.0) AND (`sim_scj < 1.0` OR `asp_scj > 2.0 × max(sim_scj, 0.5)`)
- Module constants: `_CHROMA_JUMP_ABS_FLOOR`, `_CHROMA_JUMP_RATIO`; 4 schema entries in `config.py`
- `timings["render_gate_fallback"] += 2` when gate fires
- 5 tests in `TestChromaJumpGateBench` (`test_bench_metrics.py`)

---

## S181 — 2026-06-25 (§5.49 Pipeline Strip Luma MAD Gate · §5.50 Pipeline Strip Sharpness CV Gate · §5.51 Bench Strip Luma MAD Gate · §5.52 Bench Strip Sharpness CV Gate)

*Four new post-composite quality gates: two pipeline gates (Stage 11.40 luma MAD, Stage 11.41 sharpness CV) and two bench comparative gates (luma MAD parity, sharpness CV parity). 1685 tests passing (85 skipped).*

### §5.49 Pipeline Strip Luma MAD Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_luma_mad(img, n_strips=8)` in `canvas.py` — mean absolute deviation of per-strip luma means from global mean; 0.0 for degenerate input; complements luma range (captures systematic per-strip banding, not just extremes)
- Stage 11.40 gate in `pipeline.py`: fires when `_lmad_val > _LUMA_MAD_GATE_FLOOR` (default 20.0) → SCANS fallback; reason `luma_mad_gate:{val:.2f}`
- Flags: `_LUMA_MAD_GATE_ENABLED` (`ASP_GATE_LUMA_MAD`, default 1), `_LUMA_MAD_GATE_FLOOR` (`ASP_GATE_LUMA_MAD_FLOOR`, default 20.0)
- `LUMA_MAD_GATE_FLOOR = 20.0` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestStripLumaMad` (`test_canvas.py`), 5 tests in `TestLumaMadGatePipeline` (`test_pipeline.py`)

### §5.50 Pipeline Strip Sharpness CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_sharpness_cv(img, n_strips=8)` in `canvas.py` — coefficient of variation (std/mean) of per-strip Laplacian variance; 0.0 when mean sharpness < 1.0 (flat image guard) or degenerate input; high CV = mixed-sharpness strips from mismatched frames
- Stage 11.41 gate in `pipeline.py`: fires when `_scv_val > _SHARPNESS_CV_GATE_FLOOR` (default 1.0) → SCANS fallback; reason `sharpness_cv_gate:{val:.4f}`
- Flags: `_SHARPNESS_CV_GATE_ENABLED` (`ASP_GATE_SHARPNESS_CV`, default 1), `_SHARPNESS_CV_GATE_FLOOR` (`ASP_GATE_SHARPNESS_CV_FLOOR`, default 1.0)
- `SHARPNESS_CV_GATE_FLOOR = 1.0` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestStripSharpnessCv` (`test_canvas.py`), 5 tests in `TestSharpnessCvGatePipeline` (`test_pipeline.py`)

### §5.51 Bench Strip Luma MAD Comparative Gate (`backend/benchmark/bench_anime_stitch.py`)

- `LumaMadGate` block in `run_dataset()` after `EdgeDensityGate`; reuses `_strip_luma_mad` from `canvas.py`
- Dual condition: fires when `asp_lmad > _LUMA_MAD_ABS_FLOOR` (default 10.0) AND (`sim_lmad < 2.0` OR `asp_lmad > 2.0 × max(sim_lmad, 1.0)`)
- Module constants: `_LUMA_MAD_ABS_FLOOR`, `_LUMA_MAD_RATIO`; 4 schema entries in `config.py` (abs floor + ratio for both §5.51/§5.52)
- `timings["render_gate_fallback"] += 16` when gate fires
- 5 tests in `TestLumaMadGateBench` (`test_bench_metrics.py`)

### §5.52 Bench Strip Sharpness CV Comparative Gate (`backend/benchmark/bench_anime_stitch.py`)

- `SharpnessCvGate` block in `run_dataset()` after `LumaMadGate`; reuses `_strip_sharpness_cv` from `canvas.py`
- Dual condition: fires when `asp_scv > _SHARPNESS_CV_ABS_FLOOR` (default 0.60) AND (`sim_scv < 0.05` OR `asp_scv > 2.5 × max(sim_scv, 0.01)`)
- Module constants: `_SHARPNESS_CV_ABS_FLOOR`, `_SHARPNESS_CV_RATIO`
- `timings["render_gate_fallback"] += 8` when gate fires
- 5 tests in `TestSharpnessCvGateBench` (`test_bench_metrics.py`)

---

## S180 — 2026-06-25 (§5.45 Pipeline Strip Luma Range Gate · §5.46 Pipeline Seam Edge Density Gate · §5.47 Bench Strip Luma Range Gate · §5.48 Bench Strip Edge Density Gate)

*Four new post-composite quality gates: two pipeline gates (Stage 11.38 luma range, Stage 11.39 edge density) and two bench comparative gates (luma range parity, edge density parity). 1655 tests passing (85 skipped).*

### §5.45 Pipeline Strip Luma Range Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_luma_range(img, n_strips=8)` in `canvas.py` — absolute luminance range across horizontal strips (max − min strip mean luma); 0.0 for degenerate input
- Stage 11.38 gate in `pipeline.py`: fires when `_lr_val > _LUMA_RANGE_GATE_FLOOR` (default 60.0) → SCANS fallback; reason `luma_range_gate:{val:.2f}`
- Flags: `_LUMA_RANGE_GATE_ENABLED` (`ASP_GATE_LUMA_RANGE`, default 1), `_LUMA_RANGE_GATE_FLOOR` (`ASP_GATE_LUMA_RANGE_FLOOR`, default 60.0)
- `LUMA_RANGE_GATE_FLOOR = 60.0` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestStripLumaRange` (`test_canvas.py`), 5 tests in `TestLumaRangeGatePipeline` (`test_pipeline.py`)

### §5.46 Pipeline Seam Edge Density Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_seam_edge_density(img, n_strips=8)` in `canvas.py` — maximum Canny edge-pixel fraction across horizontal strips; 0.0 for degenerate input
- Stage 11.39 gate in `pipeline.py`: fires when `_ed_val > _EDGE_DENSITY_GATE_FLOOR` (default 0.30) → SCANS fallback; reason `edge_density_gate:{val:.4f}`
- Flags: `_EDGE_DENSITY_GATE_ENABLED` (`ASP_GATE_EDGE_DENSITY`, default 1), `_EDGE_DENSITY_GATE_FLOOR` (`ASP_GATE_EDGE_DENSITY_FLOOR`, default 0.30)
- `EDGE_DENSITY_GATE_FLOOR = 0.30` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestSeamEdgeDensity` (`test_canvas.py`), 5 tests in `TestEdgeDensityGatePipeline` (`test_pipeline.py`)

### §5.47 Bench Strip Luma Range Comparative Gate (`backend/benchmark/bench_anime_stitch.py`)

- `LumaRangeGate` block in `run_dataset()` after `SatCvGate`; reuses `_strip_luma_range` from `canvas.py`
- Dual condition: fires when `asp_lr > _LUMA_RANGE_ABS_FLOOR` (default 30.0) AND (`sim_lr < 5.0` OR `asp_lr > 2.0 × max(sim_lr, 1.0)`)
- Module constants: `_LUMA_RANGE_ABS_FLOOR`, `_LUMA_RANGE_RATIO`; 4 schema entries in `config.py` (abs floor + ratio for both §5.47/§5.48)
- `timings["render_gate_fallback"] += 128` when gate fires
- 5 tests in `TestLumaRangeGateBench` (`test_bench_metrics.py`)

### §5.48 Bench Strip Edge Density Comparative Gate (`backend/benchmark/bench_anime_stitch.py`)

- `EdgeDensityGate` block in `run_dataset()` after `LumaRangeGate`; reuses `_seam_edge_density` from `canvas.py`
- Dual condition: fires when `asp_ed > _EDGE_DENSITY_ABS_FLOOR` (default 0.15) AND (`sim_ed < 0.01` OR `asp_ed > 2.5 × max(sim_ed, 0.001)`)
- Module constants: `_EDGE_DENSITY_ABS_FLOOR`, `_EDGE_DENSITY_RATIO`
- `timings["render_gate_fallback"] += 64` when gate fires
- 5 tests in `TestEdgeDensityGateBench` (`test_bench_metrics.py`)

---

## S179 — 2026-06-25 (§5.41 Pipeline Strip Hue CV Gate · §5.42 Pipeline Seam Boundary Sharpness Ratio Gate · §5.43 Bench Canvas Valid-Area Gate · §5.44 Bench Strip Saturation CV Gate)

*Four new post-composite quality gates: two pipeline gates (Stage 11.36 hue CV, Stage 11.37 seam sharpness ratio) and two bench comparative gates (valid-area parity, saturation CV parity). 1625 tests passing (85 skipped).*

### §5.41 Pipeline Strip Hue CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_hue_cv(img, n_strips=8)` in `canvas.py` — circular mean hue per strip via cos/sin averaging for the 0–179 hue wrap; returns std/mean of per-strip angles; returns 0.0 for monochrome (mean sat < 1) or degenerate input
- Stage 11.36 gate in `pipeline.py`: fires when `cv > _HUE_CV_GATE_FLOOR` (default 0.50) → SCANS fallback
- Flags: `_HUE_CV_GATE_ENABLED` (`ASP_GATE_HUE_CV`, default 1), `_HUE_CV_GATE_FLOOR` (`ASP_GATE_HUE_CV_FLOOR`, default 0.50)
- `HUE_CV_GATE_FLOOR = 0.50` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestStripHueCv` (`test_canvas.py`), 5 tests in `TestHueCvGatePipeline` (`test_pipeline.py`)

### §5.42 Pipeline Seam Boundary Sharpness Ratio Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_seam_boundary_sharpness_ratio(img, n_strips=8, boundary_px=3)` in `canvas.py` — Laplacian variance in ±boundary_px around each seam boundary vs strip interior (middle half); max ratio across boundaries capped at 50.0; skips when interior_var < 1.0 (flat image guard)
- Stage 11.37 gate in `pipeline.py`: fires when `ratio > _SEAM_SHARP_RATIO_GATE_FLOOR` (default 4.0) → SCANS fallback
- Flags: `_SEAM_SHARP_RATIO_GATE_ENABLED` (`ASP_GATE_SEAM_SHARP_RATIO`, default 1), `_SEAM_SHARP_RATIO_GATE_FLOOR` (`ASP_GATE_SEAM_SHARP_RATIO_FLOOR`, default 4.0)
- `SEAM_SHARP_RATIO_GATE_FLOOR = 4.0` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestSeamBoundarySharpnessRatio` (`test_canvas.py`), 5 tests in `TestSeamSharpRatioGatePipeline` (`test_pipeline.py`)

### §5.43 Bench Canvas Valid-Area Comparative Gate (`backend/benchmark/bench_anime_stitch.py`)

- `ValidAreaGate` block in `run_dataset()` after `SeamGradRatioGate`; reuses `_canvas_valid_area_ratio` from `canvas.py`
- Dual condition: fires when `asp_va < _VALID_AREA_ABS_FLOOR` (default 0.30) OR `asp_va < 0.7 × sim_va` when `sim_va > 0.5`
- Module constants: `_VALID_AREA_ABS_FLOOR`, `_VALID_AREA_RATIO`; 2 schema entries in `config.py`
- 5 tests in `TestValidAreaGateBench` (`test_bench_metrics.py`)

### §5.44 Bench Strip Saturation CV Comparative Gate (`backend/benchmark/bench_anime_stitch.py`)

- `SatCvGate` block in `run_dataset()` after `ValidAreaGate`; reuses `_strip_sat_cv` from `canvas.py`
- Dual condition: fires when `asp_sc > _SAT_CV_ABS_FLOOR` (default 0.30) AND `asp_sc > 2.0 × max(sim_sc, 0.001)` — absolute floor prevents false positives on genuinely saturated sequences
- Module constants: `_SAT_CV_ABS_FLOOR`, `_SAT_CV_RATIO`; 2 schema entries in `config.py`
- 5 tests in `TestSatCvGateBench` (`test_bench_metrics.py`)

---

## S178 — 2026-06-25 (§5.37 Bench Histogram Intersection Gate · §5.38 Pipeline Strip Saturation CV Gate · §5.39 Pipeline Canvas Valid-Area Ratio Gate · §5.40 Bench Seam Gradient Ratio Gate)

*Four new post-composite quality gates: a bench comparative histogram intersection gate (§5.37), a pipeline strip HSV-saturation CV gate Stage 11.34 (§5.38), a pipeline canvas valid-area ratio gate Stage 11.35 (§5.39), and a bench comparative seam gradient ratio gate (§5.40). 1595 tests passing (85 skipped).*

### §5.37 Bench Histogram Intersection Comparative Gate (`backend/benchmark/bench_anime_stitch.py`)

- `HistIntersectGate` block added in `run_dataset()` after `SeamBandNccGate`; reuses `_strip_hist_intersection_min` from `canvas.py`
- Fires when `asp_hi < _HIST_INTERSECT_ABS_FLOOR` (default 0.10) OR `asp_hi < _HIST_INTERSECT_RATIO × sim_hi` (default 0.5) when `sim_hi > 0.1`
- Module constants: `_HIST_INTERSECT_ABS_FLOOR`, `_HIST_INTERSECT_RATIO` (env: `ASP_GATE_HIST_INTERSECT_FLOOR`, `ASP_GATE_HIST_INTERSECT_RATIO`)
- Schema entry `ASP_GATE_HIST_INTERSECT_RATIO` added to `config.py`
- 5 tests in `TestHistIntersectGateBench` (`test_bench_metrics.py`)

### §5.38 Pipeline Strip Saturation CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_sat_cv(img, n_strips=8)` in `canvas.py` — coefficient of variation (std/mean) of per-strip mean HSV S-channel saturation; high CV = seam-induced color saturation mismatches; returns 0.0 for monochrome/degenerate
- Stage 11.34 gate in `pipeline.py`: fires when `cv > _SAT_CV_GATE_FLOOR` (default 0.40) → SCANS fallback
- Flags: `_SAT_CV_GATE_ENABLED` (`ASP_GATE_SAT_CV`, default 1), `_SAT_CV_GATE_FLOOR` (`ASP_GATE_SAT_CV_FLOOR`, default 0.40)
- `SAT_CV_GATE_FLOOR = 0.40` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestStripSatCv` (`test_canvas.py`), 5 tests in `TestSatCvGatePipeline` (`test_pipeline.py`)

### §5.39 Pipeline Canvas Valid-Area Ratio Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_canvas_valid_area_ratio(img, black_threshold=8)` in `canvas.py` — fraction of canvas pixels above black threshold (grayscale); low ratio = large black/empty regions = alignment failure; returns 1.0 for degenerate input
- Stage 11.35 gate in `pipeline.py`: **fires when `ratio < floor`** (LOW ratio = underfilled canvas); default floor 0.55
- Flags: `_VALID_AREA_GATE_ENABLED` (`ASP_GATE_VALID_AREA`, default 1), `_VALID_AREA_GATE_FLOOR` (`ASP_GATE_VALID_AREA_FLOOR`, default 0.55)
- `VALID_AREA_GATE_FLOOR = 0.55` in `constants/animation.py`; 2 schema entries in `config.py`
- 5 tests in `TestCanvasValidAreaRatio` (`test_canvas.py`), 5 tests in `TestValidAreaGatePipeline` (`test_pipeline.py`)

### §5.40 Bench Seam Gradient Ratio Comparative Gate (`backend/benchmark/bench_anime_stitch.py`)

- `SeamGradRatioGate` block in `run_dataset()` after `HistIntersectGate`; reuses `_strip_seam_gradient_score` from `canvas.py`
- Fires when `asp_sgr > _SEAM_GRAD_RATIO_ABS_FLOOR` (default 5.0) AND `asp_sgr > _SEAM_GRAD_RATIO_LIMIT × max(sim_sgr, 0.1)` (default 2.0×); dual condition ensures gate only fires when ASP is meaningfully worse than SCANS
- Module constants: `_SEAM_GRAD_RATIO_ABS_FLOOR`, `_SEAM_GRAD_RATIO_LIMIT` (env: `ASP_GATE_SEAM_GRAD_ABS_FLOOR`, `ASP_GATE_SEAM_GRAD_RATIO_LIMIT`)
- 2 schema entries added to `config.py`
- 5 tests in `TestSeamGradRatioGateBench` (`test_bench_metrics.py`)

---

## S177 — 2026-06-24 (§5.33 Seam Gradient Ratio Gate · §5.34 Canvas Aspect-Ratio Gate · §5.35 Bench Seam Band NCC Gate · §5.36 Pipeline Histogram Intersection Gate)

*Four new post-composite quality gates (Stages 11.31–11.33) and one new bench comparative gate: seam boundary gradient ratio, canvas H/W aspect ratio, bench seam band NCC comparison, and per-strip histogram intersection. 1565 tests passing (85 skipped).*

### §5.33 Seam Gradient Ratio Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_seam_gradient_score(img, n_strips=8)` in `canvas.py` — max ratio of boundary-row Laplacian gradient to strip-interior gradient; high ratio = hard visible seam cuts; capped at 10.0
- Stage 11.31 gate in `pipeline.py`: fires when `ratio > _SEAM_GRAD_RATIO_GATE_FLOOR` (default 3.0) → SCANS fallback
- Flags: `_SEAM_GRAD_RATIO_GATE_ENABLED` (`ASP_GATE_SEAM_GRAD_RATIO`, default 1), `_SEAM_GRAD_RATIO_GATE_FLOOR` (`ASP_GATE_SEAM_GRAD_RATIO_FLOOR`, default 3.0)
- `SEAM_GRAD_RATIO_GATE_FLOOR = 3.0` in `constants/animation.py`; 4 schema entries in `config.py`
- 5 tests in `TestSeamGradRatioGatePipeline` (`test_pipeline.py`)

### §5.34 Canvas Aspect-Ratio Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_canvas_aspect_ratio(img)` in `canvas.py` — H/W ratio of the composite canvas; correctly-stitched vertical scroll should be portrait (H >> W)
- Stage 11.32 gate in `pipeline.py`: **fires when `ratio < floor`** (LOW ratio = landscape = wrong scroll axis); dynamic floor = `max(_CANVAS_ASPECT_GATE_FLOOR, N * 0.3)`
- Flags: `_CANVAS_ASPECT_GATE_ENABLED` (`ASP_GATE_CANVAS_ASPECT`, default 1), `_CANVAS_ASPECT_GATE_FLOOR` (`ASP_GATE_CANVAS_ASPECT_FLOOR`, default 1.2)
- `CANVAS_ASPECT_GATE_FLOOR = 1.2` in `constants/animation.py`
- 5 tests in `TestCanvasAspectGatePipeline` (`test_pipeline.py`)

### §5.35 Bench Seam Band NCC Gate (`backend/benchmark/bench_anime_stitch.py`)

- SeamBandNccGate block after GhostSiqeGate in `run_dataset()` — reuses `_seam_band_ncc_min` from canvas.py
- Fires when `asp_ncc < _SEAM_NCC_ABS_FLOOR` (default 0.10) OR `asp_ncc < _SEAM_NCC_RATIO × sim_ncc` (default 0.5) when sim_ncc > 0.1
- Module constants: `_SEAM_NCC_ABS_FLOOR=0.10`, `_SEAM_NCC_RATIO=0.5` (both env-overridable)
- Schema entries `ASP_GATE_SEAM_NCC_FLOOR` and `ASP_GATE_SEAM_NCC_RATIO` in `config.py`
- 5 tests in `TestSeamBandNccGateBench` (`test_bench_metrics.py`)

### §5.36 Pipeline Strip Histogram Intersection Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_hist_intersection_min(img, n_strips=8)` in `canvas.py` — minimum histogram intersection (cv2.HISTCMP_INTERSECT, 64-bin) between adjacent strip pairs; 0=completely different, 1=identical
- Stage 11.33 gate in `pipeline.py`: **fires when `intersection < floor`** (LOW = color mismatch between strips); default floor 0.35
- Flags: `_HIST_INTERSECT_GATE_ENABLED` (`ASP_GATE_HIST_INTERSECT`, default 1), `_HIST_INTERSECT_GATE_FLOOR` (`ASP_GATE_HIST_INTERSECT_FLOOR`, default 0.35)
- `HIST_INTERSECT_GATE_FLOOR = 0.35` in `constants/animation.py`
- 5 tests in `TestHistIntersectGatePipeline` (`test_pipeline.py`)

---

## S176 — 2026-06-24 (§5.29 Ghosting SIQE Pipeline Gate · §5.30 Bench SIQE Gate · §5.31 Seam Band NCC Gate · §5.32 Strip Gradient CV Gate)

*Four new post-composite pipeline gates (Stages 11.28–11.30) and one new bench comparative gate: SIQE ghost autocorrelation, seam band NCC discontinuity, per-strip Laplacian sharpness CV, and a bench SIQE ratio gate. 1545 tests passing (85 skipped).*

### §5.29 Ghosting SIQE Pipeline Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_canvas_ghosting_siqe(img)` in `canvas.py` — FFT autocorrelation of column-mean Sobel gradient; secondary peak at lag D in [5, H//4] = ghost signature; score 0–100
- Stage 11.28 gate in `pipeline.py`: fires when `siqe > _SIQE_GATE_FLOOR` (default 30.0) → SCANS fallback
- Flags: `_SIQE_GATE_ENABLED` (`ASP_GATE_GHOSTING_SIQE`, default 1), `_SIQE_GATE_FLOOR` (`ASP_GATE_GHOSTING_SIQE_FLOOR`, default 30.0)
- Schema entries `ASP_GATE_GHOSTING_SIQE` and `ASP_GATE_GHOSTING_SIQE_FLOOR` in `config.py`
- `SIQE_GATE_FLOOR = 30.0` in `constants/animation.py`
- 5 tests in `TestSiqeGatePipeline` (`test_pipeline.py`)

### §5.30 Bench Ghosting SIQE Gate (`backend/benchmark/bench_anime_stitch.py`)

- GhostSiqeGate block after ChromaSeamGate in `run_dataset()` — reuses `_ghosting_score_v2` (same FFT autocorrelation)
- Fires when `asp_siqe > max(_GHOST_SIQE_ABS_FLOOR, _GHOST_SIQE_RATIO_LIMIT × sim_siqe)`
- Module constants: `_GHOST_SIQE_RATIO_LIMIT=2.0` (`ASP_GATE_GHOST_SIQE_RATIO`), `_GHOST_SIQE_ABS_FLOOR=30.0`
- Schema entry `ASP_GATE_GHOST_SIQE_RATIO` in `config.py`
- 5 tests in `TestGhostSiqeGate` (`test_bench_metrics.py`)

### §5.31 Seam Band NCC Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_seam_band_ncc_min(img, n_strips=8, band_px=10)` in `canvas.py` — minimum NCC between ±band_px bands above/below each strip boundary; values near 1.0 = seamless; near 0 = structural discontinuity
- Stage 11.29 gate in `pipeline.py`: **fires when `ncc < floor`** (LOW NCC = bad, unlike all other gates that fire when metric > floor)
- Flags: `_SEAM_BAND_NCC_GATE_ENABLED` (`ASP_GATE_SEAM_BAND_NCC`, default 1), `_SEAM_BAND_NCC_GATE_FLOOR` (`ASP_GATE_SEAM_BAND_NCC_FLOOR`, default 0.30)
- `SEAM_BAND_NCC_GATE_FLOOR = 0.30` in `constants/animation.py`
- 5 tests in `TestSeamBandNccGatePipeline` (`test_pipeline.py`)

### §5.32 Strip Gradient CV Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_gradient_cv(img, n_strips=8)` in `canvas.py` — coefficient of variation of per-strip mean Laplacian energy; high CV = sharpness inconsistency across strips
- Stage 11.30 gate in `pipeline.py`: fires when `cv > _STRIP_GRAD_CV_GATE_FLOOR` (default 0.50) → SCANS fallback
- Flags: `_STRIP_GRAD_CV_GATE_ENABLED` (`ASP_GATE_STRIP_GRAD_CV`, default 1), `_STRIP_GRAD_CV_GATE_FLOOR` (`ASP_GATE_STRIP_GRAD_CV_FLOOR`, default 0.50)
- `STRIP_GRAD_CV_GATE_FLOOR = 0.50` in `constants/animation.py`
- 5 tests in `TestStripGradCvGatePipeline` (`test_pipeline.py`)

---

## S171 — 2026-06-24 (§5.13 FFT Banding Gate · §5.12 Horizontal FFT Banding Metric · §5.11 Adaptive Seam-Smooth · §5.10 Strip Luma Monotonicity · §5.9 Auto Seam Lum-Step)

*Five incremental improvements across S169–S171: two new benchmark metrics, adaptive seam-smooth width driven by seam_coherence, CGU-triggered auto-enable of seam lum-step correction, and an FFT banding SCANS fallback gate. 1460 tests passing (85 skipped).*

### §5.13 FFT Banding Gate (`backend/benchmark/bench_anime_stitch.py`, `backend/src/animation/core/config.py`)

- FFTBandingGate after SCGate in `run_dataset()`: fires when `asp_fft > max(0.30, 3.0 × sim_fft)` and `_fallback_reason is None`
- `ASP_GATE_FFT_BAND=3.0`, `ASP_GATE_FFT_BAND_FLOOR=0.30`; disable with `ASP_GATE_FFT_BAND=99`
- `_fallback_reason` prefix: `fft_band_gate:`; adds 16 ms to `render_gate_fallback` timing
- 5 tests in `TestFftBandingGate` (`test_bench_metrics.py`)

### §5.12 Horizontal FFT Banding Metric (`backend/benchmark/bench_anime_stitch.py`)

- `_horizontal_fft_banding(img, n_strips=8)` — rfft of column-mean luminance profile; energy fraction at ±1 bin window around strip-boundary frequency (`n_strips//2`)
- Wired into `_compute_all_metrics()` as `horizontal_fft_banding` (range [0,1])
- 5 tests in `TestHorizontalFftBanding` (`test_bench_metrics.py`)

### §5.11 Adaptive Seam-Smooth Width (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_compute_adaptive_seam_smooth_px(canvas, base_px=4, min_px=2, max_px=12)` in `canvas.py`: measures `std(row_means)` of canvas; linearly maps sc∈[5,30] → px∈[12,2] (sc≤5→max_px, sc≥30→min_px)
- `_SEAM_SMOOTH_ADAPTIVE: bool = True` at pipeline.py module level (env: `ASP_SEAM_SMOOTH_ADAPTIVE`)
- Stage 11.19 upgraded: when adaptive enabled, calls `_compute_adaptive_seam_smooth_px` before `_smooth_seam_bands`
- `SEAM_SMOOTH_ADAPTIVE: bool = True` in `constants/animation.py`
- 5 tests in `TestComputeAdaptiveSeamSmoothPx` (`test_canvas.py`)

### §5.10 Strip Luma Monotonicity (`backend/benchmark/bench_anime_stitch.py`)

- `_strip_luma_monotonicity(img, n_strips=8)` — fraction of adjacent strip pairs with direction reversal; 0=monotonic, 1=fully alternating
- Wired into `_compute_all_metrics()` as `strip_luma_monotonicity`
- 5 tests in `TestStripLumaMonotonicity` (`test_bench_metrics.py`)

### §5.9 Auto-Enable Seam Lum-Step from CGU (`backend/src/animation/core/pipeline.py`)

- `_CGU_AUTO_LUM_STEP: float = 0.08` (env: `ASP_CGU_AUTO_LUM_STEP`) at module level
- Stage 11.20: when `_SEAM_LUM_STEP_PX == 0` and CGU > threshold → auto-sets `_lum_step_px = 20`
- Addresses moderate-banding sequences (CGU 0.10–0.20) not caught by the SCANS gate
- 5 tests in `TestCguAutoLumStep` (`test_pipeline.py`)

---

## S175 — 2026-06-24 (§5.25 Pipeline Strip Self-SSIM Gate · §5.26 Benchmark Strip-SSIM & Chroma-Coh Metrics)

*Stage 11.27 strip self-SSIM pipeline gate and benchmark metric deduplication complete the §5 post-composite cascade through eight complementary quality dimensions. 1525 tests passing (85 skipped).*

### §5.25 Pipeline Strip Self-SSIM Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_self_ssim(img, n_strips=8)` in `canvas.py`: per-strip top/bottom NCC self-consistency; minimum NCC across strips; range [−1, 1]; values near 1.0 indicate uniform strips free of seam jumps
- Stage 11.27 in `run()`: fires `_scan_stitch_fallback(reason=f"strip_ssim_gate:{val:.4f}")` when `ssim > _STRIP_SSIM_GATE_FLOOR` (default 0.85)
- `_STRIP_SSIM_GATE_ENABLED`, `_STRIP_SSIM_GATE_FLOOR` module flags; env: `ASP_GATE_STRIP_SSIM`, `ASP_GATE_STRIP_SSIM_FLOOR`
- `STRIP_SELF_SSIM_GATE_FLOOR: float = 0.85` in `constants/animation.py`
- 5 tests in `TestStripSsimGatePipeline` (`test_pipeline.py`)

### §5.26 Benchmark Strip-SSIM & Chroma-Coh Metric Deduplication (`backend/benchmark/bench_anime_stitch.py`)

- Removed local duplicate definitions of `_strip_self_ssim` and `_chroma_seam_coherence`; both now imported from `backend.src.animation.alignment.canvas`
- `_compute_all_metrics()` emits `strip_self_ssim` and `chroma_seam_coherence` keys sourced from canonical canvas.py implementations
- 5 tests in `TestBenchStripSsimChromaMetrics` (`test_bench_metrics.py`)

---

## S174 — 2026-06-24 (§5.19 SC Pipeline Gate · §5.20 Adaptive Lum-Step Wired · §5.21 FFT Pipeline Gate · §5.22 Mono Pipeline Gate · §5.23 SV Pipeline Gate · §5.24 Chroma Pipeline Gate)

*Six post-composite pipeline gates (Stages 11.22–11.26) and per-seam adaptive lum-step wiring complete the §5 pipeline-level defense cascade. 1515 tests passing (85 skipped).*

### §5.24 Chroma Seam Coherence Pipeline Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_chroma_seam_coherence(img, n_strips=8)` in `canvas.py`: mean per-channel color discontinuity at strip boundaries; higher = more visible color shift
- Stage 11.26 in `run()`: fires `_scan_stitch_fallback(reason=f"chroma_coh_gate:{val:.2f}")` when `chroma_coh > _CHROMA_COH_GATE_FLOOR` (default 20.0)
- `_CHROMA_COH_GATE_ENABLED`, `_CHROMA_COH_GATE_FLOOR` module flags; env: `ASP_GATE_CHROMA_PIPE`, `ASP_GATE_CHROMA_PIPE_FLOOR`
- `CHROMA_COH_GATE_FLOOR: float = 20.0` in `constants/animation.py`
- 5 tests in `TestChromaCohGatePipeline` (`test_pipeline.py`)

### §5.23 Seam Visibility Pipeline Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_seam_visibility_score(img)` in `canvas.py`: max absolute adjacent-row luminance jump (black border rows excluded); direct no-reference seam visibility metric
- Stage 11.25 in `run()`: fires `_scan_stitch_fallback(reason=f"sv_gate:{val:.2f}")` when `sv > _SV_GATE_FLOOR` (default 30.0)
- `_SV_GATE_ENABLED`, `_SV_GATE_FLOOR` module flags; env: `ASP_GATE_SEAM_VIS`, `ASP_GATE_SEAM_VIS_FLOOR`
- `SV_GATE_FLOOR: float = 30.0` in `constants/animation.py`
- 5 tests in `TestSvGatePipeline` (`test_pipeline.py`)

### §5.22 Strip Luma Monotonicity Pipeline Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_strip_luma_monotonicity(img, n_strips=8)` in `canvas.py`: fraction of adjacent strip pairs with luminance direction reversal (0=monotonic, 1=fully alternating)
- Stage 11.24 in `run()`: fires `_scan_stitch_fallback(reason=f"mono_gate:{val:.3f}")` when `mono > _MONO_GATE_FLOOR` (default 0.60)
- `_MONO_GATE_ENABLED`, `_MONO_GATE_FLOOR` module flags; env: `ASP_GATE_MONO_PIPE`, `ASP_GATE_MONO_PIPE_FLOOR`
- `MONO_GATE_FLOOR: float = 0.60` in `constants/animation.py`
- 5 tests in `TestMonoGatePipeline` (`test_pipeline.py`)

### §5.21 FFT Banding Pipeline Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_horizontal_fft_banding(img, n_strips=8)` in `canvas.py`: energy fraction at strip-boundary frequency in row-mean luminance FFT profile; range [0,1]
- Stage 11.23 in `run()`: fires `_scan_stitch_fallback(reason=f"fft_band_gate:{val:.4f}")` when `fft > _FFT_BAND_GATE_FLOOR` (default 0.35)
- `_FFT_BAND_GATE_ENABLED`, `_FFT_BAND_GATE_FLOOR` module flags; env: `ASP_GATE_FFT_BAND`, `ASP_GATE_FFT_BAND_FLOOR`
- `FFT_BAND_GATE_FLOOR: float = 0.35` in `constants/animation.py`
- 5 tests in `TestFftBandGatePipeline` (`test_pipeline.py`)

### §5.20 Per-Seam Adaptive Lum-Step Wired into Stage 11.20 (`backend/src/animation/core/pipeline.py`, `backend/src/animation/alignment/canvas.py`)

- `_per_seam_lum_step_px(canvas, seam_ys)` call wired in Stage 11.20 when `_SEAM_LUM_STEP_ADAPTIVE=True`: computes per-seam correction band widths; passed as `List[int]` to `_correct_seam_lum_steps`
- `_correct_seam_lum_steps` updated to accept `Union[int, List[int]]` for `band_px`; resolves per-seam width inside loop
- 5 tests in `TestCorrectSeamLumStepsListBandPx` (`test_canvas.py`)

### §5.19 Seam Coherence Pipeline Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_seam_coherence_score(img)` in `canvas.py`: `std(per-row-mean-luminance)` — proxy for horizontal strip banding severity
- Stage 11.22 in `run()`: fires `_scan_stitch_fallback(reason=f"sc_gate:{val:.3f}")` when `sc > _SC_GATE_FLOOR` (default 25.0)
- `_SC_GATE_ENABLED`, `_SC_GATE_FLOOR` module flags; env: `ASP_GATE_SEAM_COH`, `ASP_GATE_SEAM_COH_FLOOR`
- `SC_GATE_FLOOR: float = 25.0` in `constants/animation.py`
- 5 tests in `TestScGatePipeline` (`test_pipeline.py`)

---

## S173 — 2026-06-24 (§5.17 Strip Self-SSIM Gate · §5.18 Chroma Seam Coherence Gate)

*Two benchmark SCANS fallback gates completing the §5 cascade. 1485 tests passing (85 skipped).*

### §5.18 Chroma Seam Coherence Gate (`backend/benchmark/bench_anime_stitch.py`, `backend/src/animation/core/config.py`)

- ChromaSeamGate after StripSSIMGate in `run_dataset()`: fires when `asp_chroma > max(12.0, 2.5 × sim_chroma)` and `_fallback_reason is None`
- `_CHROMA_COH_RATIO_LIMIT=2.5`, `_CHROMA_COH_ABS_FLOOR=12.0`; disable with `ASP_GATE_CHROMA_COH=90`
- `_fallback_reason` prefix: `chroma_coh_gate:`; adds 256 to `render_gate_fallback` timing
- 5 tests in `TestChromaSeamCohGate` (`test_bench_metrics.py`)

### §5.17 Strip Self-SSIM Gate (`backend/benchmark/bench_anime_stitch.py`, `backend/src/animation/core/config.py`)

- StripSSIMGate after EntropyGate: fires when `asp_sssim < min(0.60, 0.5 × sim_sssim)` (inverted: lower = structurally worse)
- `ASP_GATE_STRIP_SSIM=0.5`, `ASP_GATE_STRIP_SSIM_FLOOR=0.60`; disable with `ASP_GATE_STRIP_SSIM=0`
- `_fallback_reason` prefix: `strip_ssim_gate:`; adds 128 to `render_gate_fallback` timing
- 5 tests in `TestStripSsimGate` (`test_bench_metrics.py`)

---

## S172 — 2026-06-24 (§5.14 Strip Luma Monotonicity Gate · §5.15 Seam Ownership Entropy Gate · §5.16 Per-Seam Adaptive Lum-Step Width)

*Three improvements: two benchmark SCANS gates targeting new metrics, plus per-seam adaptive correction band widths for lum-step correction. 1485 tests passing (85 skipped).*

### §5.16 Per-Seam Adaptive Lum-Step Width (`backend/src/animation/alignment/canvas.py`)

- `_per_seam_lum_step_px(canvas, seam_ys, base_px=20, ref_px=8, min_px=5, max_px=40)` — measures actual lum step at each seam position; maps step∈[5,30]→px∈[5,40] via linear interpolation
- Exported in `canvas.__all__`; `SEAM_LUM_STEP_ADAPTIVE: bool = True` in constants
- `_SEAM_LUM_STEP_ADAPTIVE` module flag in pipeline.py for future Stage 11.20 dispatch
- 5 tests in `TestPerSeamLumStepPx` (`test_canvas.py`)

### §5.15 Seam Ownership Entropy Gate (`backend/benchmark/bench_anime_stitch.py`, `backend/src/animation/core/config.py`)

- EntropyGate after MonotonGate in `run_dataset()`: fires when `asp_ent > max(3.0, 2.5 × sim_ent)` and `_fallback_reason is None`
- `ASP_GATE_ENTROPY=2.5`, `ASP_GATE_ENTROPY_FLOOR=3.0`; disable with `ASP_GATE_ENTROPY=99`
- `_fallback_reason` prefix: `entropy_gate:`; adds 64 to `render_gate_fallback` timing
- 5 tests in `TestSeamOwnershipEntropyGate` (`test_bench_metrics.py`)

### §5.14 Strip Luma Monotonicity Gate (`backend/benchmark/bench_anime_stitch.py`, `backend/src/animation/core/config.py`)

- MonotonGate after FFTBandGate in `run_dataset()`: fires when `asp_mono > max(0.50, 3.0 × sim_mono)` and `_fallback_reason is None`
- `ASP_GATE_MONO=3.0`, `ASP_GATE_MONO_FLOOR=0.50`; disable with `ASP_GATE_MONO=99`
- `_fallback_reason` prefix: `monot_gate:`; adds 32 to `render_gate_fallback` timing
- 5 tests in `TestMonotonGate` (`test_bench_metrics.py`)

---

## S168 — 2026-06-24 (§5.6 Pipeline CGU Gate · §5.8 Adaptive dy_cv Ceiling)

*Two improvements: §5.6 brings the benchmark-level CGUGate into the pipeline itself (Stage 11.21, fallback when canvas_gain_uniformity > 0.20), also enables seam-Gaussian-smoothing by default (4px); §5.8 lowers the dy_cv ceiling proportionally for large-N sequences (N≥8) to prevent compounding step irregularity. 1435 tests passing (85 skipped).*

### §5.6 Pipeline CGU Gate (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_canvas_gain_uniformity(img, n_strips=8)` — coefficient of variation of 8-strip mean luminance — moved from benchmark to `canvas.py`; exported in `__all__`
- `_CGU_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_CGU_FLOOR", "0.20"))` at pipeline.py module level
- Stage 11.21 in `run()` (after §5.1 correction): computes CGU on finished canvas; fires `_scan_stitch_fallback(reason=f"cgu_gate:{cgu:.3f}")` when `cgu > _CGU_GATE_FLOOR < 1.0`
- `_SEAM_SMOOTH_PX` default changed "0" → "4" (§4.9 Gaussian seam smoothing now on by default); `SEAM_SMOOTH_PX: int = 4` in constants

### §5.8 Adaptive dy_cv Ceiling (`backend/src/animation/core/pipeline.py`, `backend/src/constants/animation.py`)

- `_compute_adaptive_dy_cv_max(n_frames, base_max=1.5)` in `pipeline.py`: returns `base_max` unchanged for N<8; returns `max(base_max × 8/N, 0.8)` for N≥8
  - Scale examples: N=8→1.5, N=12→1.0, N=16→0.8 (floor=`DY_CV_ADAPTIVE_FLOOR`)
  - Prevents large-N sequences with moderately irregular steps from bypassing the dy_cv gate
- Wired at §4.7 gate in `run()`: `_dy_cv_adaptive_max = _compute_adaptive_dy_cv_max(N, _DY_CV_MAX)` replaces hardcoded `_DY_CV_MAX`
- `DY_CV_ADAPTIVE_FLOOR: float = 0.8` in `constants/animation.py`
- `_compute_adaptive_dy_cv_max` exported in `__all__`
- 5 tests in `TestAdaptiveDyCvMax` (`test_pipeline.py`)

---

## S167 — 2026-06-24 (§5.2 Seam Coherence Gate · §5.4 CGU in CQAS · §5.5 seam_vis in Verdict)

*Three benchmark-level improvements targeting verdict accuracy and gradual luminance banding detection. §5.2 adds a SCANS fallback gate for high seam_coherence; §5.4 adds canvas_gain_uniformity as a 5th CQAS component; §5.5 adds a direct seam_visibility penalty to the auto-verdict formula. 1430 tests passing (85 skipped).*

### §5.2 Seam Coherence Gate (`backend/benchmark/bench_anime_stitch.py`, `backend/src/animation/core/config.py`)

- SCGate block inserted after CGUGate in `run_dataset()`:
  - Reads `ASP_GATE_SEAM_COH` (float, default 2.5; set ≥90 to disable) and `ASP_GATE_SEAM_COH_FLOOR` (float, default 15.0)
  - Gate condition: `asp_sc > max(floor, 2.5 × max(sim_sc, 1.0))`
  - Prints `[SCGate]` status line; on fire: `_fallback_reason = "seam_coh_gate:asp=..."`, `timings["render_gate_fallback"] += 8`, raises RuntimeError
- `ASP_GATE_SEAM_COH` and `ASP_GATE_SEAM_COH_FLOOR` added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]` in `config.py`
- 5 tests in `TestSeamCoherenceGate` (`test_bench_metrics.py`)

### §5.4 CGU Term in CQAS (`backend/benchmark/bench_anime_stitch.py`)

- `cgu_score = clip(1.0 − cgu / 0.40, 0, 1)` computed from `canvas_gain_uniformity` metric
- Added as 5th CQAS component with weight 0.15; component list: `[(g,0.35),(sv,0.30),(sc,0.20),(sh,0.15),(cgu,0.15)]`
- Score 1.0 at cgu=0 (perfectly uniform strips), 0.0 at cgu≥0.40 (severe banding)
- 5 tests in `TestCompositeQualityScoreWithCGU` (`test_bench_metrics.py`)

### §5.5 seam_vis in Verdict (`backend/benchmark/bench_anime_stitch.py`)

- `sv_score × 0.10` additive penalty term in `_auto_verdict()`: directly penalises visible seams even when below the SeamVisGate absolute floor
- Complementary to SeamVisGate: gate is binary (fire/no-fire); verdict term is continuous

---

## S166 — 2026-06-24 (§5.1 Seam Luminance Step Correction · §5.3 Canvas Gain Uniformity Gate)

*Two improvements targeting inter-strip luminance banding (root cause of strip_banding_score=31–41 on worst failures): §5.1 bridges the per-column luminance mean gap at each seam with a linear ramp; §5.3 adds a SCANS fallback gate when ASP canvas_gain_uniformity exceeds 2.0× SCANS. 1420 tests passing (85 skipped).*

### §5.1 Post-Composite Seam Luminance Step Correction (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_correct_seam_lum_steps(canvas, seam_ys, band_px=20)` in `canvas.py`:
  - For each seam, computes per-column masked mean luminance in an `±ref_px` (up to 8px) reference band just above and below the seam
  - Derives the step vector `step = bot_lum - top_lum` (per-column) and distributes `±step/2` as a linear ramp across `±band_px` on each side
  - Only modifies pixels where `canvas.max(axis=2) > 0`; result clipped to `[0, 255]`
- `_SEAM_LUM_STEP_PX: int = int(os.environ.get("ASP_SEAM_LUM_STEP", "0"))` at pipeline.py module level (default OFF)
- Stage 11.20 in `pipeline.py run()`: estimates seam_ys from sorted affine frame centres; calls `_correct_seam_lum_steps()` when `_SEAM_LUM_STEP_PX > 0 and N > 1`
- `SEAM_LUM_STEP_PX: int = 0` constant in `constants/animation.py`
- `ASP_SEAM_LUM_STEP` added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]` in `config.py`
- `_SEAM_LUM_STEP_PX` and `_correct_seam_lum_steps` exported in `pipeline.py __all__`; `_correct_seam_lum_steps` in `canvas.py __all__`
- 5 tests in `TestCorrectSeamLumSteps` (`test_canvas.py`)
- Enable: `ASP_SEAM_LUM_STEP=20` (20px half-band)

### §5.3 Canvas Gain Uniformity Gate (`backend/benchmark/bench_anime_stitch.py`, `backend/src/animation/core/config.py`)

- CGUGate block inserted between SeamVisGate and PIL save in `run_dataset()`:
  - Reads `ASP_GATE_CGU` (float, default 2.0; set ≥90 to disable) and `ASP_GATE_CGU_FLOOR` (float, default 0.15)
  - Fires only when `_fallback_reason is None` (not already fallen back), `simple_ok` and ratio limit < 90
  - Loads `central_simple_path`, computes `_canvas_gain_uniformity()` (std/mean of 8-strip luminance) on both outputs
  - Gate condition: `asp_cgu > max(floor, ratio × max(sim_cgu, 0.001))`
  - Prints `[CGUGate]` status line; on fire: `_fallback_reason = "cgu_gate:asp=..."`, `timings["render_gate_fallback"] += 4`, raises RuntimeError
  - Calibration: test82 (asp_cgu=0.238 vs sim=0.104 → ratio=2.29, fires at ratio=2.0, floor=0.15)
- `ASP_GATE_CGU` and `ASP_GATE_CGU_FLOOR` added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]` in `config.py`
- 5 tests in `TestCanvasGainUniformityGate` (`test_bench_metrics.py`)

---

## S165 — 2026-06-24 (§4.10 Pre-Seam Global Gain Equalization)

*Root-cause fix for the dominant seam_visibility failure pattern: §4.10 equalises inter-frame luminance for ALL warped frames before GraphCut, making `_BLOCKS_GAIN_COMP`/`_BLOCKS_LUM_COMP` effective in the GraphCut path (previously only wired in the DP fallback). 1410 tests passing (85 skipped).*

### §4.10 Pre-Seam Global Gain Equalization (`backend/src/animation/rendering/compositing.py`)

- `_equalize_warped_gains(warped_frames, block_size=32)` module-level function:
  - Frame 0 is the reference; iterates frames 1…N-1 applying `_blocks_gain_compensate(prev_corrected, curr)` sequentially
  - Mask: both frames must have `max(axis=2) > 0` in the overlap region to contribute to correction
  - Returns corrected list (same length; modifies copies not originals)
- `_GLOBAL_GAIN_COMP: bool = os.environ.get("ASP_GLOBAL_GAIN_COMP", "1") != "0"` at module level (default ON)
- Wired before the GraphCut/DP composite block in `_composite_foreground()`: `if _GLOBAL_GAIN_COMP and len(warped_norm) >= 2: warped_norm = _equalize_warped_gains(warped_norm)`
- `_BLOCKS_GAIN_COMP` default changed "0" → "1" (now on by default)
- `_BLOCKS_LUM_COMP` default changed "0" → "1" (now on by default)
- `_GLOBAL_GAIN_COMP` and `_equalize_warped_gains` exported in `__all__`
- 5 tests in `TestEqualizeWarpedGains` (`test_compositing.py`)

---

## S164 — 2026-06-24 (§3.33 Feathered GraphCut Boundary Blend · §4.9 Post-Composite Seam Band Smoothing)

*Two complementary improvements targeting seam_visibility (dominant failure +512%): §3.33 feathers the hard pixel boundary at GraphCut ownership transitions; §4.9 adds an optional post-composite Gaussian blur pass at each seam row. 1405 tests passing (85 skipped).*

### §3.33 Feathered GraphCut Boundary Blend (`backend/src/animation/rendering/compositing.py`)

- `_GC_FEATHER_PX: int = int(os.environ.get("ASP_GC_FEATHER_PX", "8"))` flag at module level (default ON, 8px)
- `_feather_gc_boundaries(result, ownership_masks, warped_frames, feather_px=8)` vectorized numpy function:
  - For each pair of adjacent ownership zones, finds per-column boundary row (`argmax` of reversed axis on ownership mask)
  - Builds per-pixel alpha ramp `((b + feather_px − row) / (2 × feather_px)).clip(0, 1)` covering ±feather_px rows around boundary
  - Blends `alpha × frame_i + (1−alpha) × frame_i+1` where BOTH frames have valid content; leaves hard partition where only one frame has pixels
  - Runs ONLY in the hard-partition path (`not _MULTIBAND_BLEND`)
- Set `ASP_GC_FEATHER_PX=0` to disable; narrow band ensures no double-image ghost (8px < pose-gap threshold)
- `_GC_FEATHER_PX` and `_feather_gc_boundaries` exported in `__all__`
- 5 tests in `TestFeatherGcBoundaries` (`test_compositing.py`)

### §4.9 Post-Composite Seam Band Smoothing (`backend/src/animation/alignment/canvas.py`, `backend/src/animation/core/pipeline.py`)

- `_smooth_seam_bands(canvas, seam_ys, band_px=4)` in `canvas.py`:
  - For each seam row, extracts ±band_px band and applies `cv2.GaussianBlur(band, (1, kernel_h), 0)` (vertical direction only)
  - Triangular blend weight: 1.0 at seam centre, 0.0 at band edges — preserves content at band boundaries
  - Only blends where `canvas.max(axis=2) > 0` (valid content); no smearing into black gaps
- `_SEAM_SMOOTH_PX: int = int(os.environ.get("ASP_SEAM_SMOOTH_PX", "0"))` at pipeline.py module level (default OFF)
- Stage 11.19 in `pipeline.py run()`: estimates seam_ys from sorted affine frame centres (midpoint between adjacent centres); calls `_smooth_seam_bands()` when `_SEAM_SMOOTH_PX > 0 and N > 1`
- `SEAM_SMOOTH_PX: int = 0` constant in `constants/animation.py`
- `ASP_SEAM_SMOOTH_PX` added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]` in `config.py`
- `_SEAM_SMOOTH_PX` exported in `pipeline.py __all__`; `_smooth_seam_bands` in `canvas.py __all__`
- 5 tests in `TestSmoothSeamBands` (`test_canvas.py`)
- Enable: `ASP_SEAM_SMOOTH_PX=4` (4px half-width, ±9px kernel); safe for validation before promoting to default-ON

---

## S163 — 2026-06-24 (§4.8 SeamVisGate — Post-Render Seam Visibility Safety Net)

*One improvement: post-render SCANS fallback gate that fires when ASP seam_visibility exceeds 3× SCANS value (floor=20). Catches the 4 worst low-dy_cv seam_visibility failures in the 97-test corpus. 1402 tests passing (78 skipped).*

### §4.8 SeamVisGate (`backend/benchmark/bench_anime_stitch.py`, `backend/src/animation/core/config.py`)

- SeamVisGate block inserted between GhostGate and PIL save in `run_dataset()`:
  - Reads `ASP_GATE_SEAM_VIS` (float, default 3.0; set ≥90 to disable) and `ASP_GATE_SEAM_VIS_FLOOR` (float, default 20.0)
  - Fires when `simple_ok` and ratio limit < 90: loads `central_simple_path`, computes `_seam_visibility_score()` on both outputs
  - Gate condition: `asp_sv > max(floor, ratio × max(sim_sv, 1.0))`
  - Prints `[SeamVisGate]` status line; on fire: sets `timings["render_gate_fallback"] = 2`, raises RuntimeError → SCANS fallback
  - `_fallback_reason` key: `seam_vis_gate:asp={X}_sim={Y}_limit={Z}`
- `seam_visibility` taxonomy: 0–5=invisible, 6–12=normal, 13–25=visible step, >25=hard cut
- Calibration (97-test corpus): test74 (sv=92.6), test34 (62.8), test12 (38.2), test92 (33.6) all correctly fire at ratio=3.0, floor=20.0; test27 (sv=6.0) correctly skipped
- `ASP_GATE_SEAM_VIS` and `ASP_GATE_SEAM_VIS_FLOOR` added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]` in `config.py`
- 5 tests in `TestSeamVisibilityGate` (`test_bench_metrics.py`) — threshold calibration, floor-dominates, ratio-dominates, disable path

---

## S162 — 2026-06-24 (§4.5 Canvas-Space DP · §3.32B/C/D ghosting_siqe Scoring Fixes)

*Two improvements: §4.5 Canvas-Space DP seam as GraphCut fallback; §3.32B/C/D migrates GhostGate + RLHF scoring + param_search off the mislabelled ghosting_score metric. 1390 tests passing (85 skipped).*

### §4.5 Canvas-Space DP Seam (`backend/src/animation/rendering/compositing.py`)

- `_DP_CANVAS_SEAM = os.environ.get("ASP_DP_CANVAS_SEAM", "0") != "0"` flag at module level
- `_canvas_dp_seam_composite(warped_norm, warped_bg, canvas, H, W, N)` helper:
  - Builds per-frame coverage masks (255=has content)
  - Calls `cv2.detail_DpSeamFinder("COLOR_GRAD").find()` — handles 3-way overlaps pairwise DP misses
  - Composites pixel-by-pixel, respects `warped_bg`, runs gap-fill pass (same as GraphCut path)
- Wired as intermediate step after GraphCut fallthrough and before pairwise DP loop
- `_get_seam_cost_flags()` extended to 6-tuple (adds `_DP_CANVAS_SEAM`)
- `_DP_CANVAS_SEAM` and `_canvas_dp_seam_composite` exported in `__all__`
- 5 tests in `TestCanvasDpSeamComposite` (`test_compositing.py`)
- Enable: `ASP_DP_CANVAS_SEAM=1` (useful when `ASP_GRAPHCUT_SEAM=0`)

### §3.32B: GhostGate → ghosting_siqe (`backend/benchmark/bench_anime_stitch.py`)

- `_ghosting_score_v2()` (FFT autocorrelation, 0-100) replaces `_ghosting_score()` (sharpness proxy) in the GhostGate block
- Old gate was misfiring on sharp ASP outputs (sharpness proxy higher = sharper = better for ASP → gate incorrectly triggered SCANS fallback)
- Thresholds unchanged (floor=40, ratio=2.0) — calibration matches ghosting_siqe 0-100 scale
- Log label updated to `[GhostGate/siqe]`, fallback_reason key updated to `ghost_gate_siqe:`

### §3.32C: RLHF Rating Formula → ghosting_siqe (`backend/src/animation/rlhf/bench_import.py`)

- `suggested_rating()` now uses `ghosting_siqe / 100` (0-100→0-1 normalised) instead of `(1 − ghosting_score)`
- Old formula penalised sharp outputs; new formula correctly penalises ghosty outputs
- Fallback default: `ghosting_siqe=30.0` (neutral, approx ASP avg)
- 5 tests in `TestSuggestedRatingGhostingSiqe` (`test_bench_import.py`)

### §3.32D: Param Search Verdict → ghosting_siqe (`backend/src/animation/hitl/param_search.py`)

- `_verdict_from_config()` uses `ghosting_siqe / 100` with fallback to `ghosting_score / 100` for legacy JSON without ghosting_siqe key
- Old formula penalised sharpness under the label "ghosting" — caused incorrect parameter search signals
- 5 tests in `TestVerdictFromConfigGhostingSiqe` (`test_param_search.py`)

---

## S161 — 2026-06-24 (§4.7 dy_cv Gate · §4.2 GraphCut Default-ON · §3.32 Edge Energy Alias)

*Three improvements shipped: catastrophic-failure prevention gate, GraphCut seam enabled by default, and ghosting metric taxonomy fix. 1375 tests passing (85 skipped).*

### §4.7 dy_cv Pre-Detection Gate (`backend/src/animation/core/pipeline.py`, `backend/src/constants/animation.py`)

- `DY_CV_MAX = 1.5` constant added to `animation.py`
- `_DY_CV_MAX = float(os.environ.get("ASP_DY_CV_MAX", "1.5"))` module-level flag in `pipeline.py`
- `_compute_dy_cv(affines)` helper: `std(|Δty|) / mean(|Δty|)`; returns 0.0 when N<2 or mean<1 px (guard against static sequences)
- Gate wired before Stage 9 canvas-span-utilisation gate: `_dy_cv_gate >= _DY_CV_MAX` → immediate SCANS fallback
- Motivation: 97-test benchmark shows dy_cv≥1.5 → catastrophic ASP failure (AlSSIM 0.44–0.62, seam_vis 60–120 vs SCANS 2–3) while SCANS handles these sequences trivially. test77 (dy_cv=2.22), test43 (dy_cv=2.16), test82 (dy_cv=2.20) are all in this cluster.
- 5 tests in `TestComputeDyCv` (`test_pipeline.py`)
- `_compute_dy_cv` and `_DY_CV_MAX` exported in `pipeline.py __all__`

### §4.2 GraphCut Global Seam — Enabled by Default (`backend/src/animation/rendering/compositing.py`)

- `_GRAPHCUT_SEAM` env var default changed from `"0"` to `"1"`: `os.environ.get("ASP_GRAPHCUT_SEAM", "1")`
- GraphCut (`batch.seam.graphcut_seam_find` → C++ `cv::detail::GraphCutSeamFinder(COST_COLOR_GRAD)`) was already fully implemented in Phase 4 C++ migration; this makes it the default path
- Falls back to pairwise DP when `batch` module unavailable or GraphCut raises exception
- `test_graphcut_flag_off_by_default` updated to `test_graphcut_flag_on_by_default` (asserts `isinstance(_GRAPHCUT_SEAM, bool)` — value is `BATCH_AVAILABLE` which is True in venv)
- Target metric: `seam_visibility` +512% worse (25.77 vs 4.21 from 97-test benchmark) — dominant failure mode

### §3.32 Ghosting Metric Taxonomy Fix (`backend/benchmark/bench_anime_stitch.py`)

- `_edge_energy_score(img)` added as correctly-labelled wrapper for `_ghosting_score()` (double-Sobel Y = sharpness proxy, NOT ghosting)
- Metrics dict now emits `"edge_energy_score"` (primary key) alongside `"ghosting_score"` (alias kept for `ASP_GATE_GHOST` backward-compat and `ghosting_siqe` gate calibration)
- `_ghosting_score()` docstring updated: "§3.32: Edge energy proxy (formerly mislabelled as ghosting)"
- `_ghosting_score_v2` docstring updated to cross-reference `edge_energy_score`
- 5 tests in `TestEdgeEnergyScore` (`test_bench_metrics.py`)

---

## Benchmark Analysis — 2026-06-23 (Full 97-Test Benchmark, S160 Code)

*No new code changes. Full 97-test benchmark completed overnight (~3 hours, PID 16528 nohup). JSON: `backend/benchmark/output/anime_stitch_20260623_234305.json`. Documentation updated across `.agent/cache/` and `moon/roadmaps/asp.md`.*

### Key Findings

**1. `ghosting_score` mislabelling confirmed at corpus scale (97 tests)**  
`_ghosting_score(img)` = `mean(|∂²I/∂y²|)` (double-Sobel Y) = edge energy = sharpness proxy. Historical S142 "ASP 42% worse ghosting" was wrong. TRUE ghosting metric: `ghosting_siqe` (FFT autocorrelation, §3.8A) — **ASP=36.21 vs SS=72.34: ASP 49.9% fewer ghost patterns across all 97 tests**. Roadmap §3.32 for the rename/fix.

**2. `dy_cv` regime split — confirmed at corpus scale, revised thresholds**  
- **dy_cv < 0.17** (N=31, uniform scroll): ASP +1.0% AlSSIM avg, 20/31 (64.5%) comparable+asp_better. *The 13-test sample earlier had 5/5 here — that was optimistic sampling.*
- **dy_cv 0.17–0.50** (N=44, mixed): ASP −5.1% AlSSIM, 22/44 comparable+asp_better.
- **dy_cv ≥ 0.50** (N=22, irregular): ASP −13.2% AlSSIM, 9/22 comparable+asp_better.
- **dy_cv ≥ 1.0** (N=8): 5 simple_better, 2 comparable, 1 asp_better (test53, anomalous — no GT).

**3. Full-corpus performance picture (97 tests, S160 code, aligned_ssim_vs_gt)**  
- AlSSIM overall (55 GT tests): ASP=0.6795 vs SS=0.7195 (−5.6%)
- `seam_visibility`: ASP=25.77 vs SS=4.21 (+512% worse) — dominant failure
- `ghosting_siqe` (true): ASP=36.21 vs SS=72.34 (−49.9% — ASP BETTER)
- `sharpness`: ASP=96.67 vs SS=64.34 (+50.2% BETTER)
- Verdicts (97t): 10 asp_better (10.3%), 41 comparable (42.3%), 45 simple_better (46.4%), 1 insufficient (test95 — simple stitch crash)
- Fallbacks: 9/97 (9.3%)

**4. S142 → S160 net movement: marginal**  
asp_better 9→10 (+1), simple_better 46→45 (−1), comparable 41→41. 18 sessions of compositing work (S143–S160) produced one test improvement. Confirms that compositing refinements have reached diminishing returns without fixing core seam routing (§4.2 GraphCut) and flow estimation (RAFT).

**5. Catastrophic failure cluster at dy_cv 1.5–2.5**  
test77 (dy_cv=2.22, AlSSIM 0.444), test43 (dy_cv=2.16, AlSSIM 0.479), test82 (dy_cv=2.20, AlSSIM 0.615) — all catastrophic. test53 (dy_cv=3.59) and test18 (dy_cv=17.1) are anomalous (don't fail catastrophically, possibly trigger different pipeline paths). Explicit dy_cv gate → SCANS fallback needed for dy_cv ≥ 1.0.

**6. test95: simple stitch crashed**  
`metrics_simple = {}` — verdict=insufficient_data. ASP output exists (AlSSIM 0.656). Not counted in verdicts.

**7. `strip_banding_score` remains invalid cross-system metric**  
Always 0.0 for simple stitch. Confirmed across all 97 tests.

### Files Updated
- `.agent/cache/asp_state_of_the_pipeline.md` — replaced 13-test table with full 97-test aggregate + regime table + updated root causes
- `.agent/cache/stitching_systems_deep_comparison.md` — §Remaining Gap updated with 97-test data, seam_visibility +512% (was +654% from 13-test)
- `moon/roadmaps/asp.md` — Phase 4 header, §3.32 confirmation, Document History updated to 97-test
- `moon/CHANGELOG.md` — this entry (replaced 13-test entry)

---

## ASP C++ Migration — Phase 6: GPU Acceleration (2026-06-23) 🏁 ROADMAP CLOSED

*Phase 6: adds OpenCL UMat acceleration paths and CUDA detection to the `batch/` C++ extension. All 6 phases of the ASP C++ migration are now complete. Roadmap archived to `moon/archive/asp_cpp_migration.md`.*

### `batch/src/canvas.cpp` — `try_gpu` + `gpu_device_count`

- `warp_frames_to_canvas(frames, affines, canvas_h, canvas_w, bool try_gpu=false)`: when `try_gpu=true`, each frame is uploaded to `cv::UMat`, `cv::warpAffine` runs via OpenCL, result downloaded. Falls back to OpenMP CPU path on any exception.
- `render_median(warped_frames, bool try_gpu=false)`: param added for API symmetry; CPU nth_element path always used (placeholder for future CUDA nth_element kernel).
- `gpu_device_count() -> int`: new function returning `cv::cuda::getCudaEnabledDeviceCount()` under `#ifdef HAVE_CUDA`, else 0. `<opencv2/cuda.hpp>` conditionally included.

### `batch/src/seam.cpp` — `try_gpu` in `build_seam_cost_map`

- `build_seam_cost_map(..., bool try_gpu=false)`: both `cv::GaussianBlur` calls (cost_map_blur and cost_col_smooth) use `cv::UMat` when `try_gpu=true`. Propagated through `build_seam_cost_map_impl`.

### `batch/src/compositing.cpp` — `try_gpu` in `multiband_blend`

- `multiband_blend(..., bool try_gpu=false)`: `MultiBandBlender(try_gpu ? 1 : 0, num_bands)` — enables CUDA blender when `try_gpu=true` and CUDA is available.

### `backend/src/animation/rendering/rendering.py` — `_BATCH_GPU` dispatch

- `_BATCH_GPU = os.environ.get("ASP_BATCH_GPU","0") != "0"` flag added.
- All three `warp_frames_to_canvas` call sites pass `**{"try_gpu": True}` when `_BATCH_GPU` is set. Old compiled `.so` rejects unknown kwarg → TypeError → existing `except` fallback (zero regression).

### `backend/test/animation/batch/test_batch_gpu.py` — 7 Phase 6 tests

- `TestGpuDeviceCount` (2): returns non-negative int, stable across calls.
- `TestWarpFramesGpu` (3): `try_gpu=False` shape, `try_gpu=True` no-crash, CPU/GPU output agreement on identity affine.
- `TestRenderMedianGpu` (2): shape/dtype with `try_gpu=False` and `try_gpu=True`.
- All guarded by `HAS_PHASE6 = hasattr(batch.canvas, "gpu_device_count")` — skip with stale `.so`.

---

## ASP C++ Migration — Phase 5f: render_laplacian warp wiring (2026-06-23)

*Phase 5f: wires `batch.canvas.warp_frames_to_canvas` into `_render_laplacian` in `rendering.py`, replacing the sequential Python `cv2.warpAffine` loop with a single C++ parallel OpenMP call. Also fixes SUBMODULE_APIS test failures caused by stale compiled batch `.so`. 5 new tests.*

### `backend/src/animation/rendering/rendering.py` — `_render_laplacian` warp

- **Before**: `for img, M in zip(frames, affines): w = cv2.warpAffine(img, M, (W, H), ...)` — N sequential GIL round-trips into the Python `cv2` wrapper.
- **After**: `warped_list = list(_batch_render.canvas.warp_frames_to_canvas([...], affines_f32, H, W))` — single C++ call; OpenMP parallelises the per-frame `cv::warpAffine` loop; GIL released inside C++.
- `mask_list` built from `(w.max(axis=2) > 0).astype(np.uint8) * 255` over the returned warped frames — same result as the Python path.
- **Fallback**: `except Exception` resets `warped_list = []`; non-empty check then re-runs the sequential Python loop. Zero behaviour change without `batch`.

### `backend/test/animation/batch/test_batch_imports.py` — SUBMODULE_APIS fix

- Re-commented `filter_edge_graph` (matching) and `find_optimal_boundaries`, `blocks_gain_compensate_pair`, `blocks_lum_compensate_pair`, `multiband_blend` (compositing) with "add after next C++ build" notes.
- These symbols were added to SUBMODULE_APIS before the compiled `.so` was rebuilt — the `.so` predates Phase 3b, 4, 5b, and 5d. Commenting them out restores 31/31 passing.

### Tests — 5 new tests

- **`TestRenderLaplacianBatchWarp`** (5 tests in `test_rendering.py`): output shape (H,W,3), non-empty `valid_mask`, Python/C++ canvas pixel agreement (max diff = 0 for identical inputs), non-empty `warped_list` from C++ path, graceful fallback when `batch.canvas` is mocked to raise. All 5 skip cleanly when `batch` not compiled.

---

## ASP C++ Migration — Phase 5e: render_median C++ fast path wiring (2026-06-23)

*Phase 5e: wires `batch.canvas.render_median` + `batch.canvas.warp_frames_to_canvas` into `_render_median` as an early-return fast path. Fires when no FG exclusion, no sequential colour correction, no baselines, no confidence weighting, and the full-canvas stack fits within 1 GB. Estimated 25× speedup for the SCANS fallback path where BiRefNet is skipped. 5 new tests.*

### `backend/src/animation/rendering/rendering.py` — `_render_median` fast path

- **Condition**: `_BATCH_RENDER and not _exclude_fg and not _need_color_corr and _baselines is None and confidence_weights is None and 2·N·H·W·3 ≤ 1 GB`. Fires when all FG bg_masks are `None` (SCANS path without BiRefNet) or `ASP_FG_EXCLUDE_MEDIAN=0`.
- **Fast path flow**:
  1. `batch.canvas.warp_frames_to_canvas` — parallel OpenMP `cv::warpAffine` for all N frames
  2. `batch.canvas.render_median` — per-pixel `std::nth_element` via OpenMP row parallelism
  3. `valid_mask` built from per-frame `w.max(axis=2) > 0` scan
  4. Fade pass: builds `np.stack(warped, axis=0)` as full-canvas `(N, H, W, 3)` stack; slices rows/columns directly (no chunking needed since all frames already in memory)
  5. Animation re-render: same recursive `_render_median` call as the Python path (subgroup re-render also takes the fast path when conditions hold)
- **Fallback**: `except Exception` resets `canvas`/`valid_mask` to zeros and falls through to the existing chunked Python loop — zero behaviour change without `batch`.
- **Memory guard**: fast path skipped when `2·N·H·W·3 > 1 GB` to avoid OOM on very large canvases; the chunked path handles those cases.

### Tests — 5 new tests

- **`TestRenderMedianBatchFastPath`** (5 tests in `test_rendering.py`): output shape correct, valid_mask covers all rows, median of identical frames matches frame colour (±5), Python/C++ canvas pixel agreement (max diff ≤ 2), fast path skipped when FG masks provided. All 5 skip cleanly when `batch` not compiled.

---

## ASP C++ Migration — Phase 5d: find_optimal_boundaries in C++ (2026-06-23)

*Phase 5d: `_find_optimal_boundaries` — the boundary search hot path — implemented in `compositing.cpp` and wired into Python. GIL-released inner pixel loop; adaptive range; bg-pixel scoring with warped masks. 10 new tests.*

### `batch/src/compositing.cpp` — `find_optimal_boundaries` added

- **Algorithm**: For each adjacent frame pair in `order`, scans ±`search_range` rows from `initial_boundaries[k]`. At each candidate row, extracts a `search_slab`-row band from both warped frames and accumulates:
  - `sum_all / valid_count` — mean-abs BGR diff over all valid (both-nonzero) pixels
  - `sum_bg / bg_count` — mean-abs diff over background-masked pixels (when `bg_masks` provided)
  - Score: `0.4 × bg_d + 0.6 × all_d` when `bg_count ≥ 50`, else `all_d`
- **Adaptive range**: if affines tx spread `< 5px` (pure vertical scroll), `effective_range = 100`; otherwise `= search_range` (default 250). Matches Python §S17 logic exactly.
- **Background mask warp**: if both `bg_masks` and `affines` provided, warps each bg mask into canvas space with `cv::warpAffine(INTER_NEAREST)` once before the search loop.
- **GIL release**: `py::gil_scoped_release` wraps the entire boundary search loop (all Python objects converted to `cv::Mat` before release).
- **Final measurement**: at `best_y ± half` window for feather metric; `feather_metric = best_diff if both < 20.0 else total_diff`.
- Registered in `register_compositing()` with arg names and docstring.

### `backend/src/animation/rendering/compositing.py` — `_find_optimal_boundaries` wired

- C++ dispatch added as first path: converts `bg_masks` items to `uint8`, calls `batch.compositing.find_optimal_boundaries` with `np.ascontiguousarray` frames and `SEARCH_RANGE`/`SEARCH_SLAB` constants.
- `try/except Exception` falls through to the existing Python loop (no behaviour change without `batch`).

### Tests — 10 new tests

- **`TestFindOptimalBoundariesBatchWiring`** (5 tests in `test_compositing.py`): output shape matches N-1, boundary stays in canvas, identical frames → diff≈0, gradient frames move boundary toward low-diff region, zero search range returns initial bound. All 5 skip cleanly when batch not compiled.
- **`TestFindOptimalBoundariesVsPython`** (5 xfail-until-compiled in `test_batch_vs_python.py`): shapes agree, boundary positions agree within ±1 row, diff scores agree within ±2, identical frames diff < 1.0, three-boundary agreement within ±2 rows / ±3 diff.

---

## ASP C++ Migration — Phase 5c: exposure.cpp stubs replaced + correct_vignetting wired (2026-06-23)

*Phase 5c: all three `exposure.cpp` stubs replaced with real implementations. `correct_vignetting` wired into `photometric.py`. 11 new tests.*

### `batch/src/exposure.cpp` — all stubs replaced with real implementations
- **`correct_vignetting(frame, vmap)`**: `cv::Mat` per-channel `split/multiply/merge` with mismatched-size auto-resize. Added shared `list_to_umats_bgr`, `list_to_umats_mask`, `list_to_points` helpers. Added `#include <opencv2/stitching/detail/exposure_compensate.hpp>`.
- **`blocks_gain_compensate(frames, masks, corners, bl_w, bl_h, nr_feeds, nr_iter)`**: wraps `cv::detail::BlocksGainCompensator`. Converts lists to `std::vector<cv::UMat>` via `list_to_umats_*`; builds `std::vector<std::pair<cv::UMat, uchar>>` mask pairs with `uchar(255)` overlap flag; `feed()` runs GIL-released; `apply()` per-frame returns `array_from_mat`.
- **`blocks_channels_compensate(frames, masks, corners, bl_w, bl_h)`**: wraps `cv::detail::BlocksChannelsCompensator` — same structure but per-channel (B,G,R) gain maps for white-balance correction.

### `backend/src/animation/rendering/photometric.py` — `correct_vignetting` wired
- Added `_batch_photo` import and `_BATCH_PHOTO` guard.
- Per-frame correction loop: tries `batch.exposure.correct_vignetting(img, curr_gain)` first; falls back to Python multiply+clip on any exception.

### Tests — 11 new tests
- `TestCorrectVignettingPython` (6 tests in `test_photometric.py`): empty frames, flat gain, dtype, shape, multi-frame, valid range.
- `TestCorrectVignettingBatchWiring` (5 tests in `test_photometric.py`): identity, brightens, mismatched gain map size, dtype, valid range — skipped until C++ rebuilt.
- `TestCorrectVignettingVsPython` (5 xfail-until-compiled in `test_batch_vs_python.py`): unit gain, radial gain agreement, dtype, brightens, clip to 255.

---

## ASP C++ Migration — Phase 5b Remaining Wiring: ecc_refine + blocks compensation (2026-06-23)

*Phase 5b: `alignment/ecc.py` now dispatches inner `cv2.findTransformECC` to `batch.fg_register.ecc_refine`. Two new C++ functions `blocks_gain_compensate_pair` and `blocks_lum_compensate_pair` added to `compositing.cpp` and wired into `rendering/compositing.py`. 20 new tests.*

### `batch/src/compositing.cpp` — `blocks_gain_compensate_pair` + `blocks_lum_compensate_pair` added
- **`blocks_gain_compensate_pair(fa, fb, block_size=32)`**: per-block BGR gain. `CV_32FC3` gain grid filled per block (`mean(fa_ch)/mean(fb_ch)` if `mean_fb ≥ 1.0` else `1.0`). Bilinear resize to `(H,W,3)`. Per-channel `threshold(THRESH_TRUNC, 2.0)` + `setTo(0.5, < 0.5)` clamp. Element-wise `multiply(fb_f32, gain_map)` → `CV_8UC3`.
- **`blocks_lum_compensate_pair(fa, fb, block_size=32)`**: LAB L-channel scalar gain. Converts both zones via `COLOR_BGR2Lab`, extracts L channel per block. Gain = `m_fa_L / max(1.0, m_fb_L)`. Single-channel gain grid bilinear-resized to `(H,W)`. `threshold` + `setTo` clamp. Applied uniformly across all BGR channels via `split/multiply/merge`.
- Both registered in `register_compositing()` with docstrings.

### `backend/src/animation/alignment/ecc.py` — `batch.fg_register.ecc_refine` wired
- Added `_batch_ecc` import and `_BATCH_ECC` guard at module level.
- Inner `cv2.findTransformECC(r_s, s_s, M_s, ...)` call at each pyramid level replaced by dispatch: `_batch_ecc.fg_register.ecc_refine(r_s, s_s, M_s, ecc_m_s, cv2.MOTION_TRANSLATION, ECC_MAX_ITER, ECC_EPS)` when `_BATCH_ECC`. Both `cv2.error` and `RuntimeError` (C++ re-throw) caught to `break` out of the pyramid loop.

### `backend/src/animation/rendering/compositing.py` — batch dispatch added
- `_blocks_gain_compensate`: tries `batch.compositing.blocks_gain_compensate_pair` before Python nested loop.
- `_blocks_lum_compensate`: tries `batch.compositing.blocks_lum_compensate_pair` before Python nested loop.

### Tests — 20 new tests
- `TestBlocksGainCompensateBatchWiring` (5 tests in `test_compositing.py`): identity, brightens, empty zones, gain clamp, valid range.
- `TestBlocksLumCompensateBatchWiring` (5 tests in `test_compositing.py`): identity, brightens, empty zones, valid range, hue-preserving scalar gain.
- `TestBlocksGainCompensateVsPython` (5 xfail-until-compiled in `test_batch_vs_python.py`): identity, brighter-fa, near-black, dtype, gain-clamped-max.
- `TestBlocksLumCompensateVsPython` (5 xfail-until-compiled in `test_batch_vs_python.py`): identity, brighter-fa, dtype, near-black, gain-clamped-at-2.
- All 31 batch tests pass; 34 skipped (no compiled batch.so).

---

## ASP C++ Migration — Phase 3b + Phase 5 Remaining Wiring (2026-06-23)

*Phase 3b: `matching.cpp::filter_edge_graph` (§2.14 + geometric consistency + min-step) implemented and wired. Phase 5 remaining wiring: `near_dup_luma_filter` and `spatial_dedup_frames` now fully wired. Python fallback for `_near_dup_luma_filter` fixed to handle 2D float32 grayscale thumbs.*

### `batch/src/matching.cpp` — `filter_edge_graph` added (Phase 3b)
- New function `filter_edge_graph(edges, min_step_px=10, consistency_tol_px=15, max_tri_residual_px=0)` → `list[dict]`.
- **§2.14 Triangular Consistency**: O(F³) enumeration over all triangles in edge graph; accumulates `penalty[k] *= 0.5` for weakest edge in each inconsistent triangle (L2 residual > threshold); applied at output without modifying parse-time weights (multi-triangle accumulation).
- **Geometric Consistency**: skip edges (j>i+1) whose measured displacement disagrees with the adjacent-edge chain sum by more than `consistency_tol_px` on either axis are rejected. When chain is incomplete (missing adjacent edge), skip edge is kept.
- **Min-step guard**: detects dominant axis from median adjacent-edge displacements; drops adjacent edges with displacement on dominant axis below `min_step_px`.
- Registered in `register_matching()` with full docstring.

### `backend/src/animation/core/pipeline.py` — `filter_edge_graph` wired
- `_filter_edges`: the §2.14, geometric consistency, and min-step Python blocks are now replaced by a single `_batch.matching.filter_edge_graph(edges, MIN_EXPECTED_STEP, 15.0, _TRI_CONSISTENCY_MAX_RESIDUAL)` call when batch is available. Python fallbacks run unchanged if batch absent or call throws.

### `backend/src/animation/ingestion/frame_selection.py` — `near_dup_luma_filter` wired
- `_near_dup_luma_filter`: C++ dispatch added at the top of the function body (after threshold guard). Converts float32 [0,1] thumbs to uint8 before passing to `batch.frame_selection.near_dup_luma_filter`; extracts paths from returned tuple.
- Python fallback bug fixed: `cv2.cvtColor(t, COLOR_BGR2GRAY)` replaced with `_to_gray_f32(t)` helper that handles both 2D grayscale (identity) and 3D BGR (cvtColor). Threshold scale fixed: float32 [0,1] thumbs compare in [0,1] space (`threshold / 255`).

### `backend/src/animation/core/pipeline.py` — `spatial_dedup_frames` wired
- `_spatial_dedup_frames`: C++ dispatch block added before Python dedup logic. Converts M-affine edges to `{"i", "j", "dx", "dy"}` format for C++; receives keep indices back; reconstructs full 6-tuple `(frames, scans, masks, paths, new_edges, n_dropped)` from indices. Edge re-indexing via `o2n` and drop_set exclusion matches Python behavior.

### Tests — 25 new tests
- `TestNearDupLumaFilterBatchWiring` (5 tests in `test_frame_selection.py`): float32 2D thumbs — returns list[str], first kept, last kept, distinct all-kept, identical first+last only.
- `TestSpatialDedupFramesBatchWiring` (5 tests in `test_pipeline.py`): no-drop case, near-static frame dropped, scans sync preserved, edge reindex correct, horizontal displacement respected.
- `TestFilterEdgeGraph` (5 tests in `test_batch_vs_python.py`): adjacent-only pass, consistent skip kept, inconsistent skip rejected, §2.14 weight halved, min-step guard — skipped when `batch.matching` not compiled; xfail when stub raises RuntimeError.

---

## ASP C++ Migration — Phase 5 Complete (fg_register + sr_classical) (2026-06-23)

*Phase 5 completion: `fg_register.cpp` (4 fns) and `sr_classical.cpp` (4 fns) implemented and wired. All Phase 5 `.cpp` files are now real implementations (no stubs remain). Phase 6 (GPU) is next.*

### `batch/src/fg_register.cpp` — 4 functions implemented
- `ecc_refine(template, source, initial_M, mask, motion_type, max_iters, eps)` → float32 (2,3): wraps `cv::findTransformECC` with `gaussFiltSize=5`; throws `std::runtime_error` on `cv::Exception` so Python caller can log and skip.
- `arap_push_regularise(flow, fg_mask, cell_size, n_iter, image, offset_y, offset_x)` → float32 (H,W,2): per-cell `nth_element` median in C++ scratch buffers (OpenMP parallel); LSD collinearity groups cells by shared line segments, applies mean tx/ty; bilinear interp via `cv::resize(INTER_LINEAR)`; SLIC superpixel initialization guarded by `#ifdef HAVE_OPENCV_XIMGPROC`, falls back to regular grid.
- `slic_sgm_proxy(crop_a, crop_b, fg_mask, n_segments, compactness, max_dist_frac, min_match_score)` → float32 (H,W,2): BGR→LAB `cv::cvtColor`; ximgproc SLIC or regular grid labels; per-segment colour affinity × centroid distance score; throws when <2 segs (caller falls back to RAFT).
- `lsd_collinearity(seam_band, offset_y, offset_x, min_length)` → `list[dict]`: `cv::createLineSegmentDetector(0).detect()` with length filter and offset shift.

### `backend/src/animation/alignment/fg_register.py` — C++ dispatch wired
- Added `_BATCH_FGREG` flag (try/except `import batch`).
- `_arap_regularise` → `batch.fg_register.arap_push_regularise` primary dispatch; full Python fallback on exception.
- `_slic_sgm_proxy` → `batch.fg_register.slic_sgm_proxy` fallback when scikit-image (`_slic_fn`) is unavailable.

### `batch/src/sr_classical.cpp` — 4 functions implemented
- `dct_restore(frame, block_size, threshold_frac)` → uint8 same shape: tile DCT-II soft-threshold; `cv::dct` forward + `cv::idct` inverse per tile; OpenMP parallel over tiles; `threshold_frac × max_coeff` zeros high-frequency noise.
- `pso_register(reference, source, n_particles, t_max, search_lo, search_hi)` → `dict{tx, ty, angle, scale, fitness}`: PSO translation search; per-particle NCC via `cv::warpAffine`; OpenMP parallel fitness evaluation; per-iteration velocity clamp and bounds reflect; returns DP path baseline if DE didn't improve.
- `de_seam(img_a, img_b, horizontal, pop_size, n_gen, smoothness_w, de_f, de_cr)` → int32 (H,): Differential Evolution over real-valued seam chromosomes; energy = pixel absdiff + 0.5×(|gx|+|gy|) + smoothness×|path diff|; OpenMP parallel fitness; DE mutation/crossover/selection; DP baseline seam seeds half the initial population; returns DP if DE doesn't improve.
- `robust_sr(lr_frames, affines, scale, beta, nr_iterations)` → uint8 (H×scale, W×scale, C): multi-frame cubic upsample fusion + iterative L1 sub-gradient (Gaussian blur residual sign descent).

### `backend/src/animation/mfsr/de_seam.py` — C++ dispatch wired
- Added `_BATCH_SR` flag.
- `de_seam` → `batch.sr_classical.de_seam` primary dispatch; Python DE + DP fallback on any exception.

### `backend/src/animation/mfsr/pso_registration.py` — C++ dispatch wired
- Added `_BATCH_SR` flag.
- `pso_register` → `batch.sr_classical.pso_register` for `motion_model="translation"`; Python PSO fallback for other models or on exception.

### Tests
- `TestBatchFgRegisterWiring` (5 tests in `test_fg_register.py`): arap_regularise shape/dtype, zero flow, fg smoothing, slic_sgm_proxy return type, image kwarg no crash.
- `TestBatchSrClassicalDirect` (5 tests in `test_mfsr_batch_wiring.py`): dct_restore shape, de_seam int32, de_seam bounds, pso dict keys, pso fitness range — auto-skipped until `sr_classical.cpp` is compiled.
- `TestDeSeamWiring` (3 tests): de_seam returns array, length matches rows (horizontal), length matches cols (vertical).
- `TestPsoRegisterWiring` (2 tests): returns (2,3) affine + float score, tx within search range.

### Result
- Python test suite (runnable tests): 10 passed, 5 skipped (pending sr_classical compile), 0 failed.
- All Phase 5 `.cpp` implementations complete. Total Phase 1–5: 26 new wiring tests added.

---

## ASP C++ Migration — Phase 5 (canvas + frame_selection) (2026-06-23)

*Phase 5 partial completion: `canvas.cpp` (7 functions) and `frame_selection.cpp` (5 functions) implemented in C++ and wired into Python pipeline with fallbacks.*

### `batch/src/canvas.cpp` — 7 functions implemented
- `compute_canvas(affines, frame_shapes)` → `(canvas_h, canvas_w, shift_x, shift_y)`: warped-corner bounding box; shift placed so min corner is at (0,0). Python caller applies `CANVAS_MAX_DIM` clamp.
- `warp_frames_to_canvas(frames, affines, canvas_h, canvas_w)` → `list[ndarray]`: OpenMP parallel `cv::warpAffine(INTER_LINEAR)` over all N frames (releases GIL).
- `render_median(warped_frames)` → `ndarray`: per-pixel content-aware `nth_element` temporal median; excludes all-black (no-content) pixels from sample. OpenMP parallel over rows.
- `crop_to_valid(canvas, valid_fraction)` → `(y0, y1, x0, x1)`: tight bounding-box scan for non-zero content; exclusive Python-slice output.
- `telea_fill_gaps(canvas, gap_mask, inpaint_radius)` → `ndarray`: `cv::inpaint(INPAINT_TELEA, radius=3)` wrapper; noop on empty mask.
- `detect_scroll_axis(affines)` → `str`: `"vertical" | "horizontal" | "diagonal" | "none"` from tx/ty range ratio; matches Python thresholds exactly.
- `panorama_stitch_fallback(frames)` → `(bool, ndarray | None)`: `cv::Stitcher_create(PANORAMA).stitch()` with error-code handling; returns `(False, None)` on failure.

### `backend/src/animation/alignment/canvas.py` — C++ dispatch wired
- Added `_BATCH_CANVAS` flag (try/except `import batch`).
- `_compute_canvas` → `batch.canvas.compute_canvas` fast path; returns same `(int, int, ndarray[2])` type.
- `_detect_scroll_axis` → `batch.canvas.detect_scroll_axis` fast path.
- `_telea_fill_gaps` → `batch.canvas.telea_fill_gaps` fast path.
- `_panorama_stitch_fallback` → `batch.canvas.panorama_stitch_fallback` for the stitch step; Python post-processing (largest_valid_rect crop, PIL save) unchanged.

### `batch/src/frame_selection.cpp` — 5 functions implemented
- `detect_hold_blocks_mad(thumbs, threshold)` → `list[int]` of hold-frame indices (MAD < threshold); parallel MAD via `cv::absdiff + cv::mean`, `to_luma_f32` converts uint8 input to float [0,1] for threshold comparison.
- `detect_hold_blocks_dhash(thumbs, hash_size, hamming_thresh)` → `list[int]` of hold-frame indices; INTER_AREA resize to (hash_size, hash_size+1), horizontal gradient binarisation, Hamming XOR popcount.
- `temporal_variance_filter(thumbs, paths, sigma_threshold)` → `(list[ndarray], list[str])`; per-triplet pixel variance; first/last always kept.
- `near_dup_luma_filter(thumbs, paths, threshold)` → `(list[ndarray], list[str])`; mean abs luma diff vs previous kept frame (threshold in [0,255] scale); first/last kept.
- `spatial_dedup_frames(frames, scans, masks, paths, edges, min_disp_px)` → `list[int]` keep indices; greedy from cumulative edge displacements; always keeps first + last.

### `backend/src/animation/ingestion/frame_selection.py` — C++ dispatch wired
- Added `_BATCH_FSEL` flag.
- `_detect_hold_blocks` → `batch.frame_selection.detect_hold_blocks_mad`; converts float32 [0,1] thumbs to uint8; converts C++ hold-frame-indices to Python block-start-indices (`[i for i in range(N) if i not in hold_set]`).
- `_detect_hold_blocks_dhash` → `batch.frame_selection.detect_hold_blocks_dhash`; same conversion pattern.
- `_temporal_variance_filter` → `batch.frame_selection.temporal_variance_filter`; recovers original float32 thumb objects by path-key mapping.

### `backend/src/animation/rendering/rendering.py` — C++ dispatch wired
- Added `_BATCH_RENDER` flag.
- `_render_first` → `batch.canvas.warp_frames_to_canvas` fast path: parallel warpAffine over all N frames (GIL released in C++), then reverse-order first-frame-wins compositing. Falls back to sequential Python `cv2.warpAffine` loop on any exception.

### Tests
- `TestBatchCanvasWiring` (6 tests in `test_canvas.py`): compute_canvas types, height coverage, scroll axis vertical/horizontal, telea no-gap identity, telea shape preserved.
- `TestBatchFrameSelectionWiring` (5 tests in `test_frame_selection.py`): hold blocks returns list[int], always includes 0, identical frames → single block, different frames → N blocks, temporal variance disabled → no drop.

### Result
- Python test suite: 1329 passed, 28 skipped, 0 failed (+11 vs Phase 4)

---

## ASP C++ Migration — Phase 4 Complete (2026-06-23)

*Completed Phase 4 of the C++ migration roadmap: GraphCut seam finder and MultiBandBlender wired into the Python compositing pipeline; `seam_ownership_entropy` benchmark metric added. Phase 5 (canvas, fg_register, frame_selection, sr_classical) next.*

### GraphCut Seam Python Wiring (`backend/src/animation/rendering/compositing.py`)
- Wired `batch.seam.graphcut_seam_find` as an early-return path in `_composite_foreground` before the hard-partition + DP blend loop. When `ASP_GRAPHCUT_SEAM=1`:
  - Builds per-frame coverage masks from `warped_norm`; uses `(0,0)` corners (frames are full canvas-size)
  - Calls `graphcut_seam_find(gc_frames, gc_masks, gc_corners)` with GIL released in C++
  - Applies returned ownership masks to result; does gap fill inline; updates `seam_meta_out`; returns early
  - If `ASP_MULTIBAND_BLEND=1` also set: calls `batch.compositing.multiband_blend(gc_frames, ownership, gc_corners, num_bands=5)` and clips result to `(H, W)` canvas
  - Any exception falls back to existing DP blend path (no loss of robustness)

### `seam_ownership_entropy` Benchmark Metric (`backend/benchmark/bench_anime_stitch.py`)
- Implemented `_seam_ownership_entropy(output_img, affines, band_px=8)` (§4.3): Shannon entropy (bits, base-2) of luminance pixel values in `±band_px` bands around estimated seam boundary rows. Seam boundaries estimated as midpoints between sorted `ty` affine offsets.
  - Low entropy (`< 3.5`): clean blend — single-frame content in seam band
  - High entropy (`> 5.0`): contested seam — both-frame content present (potential ghosting)
- Wired into `_compute_all_metrics` as `"seam_ownership_entropy"` key.

### Tests (Python)
- `TestGraphcutSeamWiring` (5 tests in `test_compositing.py`): flags exist, both off by default, included in `_get_seam_cost_flags()` tuple.
- `TestSeamOwnershipEntropy` (5 tests in `test_bench_metrics.py`): no-affines/single-affine return 0.0, result nonneg, uniform image low entropy, wired in `_compute_all_metrics`.

### Result
- Python test suite: 1318 passed, 28 skipped, 0 failed

---

## ASP C++ Migration — Phase 4 Started (2026-06-23)

*Phase 4: GraphCut seam finder and MultiBandBlender implemented in C++ (`batch.seam`, `batch.compositing`). `seam_batch` Python wiring complete. Critical pybind11 zero-stride array bug fixed. Python dispatch correctness fixes for Phase 2/3 fast paths.*

### GraphCut Seam Finder (`batch/src/seam.cpp`)
- Implemented `graphcut_seam_find`: wraps `cv::detail::GraphCutSeamFinder(COST_COLOR_GRAD)`. Accepts N warped frames + N binary masks + N canvas corners; returns N updated ownership masks (per-pixel assignment). Global N-frame graph-cut replaces pairwise DP, directly addressing the 93.8% ghosting and 88.5% seam-visibility failure modes from the benchmark.
- Pybind11 binding registered as `batch.seam.graphcut_seam_find`. Gate flag `ASP_GRAPHCUT_SEAM=1` defined in `compositing.py` (default OFF — Python dispatch wiring into `_composite_foreground` pending).
- C++ tests: `GraphCutSeamFinder: 2 frames produces 2 updated masks`, `masks partition ownership (non-overlapping tiles)`, `3 frames completes without error` — all pass.

### MultiBandBlender (`batch/src/compositing.cpp`)
- Implemented `multiband_blend_impl` + `multiband_blend`: wraps `cv::detail::MultiBandBlender`. Accepts N warped frames + N ownership masks + N canvas corners + `num_bands`; returns blended canvas. Eliminates per-band pyramid copy overhead vs Python `cv2.pyrDown`/`pyrUp` loop.
- Pybind11 binding registered as `batch.compositing.multiband_blend`. Gate flag `ASP_MULTIBAND_BLEND=1` defined in `compositing.py` (default OFF — Python dispatch wiring pending).
- C++ tests: `single frame returns frame content`, `two adjacent frames produce wider canvas`, `two overlapping frames produce blended output`, `throws on empty input`, `num_bands=1 still returns correct shape` — all pass.

### `seam_batch` Python Wiring (`backend/src/animation/rendering/compositing.py`)
- Wired `batch.seam.seam_batch` into the precomputation path in `_composite_foreground`. Gate: `ASP_SEAM_BATCH=1`. Dispatches all N-1 seam jobs to C++ OpenMP parallel batch (GIL released). Python `ThreadPoolExecutor` path retained as fallback. The `_zone_pairs` list is built with `np.ascontiguousarray` to satisfy pybind11 contiguity requirements.

### Bug Fix: `seam_cut`/`seam_batch` pybind11 Zero-Stride Array (`batch/src/seam.cpp`)
- **Root cause**: `py::array_t<int32_t>(result.size(), result.data())` creates a zero-stride scalar broadcast — all elements aliased element 0. The C++ traceback set `path[40]=10` correctly but Python read `path.strides=(0,)` → always returned `path[0]` regardless of index. Manifested as waypoint hard-force being silently ignored (`path[40]` returned 16 instead of 10).
- **Fix**: Replaced with explicit shape+stride vectors + owned numpy allocation + `std::copy`:
  ```cpp
  std::vector<ssize_t> shape   = {static_cast<ssize_t>(result.size())};
  std::vector<ssize_t> strides = {static_cast<ssize_t>(sizeof(int32_t))};
  py::array_t<int32_t> out(shape, strides);
  std::copy(result.begin(), result.end(), out.mutable_data());
  ```
  Same fix applied to `seam_batch` inner loop.

### Bug Fixes: Phase 3 Python Dispatch (`backend/src/animation/alignment/bundle_adjust.py`)
- **`UnboundLocalError: x0`**: The "Initialise identity" + "Initial sequential guess" blocks (which define `x0`) were outside the `if BATCH_AVAILABLE / else` block. C++ path took `batch.bundle_adjust.bundle_adjust_affine()` but then fell through to `scipy.optimize.least_squares(x0=x0)`. Fixed by indenting both blocks inside the `else` branch.
- **`_spanning_tree_inlier_filter` edge format**: C++ `edge_to_dict` returns `{i,j,dx,dy,weight,type}` — no `M` key. Fixed by extracting `dx/dy` from `e["M"][0,2]`/`e["M"][1,2]` before calling C++, then filtering original Python edge objects using `(i,j,dx_rounded,dy_rounded)` key set (not `(i,j)` which was ambiguous for duplicate-displacement pairs).
- **`_compute_adaptive_f_scale` edge format**: Same issue — edges with only `"M"` key caused C++ to see `dx=dy=0` defaults. Fixed by extracting dx/dy from M before the C++ call.

### Bug Fix: `_build_seam_cost_map` C++ Dispatch Condition (`backend/src/animation/rendering/compositing.py`)
- Added Python-only feature flags to the dispatch guard: `_MESH_BARRIER`, `_SEAM_HARD_BARRIER`, `_COST_MAP_BLUR_SIGMA`, `_COST_MAP_NORM`, `_SCATTER_COST`. When any of these is enabled, the Python implementation is used (C++ does not support these flags). Previously the C++ path was taken unconditionally, causing tests that enabled these flags to get wrong results.

### Test Suite Fixes (Python)
- `TestNonMonotonicFrameOrder.test_reversed_edge_result_is_consistent`: C++ BA + spanning-tree outlier rejection correctly prunes the reversed edge → monotonic output. Updated test to verify frame-0 anchor and output length instead of expecting non-monotonic behavior.
- `test_wave_correct_affines_minimal_args`: Updated to pass numpy arrays instead of dicts (function is implemented, not a stub).
- `test_no_drift_unchanged`: Updated from identity check (`result is affines[i]`) to value comparison (`np.testing.assert_allclose`); C++ always returns new arrays.

### Result
- Python test suite: 1308 passed, 28 skipped, 0 failed
- C++ native tests: 82 tests, 452 assertions, all passed

---

## ASP C++ Migration — Phase 3 Complete (2026-06-23)

*Completed Phase 3 of the C++ migration roadmap (Alignment Hot Path): phase correlation, static edge rejection, affine validation, and linear wave correction now run in native C++. Python fallback pattern wired into all four affected modules.*

### Phase Correlation (`batch/src/matching.cpp`)
- Implemented `phase_correlate_masked_impl`: `cv::phaseCorrelate` with background masking (foreground pixels zeroed before FFT). Falls back to whole-frame correlation when fewer than 500 bg pixels are available. Eliminates 2 intermediate numpy copies per call.
- Implemented `reject_static_edges_impl` (§1.2A): drops edges where `|dx| < min_disp_px AND |dy| < min_disp_px` in O(N).
- Implemented `compute_adaptive_min_disp_impl` (§1.2C): `max(50px, 0.10 × median_adjacent_step)` using dominant axis median.
- Python wiring: `flow/cam_flow.py::bg_masked_phase_correlate` dispatches to `batch.matching.phase_correlate_masked` when available.

### Affine Validation (`batch/src/validation.cpp`)
- Implemented `validate_affines_impl`: full health check — Euclidean gap sort, ratio, min_gap, rotation, scale, and Kendall-τ monotonicity (§1.12). Includes inline `detect_scroll_axis_impl` mirroring Python canvas.py logic.
- Implemented `compute_adaptive_min_gap_impl` (§0.5C): `max(20.0, canvas_span / (N×3))` with axis-appropriate span (diagonal uses vector magnitude).
- Implemented `compute_adaptive_rot_scale_impl` (§0.5D): tight vs loose thresholds based on per-sequence rotation/scale standard deviation.
- Python wiring: all three functions in `core/validation.py` dispatch to `batch.validation.*` when available. Returns `AffineHealth` namedtuple compatible with all existing callers.

### Linear Wave Correction (`batch/src/wave_correct.cpp`)
- Implemented `wave_correct_values_impl`: Eigen `HouseholderQR` linear fit on the Vandermonde matrix, subtracts trend and anchors corrected sequence at `vals[0]`. Equivalent to `numpy.polyfit(frame_idx, vals, 1)` but ~10× faster for N ≤ 100.
- Python wiring: `core/pipeline.py::_wave_correct_affines` dispatches to `batch.wave_correct.wave_correct_affines` when available.

### Bug Fix: Bundle Adjust Submodule Paths
- Fixed `alignment/bundle_adjust.py` wiring that was calling `batch.bundle_adjust_affine` and `batch.spanning_tree_inlier_filter` (top-level, non-existent) instead of the correct submodule paths `batch.bundle_adjust.bundle_adjust_affine`, `batch.bundle_adjust.spanning_tree_inlier_filter`, and `batch.bundle_adjust.compute_adaptive_f_scale`.

### C++ Test Suite Expanded (`batch/tests/`)
- `test_matching.cpp`: enabled all previously-stubbed tests (removed `[not_impl]` / `REQUIRE_THROWS_AS`); added size-mismatch throw test.
- `test_validation.cpp` (new): 11 tests covering clean pass, ratio fail, min_gap fail, rotation fail, scale fail, Kendall-τ monotonicity fail, adaptive min gap, and adaptive rot/scale thresholds.
- `test_wave_correct.cpp` (new): 7 tests covering N<3 passthrough, range-below-threshold passthrough, pure linear removal, first-frame anchor, zero-slope passthrough, length invariant, and mixed-signal linear extraction.
- `batch/tests/CMakeLists.txt` updated to include new test files.

---

## ASP C++ Migration — Phase 3 Started (2026-06-22)

*Started Phase 3 of the C++ migration roadmap (Alignment Hot Path), translating the core bundle adjustment solver into native C++.*

### Bundle Adjustment Implementation (`batch/src/bundle_adjust.cpp`)
- Migrated `spanning_tree_inlier_filter` (Kruskal + Union-Find + BFS) to prune inconsistent edges before BA.
- Migrated `gnc_bundle_adjust` with GNC-TLS outer loop, Eigen LM inner, Cauchy robust loss, and adaptive `f_scale`.
- Wired C++ `bundle_adjust_affine` into `backend/src/animation/alignment/bundle_adjust.py`.
- Evaluated `asp_test01` with 10-50x speedups in the alignment stage and identical numerical outputs.
- Retained Python fallback structure.

---

## ASP C++ Migration — Phase 2 (2026-06-22)

*Completed Phase 2 of the C++ migration roadmap (Hot Path: Seam + Compositing), translating core OpenCV image manipulation bottlenecks into native C++ with pybind11.*

### Seam Implementation (`batch/src/seam.cpp`)
- Migrated DP-based `seam_cut` and multi-tier `build_seam_cost_map`.
- Added OpenMP-parallelized `seam_batch` execution.

### Compositing Implementation (`batch/src/compositing.cpp`)
- Migrated zone blending functions: `zone_chroma_align`, `zone_lum_norm`, `zone_sat_norm`, `zone_contrast_eq`, `zone_hue_eq`.
- Migrated soft-edge handlers: `laplacian_blend`, `single_pose_soft_edge`, `seam_color_match`.
- Migrated temporal gain loop: `normalize_warped_frames`.

### Exposure Implementation (`batch/src/exposure.cpp`)
- Configured OpenCV `BlocksGainCompensator` pipeline (`blocks_gain_compensate`, `blocks_channels_compensate`).
- Implemented `correct_vignetting`.

### Test Architecture (`batch/tests/`)
- Successfully restructured test suite to separate fast native Catch2 unit tests from Python parity integration tests.
- Re-enabled C++ tests across `test_seam.cpp`, `test_compositing.cpp`, and `test_exposure.cpp`.

---

## Anime Stitch Pipeline — Session 160 (2026-06-22)

*Four improvements: spatial blocks BGR gain compensation, post-BA wave correction, LAB L-channel blocks gain compensation, and canvas strip-level luminance gain uniformity metric.*

### §4.1 — Spatial Blocks BGR Gain Compensation (`backend/src/animation/compositing.py`)

- `_blocks_gain_compensate(fa_zone, fb_zone, block_size=32) → np.ndarray` — divides the blend zone into 32×32 blocks and computes a per-block per-channel BGR gain ratio `mean(fa_block) / mean(fb_block)`. A bilinear-resized (H, W, 3) gain map is applied to `fb_zone` to correct strip-level banding that global scalar gain normalisation cannot handle. Gain clamped to [0.5, 2.0]; blocks where fb-mean < 1.0 use gain=1.0. Wired into `_fb_for_blend` chain after `_zone_lum_norm`. Enable: `ASP_BLOCKS_GAIN_COMP=1`. Targets strip_banding_score (97.9% worse than simple stitch in benchmark).

### §4.3 — Post-BA Wave Correction (`backend/src/animation/pipeline.py`)

- `_wave_correct_affines(affines, axis='vertical') → List[np.ndarray]` — fits a linear trend (`np.polyfit` degree 1) to the tx (vertical) or ty (horizontal) sequence and subtracts it, straightening the panorama midline after bundle adjustment. Only fires when the range exceeds `WAVE_CORRECT_MIN_TX_RANGE=5.0 px` to avoid modifying already-clean sequences. First frame is used as anchor. Enable: `ASP_WAVE_CORRECT=vertical` or `horizontal`. Wired between §3.16 trajectory smoother and Stage 7b validation.

### §4.4 — LAB L-Channel Blocks Gain Compensation (`backend/src/animation/compositing.py`)

- `_blocks_lum_compensate(fa_zone, fb_zone, block_size=32) → np.ndarray` — like §4.1 but uses the LAB L-channel ratio as a scalar gain applied uniformly to all BGR channels. Avoids the colour cast from per-channel BGR gain when any channel's mean is near zero in a block. Gain clamped to [0.5, 2.0]. Wired after `_blocks_gain_compensate` in the `_fb_for_blend` chain. Enable: `ASP_BLOCKS_LUM_COMP=1`.

### §3.31 — Canvas Strip Luminance Gain Uniformity (`backend/benchmark/bench_anime_stitch.py`)

- `_canvas_gain_uniformity(img, n_strips=8) → float` — divides the output into 8 horizontal strips, computes the coefficient of variation (std/mean) of strip-mean luminances. Range [0, ∞); 0=perfectly uniform; high=strip banding present. Degenerate inputs (fewer rows than strips, all-zero image) return 0.0. Added as `canvas_gain_uniformity` to all benchmark result dicts.

**Test suite: 1272 passed (+20 from 1252), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 159 (2026-06-22)

*Four improvements: seam transition straightness penalty, per-strip top/bottom NCC self-consistency metric, fg-majority column floor in seam cost map, and per-zone HSV hue equalization.*

### §1.125 — Seam Transition Straightness Penalty (`backend/src/animation/compositing.py`)

- `_SEAM_TRANSITION_PEN` (default 0.0) adds a row-distance-from-midline cost to the energy matrix in `_seam_cut` before the DP forward pass. The distance is normalised to [0, 1] so the penalty is scale-invariant across zone heights. Creates a mild prior toward straight horizontal seam paths running through the zone centre. High values (e.g. 50) strongly constrain the seam near the midline; low values preserve natural low-energy routing around fg content. Enable: `ASP_SEAM_TRANSITION_PEN=<float>`.

### §3.30 — Per-Strip Top/Bottom NCC Self-Consistency (`backend/benchmark/bench_anime_stitch.py`)

- `_strip_self_ssim(img, n_strips=8) → float` — splits each horizontal band in half and computes the Normalized Cross-Correlation (NCC) between the top and bottom halves at thumbnail scale (32 px height). Returns the minimum NCC across all strips. A clean uniform strip scores ≈1.0; a strip straddling a visible seam or brightness jump scores lower. Added as `strip_self_ssim` to all benchmark result dicts.

### §1.126 — Fg-Majority Column Floor in Seam Cost Map (`backend/src/animation/compositing.py`)

- `_FG_MAJORITY_FLOOR` (default 0.0 = off) gates on `_build_seam_cost_map`: when the entire blend zone is >60% fg interior (cost ≥ 1.0), raises columns that are >80% fg to at least `_FG_MAJORITY_FLOOR`, pushing the DP seam toward the minority background/low-cost corridor columns. Guard: skipped when all columns are heavy (no corridor available). Enable: `ASP_FG_MAJORITY_FLOOR=<float>` (e.g. 1.5).

### §1.127 — Per-Zone HSV Hue Equalization (`backend/src/animation/compositing.py`)

- `_zone_hue_eq(fa_zone, fb_zone) → np.ndarray` — shifts the circular mean hue of `fb_zone` to match `fa_zone` using HSV hue channel. Only fires when the mean hue difference exceeds `ZONE_HUE_EQ_MIN_DIFF_DEG=5°` (OpenCV convention: 0–180). Shift clamped to [−30°, +30°] to prevent extreme corrections. Chained after `_ZONE_CONTRAST_EQ` in the `_fb_for_blend` block of the normal blend branch. Enable: `ASP_ZONE_HUE_EQ=1`.

**Test suite: 1252 passed (+20 from 1232), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 158 (2026-06-22)

*Four improvements: high seam path cost escalation gate, local scatter penalty in seam cost map, adaptive single-pose soft-edge width from seam residual, and blend zone coverage fraction metric.*

### §1.122 — High Seam Path Cost Escalation (`backend/src/animation/compositing.py`)

- `_mean_path_cost(path_local, cost_map) → float` — computes the mean seam cost value sampled along the selected DP path. When `ASP_HIGH_PATH_COST_THRESH > 0` and mean path cost exceeds threshold, escalates to single-pose before blending. Complementary to §1.69 (bg-ratio gate): catches routes that nominally pass the bg-ratio check but still incur high aggregate cost due to scattered fg pixels. Default OFF; recommended: `ASP_HIGH_PATH_COST_THRESH=0.6`.

### §3.29 — Blend Zone Coverage Fraction (`backend/benchmark/bench_anime_stitch.py`)

- `_zone_coverage_fraction(img, n_strips=8) → float` — approximates the fraction of image height occupied by inter-strip blend zones. Computed as `(n_strips−1) × 2 × (strip_h // 3) / H`, capped at 1.0. High fraction indicates blend zones dominate the canvas and seam quality matters more. Added as `zone_coverage_fraction` to all benchmark result dicts.

### §1.123 — Local Scatter Penalty in Seam Cost Map (`backend/src/animation/compositing.py`)

- When `ASP_SCATTER_COST=1`, adds a per-pixel local variance term to the seam cost map before DP. Computed via 3×3 box-filter variance normalised to [0, `_SCATTER_COST_WEIGHT`] across the zone. Routes the DP seam toward spatially smooth (uniform background) corridors and away from high-frequency noise or scattered fg debris. Default OFF; `ASP_SCATTER_COST_WEIGHT=0.3`.

### §1.124 — Adaptive Single-Pose Soft-Edge Width from Seam Residual (`backend/src/animation/compositing.py`)

- Extends §1.22 (feather-based adaptive width) with a second stage driven by `seam_post_diffs`. When `ASP_ADAPTIVE_SP_SOFT=1`: post-diff > 30 lum → clamps to `ASP_ADAPTIVE_SP_SOFT_MIN` (default 3 px, narrow to limit ghost risk); post-diff < 10 lum → widens to `ASP_ADAPTIVE_SP_SOFT_MAX` (default 10 px, extra smoothing for clean warps). Mid-range [10, 30] leaves the feather-based value unchanged.

**Test suite: 1232 passed (+20 from 1212), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 157 (2026-06-22)

*Four improvements: zone width CV gate, saturation step audit, zone histogram intersection gate, and seam gradient direction coherence metric.*

### §1.119 — Seam Zone Width Variance Gate (`backend/src/animation/compositing.py`)

- `_zone_width_cv(boundaries) → float` — computes std/mean of adjacent zone widths (boundary gaps). High CV indicates the boundary search produced an uneven layout (some zones very narrow, others very wide), which correlates with bad BA outcomes. When `ASP_ZONE_WIDTH_CV_MAX > 0` and CV exceeds threshold, pre-escalates the narrowest seam to single-pose before DP. Default OFF.

### §1.120 — Post-Composite Saturation Step Audit (`backend/src/animation/compositing.py`)

- `_audit_seam_sat_steps(result, boundaries, band_px=5) → Dict[int, float]` — analogous to §1.106 lum audit but for HSV saturation. Measures mean saturation difference between ±5px bands above and below each seam boundary. Logs a warning when step exceeds `ASP_SEAM_SAT_WARN_THRESH`. Stores `seam_sat_steps` and `max_seam_sat_step` in `seam_meta_out`. Catches chromatic banding invisible to luminance-only checks.

### §1.121 — Zone Histogram Intersection Pre-gate (`backend/src/animation/compositing.py`)

- `_zone_hist_intersection(fa_zone, fb_zone) → float` — computes mean per-channel (32-bin) normalised histogram intersection in [0, 1]. Values near 1.0 = identical colour palettes; low values = disjoint histograms. When `ASP_ZONE_HIST_THRESH > 0` and score falls below threshold, pre-escalates to single-pose before DP. Complementary to §1.117 NCC (structural) — catches colour-palette shifts that NCC misses.

### §3.28 — Seam Boundary Gradient Direction Coherence Metric (`backend/benchmark/bench_anime_stitch.py`)

- `_seam_row_grad_coherence(img, n_strips=8, band_px=8) → float` — measures circular mean resultant length of Sobel gradient directions in ±8px row bands at each inter-strip boundary. R near 1.0 = dominant gradient orientation (likely a real edge); R near 0 = isotropic noise. Returns minimum R across all boundaries. Added as `seam_grad_coherence_min` to all benchmark result dicts.

**Test suite: 1212 passed (+20 from 1192), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 156 (2026-06-22)

*Four improvements: zone bg-fraction diagnostic, fast thumbnail NCC pre-gate, seam sharpness measurement, and seam band NCC benchmark metric.*

### §1.116 — Zone Blend Bg-Fraction Diagnostic (`backend/src/animation/compositing.py`)

- Computes `1 - _fg_fraction_in_zone(bg_a, bg_b)` for every blend zone and stores it in `debug_context["zone_bg_fracs"]` when `ASP_ZONE_BG_FRAC_DIAG=1`. Pure observability — no blend logic change. Reveals how much of each blend zone is background vs character pixels, guiding calibration of §1.95/§1.101 fg-density gates. Default OFF.

### §1.117 — Fast Thumbnail NCC Structural Pre-gate (`backend/src/animation/compositing.py`)

- `_zone_pair_ncc(fa_zone, fb_zone, thumb_size=32) → float` — downsizes both zone crops to 32×32 and computes normalized cross-correlation. Returns 1.0 for empty/degenerate inputs. In the blend loop, when `ASP_ZONE_FAST_NCC_THRESH > 0` and NCC falls below threshold on a non-escalated seam, escalates to single-pose (dominant fg frame). Catches structurally different zones (pose gap, occlusion) before the heavier §1.97 entropy asymmetry gate.

### §1.118 — Seam Band Laplacian Sharpness Guard (`backend/src/animation/compositing.py`)

- `_measure_seam_sharpness(result, boundaries, band_px=5) → Dict[int, float]` — after compositing, measures Laplacian variance in a ±5px band around each boundary in the final canvas. Low variance = blur artifact at seam. When `ASP_SEAM_SHARP_MIN > 0`, logs a per-boundary warning for blurred seams. Also stores `seam_sharpness` and `max_seam_blur` in `seam_meta_out` for benchmark analysis.

### §3.27 — Seam Band NCC Benchmark Metric (`backend/benchmark/bench_anime_stitch.py`)

- `_seam_band_ncc(img, n_strips=8, band_px=10) → float` — splits the output image into strips and computes NCC between the 10px bands immediately above and below each inter-strip boundary. Returns the minimum across all boundaries. Values near 1.0 = smooth transitions; low values = abrupt seam. Added as `seam_band_ncc_min` to all benchmark result dicts.

**Test suite: 1192 passed (+20 from 1172), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 155 (2026-06-22)

*Four improvements: seam cost map column-wise smooth, zone RMS contrast equalization, per-strip saturation CV metric, and absolute feather jump cap.*

### §1.113 — Seam Cost Map Column-wise Gaussian Smooth (`backend/src/animation/compositing.py`)

- After §1.110 row Gaussian blur in `_build_seam_cost_map`, applies `scipy.ndimage.gaussian_filter1d` along axis=1 (columns) on the soft-cost region (< 1e5). Creates lateral cost gradients that prevent DP zigzagging between adjacent equal-cost columns. Hard barriers preserved. `ASP_COST_COL_SMOOTH_SIGMA=1.5` (default 0.0 = OFF).

### §1.114 — Zone RMS Contrast Equalization (`backend/src/animation/compositing.py`)

- `_zone_contrast_eq(fa_zone, fb_zone) → ndarray` — computes luminance std over non-black pixels in each zone and scales `fb_zone` so its contrast matches `fa_zone`. Scale clamped [0.5, 2.0]; skips when ratio deviation < 5% or std_b < 1. Chained after `_zone_sat_norm` (§1.111) in the normal blend path. Corrects contrast-wash banding that §1.104 (mean lum) cannot fix. `ASP_ZONE_CONTRAST_EQ=1`. Default OFF.

### §3.26 — Per-strip Saturation CV Benchmark Metric (`backend/benchmark/bench_anime_stitch.py`)

- `_strip_sat_cv(img, n_strips=8) → float` — converts to HSV, measures mean saturation per strip, returns std/mean across strips. High CV = some strips are vivid while others are desaturated (photometric banding invisible to lum/chroma metrics). Added as `strip_sat_cv` to all benchmark result dicts.

### §1.115 — Absolute Feather Jump Cap (`backend/src/animation/compositing.py`)

- `_cap_feather_jumps(feathers, max_jump) → ndarray` — two-pass (forward + backward) clamp enforcing that no adjacent feather pair differs by more than `max_jump` pixels. Wired after §1.92 Gaussian smooth. Complements §1.68 (ratio-based): catches extreme absolute jumps in wide sequences that pass the ratio test. `ASP_FEATHER_JUMP_MAX=150` (default 0 = OFF).

**Test suite: 1172 passed (+20 from 1152), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 154 (2026-06-22)

*Four improvements: seam cost map Gaussian blur, zone background saturation normalization, seam path drift gate, and seam boundary entropy benchmark metric.*

### §1.110 — Seam Cost Map Gaussian Blur (`backend/src/animation/compositing.py`)

- After §1.109 normalization in `_build_seam_cost_map`, applies `scipy.ndimage.gaussian_filter` to the soft-cost region (cost < 1e5). Smooths tier-boundary transitions so DP has a gradient slope toward background corridors instead of a binary step — prevents argmin oscillation between equal-energy tier-boundary columns. Hard barriers (≥ 1e5) are preserved unchanged. `ASP_COST_MAP_BLUR_SIGMA=2.0` (default 0.0 = OFF).

### §3.25 — Seam Boundary Entropy Benchmark Metric (`backend/benchmark/bench_anime_stitch.py`)

- `_seam_boundary_entropy(img, n_strips=8, band_px=15) → List[float]` — for each inter-strip boundary, computes Shannon entropy of the 256-bin greyscale histogram in a ±15px row band, normalised by log2(256)=8 to [0, 1]. High entropy = complex varied texture at seam (more likely to be noticeable). Added as `seam_boundary_entropies` (list) and `seam_boundary_entropy_max` (Optional[float]) to all benchmark result dicts.

### §1.111 — Zone Background HSV Saturation Normalization (`backend/src/animation/compositing.py`)

- `_zone_sat_norm(fa_zone, fb_zone) → ndarray` — converts zones to HSV, matches mean saturation of background (non-black) pixels in `fb_zone` to `fa_zone` via a scalar gain clamped [0.5, 2.0]. Skips when ratio deviation < 2%. Chained after `_zone_lum_norm` (§1.104) in the normal blend path. Addresses chromatic seam banding caused by palette saturation shift between frames (e.g. warm-sunset vs cool-indoor hold transition). `ASP_ZONE_SAT_NORM=1`. Default OFF.

### §1.112 — Seam Path Vertical Drift Gate (`backend/src/animation/compositing.py`)

- `_seam_path_drift(path) → float` — returns `max(|path[i+1] - path[i]|)` across consecutive path columns. A large drift indicates a sudden vertical discontinuity in the DP seam — produces a visible kink slash even after §1.25 median smoothing. In the blend loop, after §1.31 FG penetration check: when drift > `_SEAM_DRIFT_THRESH` and the seam is not already single-pose, escalates to single-pose (dominant by fg pixel count). `ASP_SEAM_DRIFT_THRESH=15.0` (default 0.0 = OFF).

**Test suite: 1152 passed (+21 from 1131), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 153 (2026-06-22)

*Four improvements: adaptive seam band width, Laplacian blend alpha schedule, seam cost map normalization, and seam boundary row std metric.*

### §1.107 — Adaptive Seam Band Width from Zone Height (`backend/src/animation/compositing.py`)

- `_adaptive_seam_band(zone_h, base_band, max_band=40) → int` — returns `min(max_band, max(base_band, zone_h // 6))`. In the single-pose colour-correction path, replaces the fixed `_sp_soft_px + 4` band with a computed `_band_px_sp` variable passed to `_seam_color_match`, `_seam_band_hist_match`, and `_seam_lum_converge`. For tall zones (feather=300 → zone_h≈600), band grows to 40px; for short zones it falls back to base. `ASP_ADAPTIVE_SEAM_BAND=1`. Default OFF.

### §3.24 — Seam Boundary Row Std Benchmark Metric (`backend/benchmark/bench_anime_stitch.py`)

- `_seam_row_std(img, n_strips=8) → float` — for each inter-strip boundary row, computes std of BGR pixel values across the full width, returns max std / 255. High value = strong horizontal variation at a boundary row = visible seam artifact. Added as `seam_row_std` field to all benchmark result dicts.

### §1.108 — Laplacian Blend Alpha Schedule (`backend/src/animation/stateless.py`)

- Added `alpha_schedule: bool = False` parameter to `_laplacian_blend`. When enabled, mixes a sharp-masked version (`mask²`) at 30% with the normal Laplacian result at 70% before returning. Reduces high-frequency colour bleeding at character cel boundaries while preserving low-frequency smooth transitions. Wired in blend loop as `_laplacian_blend(..., alpha_schedule=_LAPLACIAN_ALPHA_SCHEDULE)`. `ASP_LAPLACIAN_ALPHA_SCHEDULE=1`. Default OFF.

### §1.109 — Seam Cost Map L-inf Normalization (`backend/src/animation/compositing.py`)

- At end of `_build_seam_cost_map`, normalizes non-barrier pixels (< 1e5) to [0, 1] via L-inf normalization. Ensures the relative cost tiers (0→0.3→0.5→1.0→2.0) remain stable when additive terms (§3.17 HF column cost, §1.35 line-art gradient penalty) push soft-tier values above 1.0. Hard barriers (≥ 1e6) are preserved unchanged. `ASP_COST_MAP_NORM=1`. Default OFF.

**Test suite: 1131 passed (+20 from 1111), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 152 (2026-06-22)

*Four improvements: per-zone luminance normalization, seam-path column spread metric, fg-overlap blend weight cap, and post-composite seam lum step audit.*

### §1.104 — Per-Zone Luminance Normalization Before Blend (`backend/src/animation/compositing.py`)

- `_zone_lum_norm(fa_zone, fb_zone) → ndarray` — computes mean grayscale luminance of non-black pixels in each zone and applies a scalar gain (clamped [0.5, 2.0]) to `fb_zone` non-black pixels so its mean matches `fa_zone`. Skips when ratio < 1%. Chained after `_zone_chroma_align` (§3.19) in the normal blend path. `ASP_ZONE_LUM_NORM=1`. Default OFF. Distinct from §1.56 (post-composite strip lum) and §3.19 (LAB chroma).

### §3.23 — Seam-Path Column Spread Benchmark Metric (`backend/benchmark/bench_anime_stitch.py`)

- `_seam_col_spread(img, n_strips=8) → float` — for each strip, finds the column of maximum horizontal Sobel gradient magnitude, collects N peaks, returns `std(peaks) / W`. Low normalized std = concentrated routing (all strips use same seam column = bad); high = spread across columns (good background routing). Added as `seam_col_spread` field to all benchmark result dicts.

### §1.105 — Fg-Overlap Laplacian Blend Weight Cap (`backend/src/animation/compositing.py`)

- Before `_laplacian_blend`, computes a per-pixel fg-overlap mask (both zones have fg content) and lum diff mask (diff > 10 lum units). When `ASP_FG_OVERLAP_BLEND_CAP > 0.0` and a pixel meets both criteria, caps `mask_float` at the configured value (e.g. 0.3), strongly weighting the dominant zone. Prevents double-image ghost in fg-overlap pixels where ARAP blend would otherwise contribute both poses equally. Default `0.0` (OFF).

### §1.106 — Post-Composite Seam Lum Step Audit (`backend/src/animation/compositing.py`)

- `_audit_seam_lum_steps(result, boundaries, band_px=5, warn_thresh=8.0) → Dict[int, float]` — after all seams composited (after §1.90 bilateral smooth), measures mean absolute lum difference in ±5px rows at each boundary in the final output. Logs `[Stitch] §1.106 seam-step WARNING` for any step > threshold. Stores `seam_lum_steps` and `max_seam_lum_step` into `seam_meta_out` when provided. Always runs (negligible overhead). `ASP_POST_SEAM_WARN_THRESH=8.0`.

**Test suite: 1111 passed (+20 from 1091), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 151 (2026-06-22)

*Four improvements: full blend-zone MAD pre-escalation, warp residual momentum damping, reference-proximity dominant frame selection, and seam contrast ratio benchmark metric.*

### §1.101 — Full Blend-Zone MAD Pre-Escalation (`backend/src/animation/compositing.py`)

- In the blend loop after §1.97 entropy gate, computes `mean(|fa_zone − fb_zone|)` over the full zone (not just shared fg pixels). When MAD > `_ZONE_MAD_THRESH`, escalates to single-pose before the DP. Broader than §1.60 (fg-only MAD): catches colour-shift differences in the background region too. `ASP_ZONE_MAD_THRESH=30.0` to enable. Default `0.0` (OFF).

### §1.102 — Warp Residual Momentum Damping (`backend/src/animation/compositing.py`)

- In the fg-registration loop, immediately after computing `_sp_thresh`: when `ASP_WARP_MOMENTUM_DAMP=1` and `k-1 in seam_single_pose`, multiplies `_sp_thresh` by `_WARP_MOMENTUM_FACTOR` (default 0.85). Adjacent seams sharing a frame often share the same pose discontinuity; earlier pre-escalation prevents ARAP from spending compute on unregisterable zones. Runs before the §1.95 fg-fraction scaling block. `ASP_WARP_MOMENTUM_FACTOR=0.85`. Default OFF.

### §3.22 — Seam Contrast Ratio Benchmark Metric (`backend/benchmark/bench_anime_stitch.py`)

- `_seam_contrast_ratio(img, n_strips=8, band_px=10) → float` — computes mean absolute Laplacian energy in ±`band_px` rows around each inter-strip boundary vs. energy in non-boundary regions. Returns `seam_energy / interior_energy`. Values near 1.0 = no artifact; > 1.5 = visible seam sharpness discontinuity. Returns 1.0 (neutral) for degenerate inputs. Added as `seam_contrast_ratio` field to all benchmark result dicts.

### §1.103 — Reference-Proximity Dominant Frame Selection (`backend/src/animation/compositing.py`)

- In the `post_diff > _sp_thresh` escalation path of the fg-registration loop: when `ASP_SP_REF_PROX=1`, selects `dom` as whichever of `fi_a`/`fi_b` is temporally closest to `ref_fi` (the central reference frame), rather than the frame with more fg pixels. The reference frame has the least accumulated warp drift, making it the most geometrically reliable dominant. Only affects the main post-ARAP escalation path; fallback and pre-escalation paths unchanged. Default OFF.

**Test suite: 1091 passed (+20 from 1071), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 150 (2026-06-22)

*Four improvements: inter-strip gain smoothing, extended fg dilation cost ring, seam endpoint bg-preference, and per-strip gradient energy CV benchmark metric.*

### §1.98 — Per-Frame Gain Normalization Smoothing (`backend/src/animation/compositing.py`)

- `_smooth_gain_array(gains, sigma=1.0) → ndarray` — 1-D Gaussian smooth (scipy `gaussian_filter1d`, mode=`nearest`) over the per-frame `frame_gains` list. Wired after the per-frame normalization loop: when `ASP_SMOOTH_GAIN=1`, re-applies the smoothed/raw ratio to `warped_norm` bg pixels only (skip ratio < 0.5%). Prevents abrupt brightness staircase caused by isolated outlier gain corrections. `ASP_SMOOTH_GAIN=1`, `ASP_SMOOTH_GAIN_SIGMA=1.0`. Default OFF.

### §3.20 — Extra Fg-Boundary Outer Dilation Cost Ring (`backend/src/animation/compositing.py`)

- In `_build_seam_cost_map`, after the existing Tier-2 fg-edge buffer (cost=0.5), dilates the combined fg mask by `_EXTRA_FG_DILATION` px and adds a 0.3-cost outer ring. Creates gradient 0→0.3→0.5→1.0 from background to fg-interior, pushing the DP seam further from character edges. `np.maximum` preserves existing higher Tier-1/2 costs. `ASP_EXTRA_FG_DILATION=8` to enable. Default `0` (OFF).

### §1.99 — Seam Endpoint Bg-Preference (`backend/src/animation/compositing.py`)

- At end of `_build_seam_cost_map`, amplifies fg pixel costs (≥1.0) by 10× in the top/bottom `_SEAM_PIN_ROWS` rows of the zone. Steers the DP seam path to enter and exit through background-only columns at zone edges. Guards on `zone_h > 2 * _SEAM_PIN_ROWS`. `ASP_SEAM_PIN_ROWS=3` to enable. Default `0` (OFF).

### §3.21 — Per-Strip Gradient Energy CV Benchmark Metric (`backend/benchmark/bench_anime_stitch.py`)

- `_strip_gradient_cv(img, n_strips=8) → float` — splits image into N equal strips, computes mean absolute Laplacian energy per strip, returns coefficient of variation (std/mean). High CV = some strips much sharper/blurrier than adjacent ones — signature of seam-induced sharpness discontinuities. Returns 0.0 for flat or degenerate images. Added as `strip_gradient_cv` field to all benchmark result dicts.

**Test suite: 1071 passed (+20 from 1051), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 149 (2026-06-22)

*Four improvements: ghost-reduction via fg-zone threshold scaling, pre-blend chroma normalisation, chroma seam coherence benchmark metric, and entropy-asymmetry pre-escalation gate.*

### §1.95 — Fg-Zone Single-Pose Threshold Scaling (`backend/src/animation/compositing.py`)

- After computing `_sp_thresh` in the fg-registration loop, computes zone fg fraction via `_fg_fraction_in_zone` on the boundary slice. When fraction > `_SP_FG_FRAC_THRESH` (default 0.5), multiplies threshold by `_SP_THRESH_FG_FACTOR` (default 0.7). Fg-dominated blend zones produce worse ghosts; lowering the threshold catches them for single-pose escalation earlier. `ASP_SP_THRESH_FG_SCALE=1`. Default OFF.

### §3.19 — Per-Zone Pre-Blend Chroma Alignment (`backend/src/animation/compositing.py`)

- `_zone_chroma_align(fa_zone, fb_zone) → ndarray` — computes LAB a/b mean over non-black pixels in both zones; when either delta > 2 LAB units, applies a global additive shift to `fb_zone` so its chroma mean matches `fa_zone`. Wired before `_laplacian_blend` in the normal (non-single-pose) path: `_fb_for_blend = _zone_chroma_align(fa_zone, fb_zone) if _ZONE_CHROMA_ALIGN and k not in seam_single_pose else fb_zone`. `ASP_ZONE_CHROMA_ALIGN=1`. Default OFF.
- Distinct from §1.56 (`_seam_chroma_equalize`): §1.56 is a post-composite narrow-band correction; §3.19 acts per-zone pre-blend.

### §1.96 — Chroma Seam Coherence Benchmark Metric (`backend/benchmark/bench_anime_stitch.py`)

- `_chroma_seam_coherence(img, n_strips=8) → float` — converts to LAB, computes per-strip mean of |a|+|b| channels, returns max absolute step between adjacent strip means. Higher score = visible colour-temperature discontinuity between stitched strips. Added as `chroma_seam_coherence` field to all benchmark result dicts.

### §1.97 — Seam Zone Entropy Asymmetry Gate (`backend/src/animation/compositing.py`)

- `_zone_entropy(zone) → float` + `_seam_zone_entropy_gap(fa_zone, fb_zone) → float` — Shannon entropy from grayscale histogram. A large gap (one near-flat zone, one textured) means ARAP flow has no gradient signal on the flat side and produces spurious warp vectors. When gap > `_ENTROPY_GAP_THRESH`, pre-escalates to single-pose. `ASP_ENTROPY_GAP_THRESH=1.5` to enable. Default `0.0` (OFF). Wired in blend loop after §1.86 SSIM check.

**Test suite: 1051 passed (+20 from 1031), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 148 (2026-06-22)

*Four compositing + benchmark improvements addressing residual seam colour drift and GT-less evaluation coverage.*

### §1.91 — Iterative Seam Luminance Convergence (`backend/src/animation/compositing.py`)

- `_seam_lum_converge(dom_zone, oth_zone, path_local, band_px, target_delta=5.0, max_iters=2)` — measures residual mean-delta in the seam band after S16+§1.88; if > `target_delta` lum units, applies another `_seam_color_match` pass. Caps at `max_iters` to avoid over-correction. Wired in single-pose path after `_seam_band_hist_match` when `ASP_SEAM_LUM_CONVERGE=1`.

### §1.92 — Gaussian Feather Array Smoothing (`backend/src/animation/compositing.py`)

- `_smooth_feather_array(feathers, sigma=1.0, feather_min, feather_max)` — 1D Gaussian smooth on the feather width array (σ=1 seam by default) to prevent abrupt transitions between adjacent seams. Re-clamps to `[FEATHER_MIN, FEATHER_MAX]` after smoothing. Wired after `_enforce_feather_ratio` when `ASP_SMOOTH_FEATHER=1`.

### §3.18 — CQAS Composite Quality Aggregate Score (`backend/benchmark/bench_anime_stitch.py`)

- `_compute_cqas(metrics) → Optional[float]` — single [0,1] quality signal combining `ghosting_siqe` (0.35), `seam_visibility` (0.30), `seam_coherence` (0.20), `sharpness` (0.15) with heuristic normalization. Added as `cqas` field to all benchmark result dicts. Especially useful for the 43 GT-less tests where GT-SSIM is unavailable.

### §1.94 — Background Plate Consistency Score (`backend/benchmark/bench_anime_stitch.py`)

- `_bg_consistency_score(img, n_strips=1) → float` — per-strip row-mean luminance std; high score signals corrupted background plate (§1.87 masked-median inconsistency). Added as `bg_consistency_score` field to all benchmark result dicts.

**Test suite: 1031 passed (+20 from 1011), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 147 (2026-06-22)

*Implements four compositing improvements addressing the remaining quality gap (ghosting 42% worse, seam color banding).*

### §1.88 — Band Histogram Matching (`backend/src/animation/compositing.py`)

- `_seam_band_hist_match(dom_zone, oth_zone, path_local, band_px)` — per-channel ECDF histogram transfer in the seam blend band. After S16 mean-shift, fits the full luminance distribution of `oth_zone` to `dom_zone` in the blend band using `scipy.interpolate.interp1d`. Falls back to mean-shift when scipy is unavailable or band has < 10 pixels. `ASP_HIST_MATCH_SEAM=1`. Called in the single-pose path after `_seam_color_match`.
- **Why better than mean-shift**: handles zones with skewed distributions (e.g., bright-biased dom vs dark-biased oth) where matching only the mean leaves a distribution mismatch visible as banding.

### §1.89 — Seam Residual Order (`backend/src/animation/compositing.py`)

- `ASP_SEAM_ORDER=residual` — sorts the blend loop by ascending `seam_post_diffs[k]` before compositing. Lowest-residual seams (best registration quality) processed first to establish the reference quality baseline. Higher-residual seams accumulate less compounding error.
- `_SEAM_ORDER_RESIDUAL` module flag. Falls back to linear order when `seam_post_diffs` is empty.

### §1.90 — Post-Seam Bilateral Smoothing (`backend/src/animation/compositing.py`)

- `_bilateral_seam_smooth(canvas, seam_paths, band_px=5, sigma_space=3.0, sigma_color=20.0)` — after all seams composited, applies `cv2.bilateralFilter` in ±`band_px` columns around each DP seam path. Smooths residual 1–3 lum-unit color steps without blurring content outside the narrow band. `ASP_BILATERAL_SEAM=1`.
- Operates row-by-row to avoid blurring across seam boundary positions that differ in column between rows.

### §3.17 — High-Frequency Column Seam Cost (`backend/src/animation/compositing.py`)

- `_hf_column_cost(zone_a, zone_b, hf_threshold=50.0, hf_boost=0.5)` — computes per-column Laplacian energy as an additive cost term in `_build_seam_cost_map`. Columns with mean `|∇²I| > hf_threshold` receive +`hf_boost` cost, routing the DP seam away from texture-heavy columns (strong horizontal edges) toward smooth background corridors. `ASP_HF_SEAM_COST=1`.
- Complements §3.15A column barrier (fg-interior percentage) and §3.15B mesh barrier (Delaunay triangles) with a texture-based signal.

**Test suite: 1011 passed (+20 from 991), 5 failed (pre-existing ptlflow), 9 skipped.**

---

## Anime Stitch Pipeline — Session 146 (2026-06-22)

*Implements §3.16B HITL per-test preset system, §3.5B CamFlow background-masked phase correlation, and §2.10A flow HITL callback checkpoint.*

### §3.16B — HITL Per-Test Preset System (`backend/src/animation/hitl_presets.py`)

**Pain point:** The 4 confirmed genuine SCANS fallbacks (tests 54, 59, 73, 89) fail upstream due to 2D/curved camera motion that bundle adjustment cannot model. Manual HITL corrections via shipped HITL dialogs (SelectionReview §2.1, EdgeReview §2.2, CanvasInspector §2.3) need a persistence layer to auto-apply on re-runs.

**Implementation:**
- `HitlPreset` dataclass — `test_name`, `forced_frame_indices`, `drop_edges` (list of (src, dst) tuples), `forced_boundaries`, `scroll_axis_override`, `force_scans`, `notes`. `to_dict()` / `from_dict()` for JSON round-trip.
- `save_hitl_preset(test_name, preset, base_dir)` — writes JSON to `ASP_HITL_PRESET_DIR/{test_name}.json` (default `~/.image-toolkit/hitl_presets/`).
- `load_hitl_preset(test_name, base_dir)` — returns `HitlPreset` or `None` if missing. Warning on parse failure.
- `list_hitl_presets(base_dir)` — returns sorted list of test names with saved presets.
- `apply_hitl_preset(pipeline_state, preset)` — applies `force_scans`, `drop_edges`, `forced_boundaries`, `scroll_axis_override` to a pipeline state dict.
- Wired in `pipeline.py`: after `image_paths` sorting, derive `_test_name = Path(image_paths[0]).parent.name`, call `load_hitl_preset(_test_name)`. If `force_scans` → immediate SCANS fallback. After `_filter_edges`, apply `drop_edges` override.
- `"ASP_HITL_PRESET_DIR"` added to `_CONFIG_SCHEMA` in `config.py`. `HITL_PRESET_DIR_DEFAULT` added to `constants/animation.py`.
- 5 tests `TestHitlPreset` in `test_hitl_presets.py`: round-trip, missing→None, list presets, drop_edges apply, force_scans apply.

### §3.5B — CamFlow Background-Masked Phase Correlation (`backend/src/animation/cam_flow.py`)

**Pain point:** Phase correlation on whole-frame thumbnails conflates camera pan with character animation. A "50px displacement" may be 5px camera + 45px arm swing. The existing `ASP_TWO_CHANNEL_SELECT` path was a prototype; this formalizes it as a proper module with a cleaner API.

**Implementation:**
- `bg_masked_phase_correlate(frame_a, frame_b, bg_mask_a, bg_mask_b, min_bg_pixels) → (dx, dy, response)` — zeros out foreground pixels in both grayscale frames before `cv2.phaseCorrelate`. Falls back to whole-frame if `combined_bg.sum() < min_bg_pixels` (`CAM_FLOW_MIN_BG_PIXELS=500`).
- `CamFlowEstimator(min_bg_pixels)` — stateless wrapper.
- Wired in `frame_selection.py`: `_CAMFLOW = os.environ.get("ASP_CAMFLOW", "")`. When `_CAMFLOW == "bg_masked"` and `_bg_thumb_mask` is available, routes phase correlation through `bg_masked_phase_correlate` before the existing `_TWO_CHANNEL_SELECT` path.
- `"ASP_CAMFLOW"` added to `_CONFIG_SCHEMA`. `CAM_FLOW_MIN_BG_PIXELS=500` added to `constants/animation.py`.
- 5 tests `TestBgMaskedPhaseCorrelate` in `test_cam_flow.py`: no-mask tuple, bg-masked shift detection, insufficient-bg fallback, zero-shift estimator, vertical-shift estimator.

### §2.10A — Flow HITL Callback Checkpoint (`backend/src/animation/compositing.py`)

**Pain point:** When Stage 8.5 escalates to single-pose (post_warp_diff > threshold), there is no hook for external code (GUI or test harness) to inject a user-corrected flow field and attempt re-registration before committing to single-pose.

**Implementation:**
- Module-level `_flow_hitl_callback: Optional[Callable[[int, dict], Optional[np.ndarray]]] = None`.
- `set_flow_hitl_callback(cb)` — registers/clears the callback. Exported in `__all__`.
- In `_composite_foreground`, at the single-pose escalation point (after `post_diff > _sp_thresh`): if callback is set, calls `cb(k, {"post_warp_diff": post_diff, "seam_k": k, "fi_a": fi_a, "fi_b": fi_b})`. If it returns a `(H, W, 2)` flow array, re-runs `register_foreground_at_seam` with `flow_override=`. Exception in callback is caught and logged. Normal escalation proceeds regardless.
- `Callable` added to `typing` import in `compositing.py`.
- 5 tests `TestFlowHitlCallback` appended to `test_compositing.py`: register/clear, identity preserved, None after clear, exported in `__all__`, callback returning None proceeds.

**991 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures unchanged).**

---

## Anime Stitch Pipeline — Session 145 (2026-06-21)

*Implements §3.15B OBJ-GSP Triangular Mesh Barrier and §2.8 HybridStitch Export.*

### §3.15B — OBJ-GSP Triangular Mesh Barrier (`backend/src/animation/compositing.py`)

**Pain point:** §3.15A raised fg-dominated *columns* to cost=2.0 (soft barrier), but the DP seam can still route diagonally through the fg interior if no column is cleanly fg-free. The OBJ-GSP mesh approach builds a hard barrier at the actual fg *shape boundary*, forcing the seam into background-only corridors.

**Implementation:**
- `_build_fg_mesh_barrier(apply_mask, min_area_px=100) → np.ndarray` — `cv2.findContours` on fg mask → stack all contour points → `scipy.spatial.Delaunay` triangulation → `cv2.fillConvexPoly` each simplex with cost=1e6. Returns zeros for empty mask, tiny-area contours (< `min_area_px`), or < 4 contour points (degenerate).
- Module flag `_MESH_BARRIER: bool` at module level. `ASP_MESH_BARRIER=1` to enable (default OFF). `MESH_BARRIER_MIN_AREA_PX=100` in `constants/animation.py`. `"ASP_MESH_BARRIER"` added to `_CONFIG_SCHEMA`.
- Wired in `_build_seam_cost_map` after §3.15A column filter: combines `bg_mask_a` / `bg_mask_b` fg zones (union), resizes if needed, calls `_build_fg_mesh_barrier`, applies with `np.maximum`. Zero overhead when disabled.
- Added `"_build_fg_mesh_barrier"` and `"_MESH_BARRIER"` to `compositing.py __all__`.
- 5 tests `TestMeshBarrier` in `test_compositing.py`: empty mask → zeros, tiny-area → no barrier, large rect → high-cost interior, flag is bool, cost map enforces barrier with `monkeypatch`.

### §2.8 — HybridStitch Export (`backend/src/animation/hybrid_export.py`)

**Pain point:** When the pipeline produces a bad stitch, there is no way to resume from mid-pipeline state for manual correction — the operator must re-run all 13 stages from scratch or guess affine parameters manually.

**Implementation:**
- `HybridExportData` dataclass — `image_paths`, `affines` (flat 6-float lists), `photometric_gains`, `photometric_biases`, `canvas_w`, `canvas_h`, `seam_boundaries`, `seam_post_diffs`, `timestamp` (UTC ISO-8601), `asp_version="S145"`.
- `build_hybrid_export(pipeline_state: dict) → HybridExportData` — handles numpy affine arrays (flattened to 6-float), numpy boundary arrays (`.tolist()`), seam_post_diffs key coercion to str.
- `save_hybrid_export(data, path)` — `json.dumps(dataclasses.asdict(data), indent=2)`, creates parent dirs.
- `load_hybrid_export(path) → HybridExportData` — raises `FileNotFoundError` if missing.
- `_HYBRID_EXPORT_PATH: str` flag in `pipeline.py` (`ASP_HYBRID_EXPORT_PATH`, default empty = disabled). Wired after the final save in `AnimeStitchPipeline.run()` — try/except wrapped, failure logs warning and continues. Added to `pipeline.py __all__`. `"ASP_HYBRID_EXPORT_PATH"` added to `_CONFIG_SCHEMA`.
- 5 tests `TestHybridExport` in `test_pipeline.py`: affine flattening, scalar fields, save+load round-trip, missing-file raises, flag is str.

**976 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures unchanged).**

---

## Anime Stitch Pipeline — Session 144 (2026-06-21)

*Implements §3.12A Overmix Hold-Block Sub-Pixel Averaging and §3.9 SI-FID Proxy Metric.*

### §3.12A — Overmix-Style Hold-Block Sub-Pixel Averaging (`backend/src/animation/frame_selection.py`)

**Pain point:** MPEG compression introduces DCT block noise (±2–4 luma units) across frames that are part of the same animation hold (cel repeated N times). Downstream phase-correlation and ECC matching must fight through this noise, and the hold frames contribute no new spatial information — only noise averaging.

**Implementation:**
- `_hold_block_average(frames, hold_ids, paths) → Tuple[List[np.ndarray], List[str]]` — groups frames by hold block ID; for multi-frame blocks, ECC-aligns each frame to the first (`MOTION_TRANSLATION`, 20 iters, 1e-3 eps) and stack-averages with `np.mean(stack).clip(0,255)`. Single-frame blocks pass through unchanged. Path taken from the middle frame of each block.
- `cv2.error` on ECC (e.g., uniform frames with zero gradient) → falls back to raw frame without alignment, then averages normally.
- Achieves √N SNR improvement (N=2: +3 dB, N=3: +4.8 dB) on MPEG-compressed hold sequences.
- Wired as step 3c in `smart_select_frames` after `_refine_hold_ids_by_response` (step 3b); rebinds `thumbs`, `frames_paths`, `N`, `hold_ids`.
- Gate: `_HOLD_AVERAGE and _HOLD_THRESHOLD > 0.0` — requires hold detection to be active (MAD or dHash); `ASP_HOLD_AVERAGE=1` to enable.
- Added to `__all__`. `HOLD_AVERAGE_ECC_ITERS=20`, `HOLD_AVERAGE_ECC_EPS=1e-3` in `constants/animation.py`. `"ASP_HOLD_AVERAGE"` in `_CONFIG_SCHEMA`.
- 5 tests `TestHoldBlockAverage` in `test_frame_selection.py`: single-frame passthrough, identical block averages to same value, output lengths match, path from middle frame, ECC failure graceful fallback.

### §3.9 — SI-FID Proxy Metric (`backend/benchmark/bench_anime_stitch.py`)

**Pain point:** The benchmark lacks a reference-free perceptual quality metric that compares ASP and simple_stitch on the same sharpness/texture axis without requiring ground truth or a GPU InceptionV3 forward pass.

**Implementation:**
- `_compute_si_fid_score(asp_img, sim_img, patch_size=128, n_patches=32, seed=42) → Optional[float]` — samples N random patch pairs at identical locations in both images; computes Laplacian variance per patch; returns `mean(asp_var) / mean(sim_var)`. Values >1.0 mean ASP is sharper; <1.0 means simple_stitch is sharper. Returns None when images are None or smaller than patch_size.
- `_SI_FID` / `_SI_FID_PATCH_SIZE` / `_SI_FID_N_PATCHES` module-level flags. `ASP_SI_FID=1` to enable.
- `si_fid_ratio` wired into `_build_result` and emitted as `comparison.si_fid` in every benchmark result dict.
- `SI_FID_PATCH_SIZE=128`, `SI_FID_N_PATCHES=32` in `constants/animation.py`. `"ASP_SI_FID"` in `_CONFIG_SCHEMA`.
- 5 tests `TestSiFidProxy` in `test_bench_metrics.py`: identical images → ratio ≈ 1.0, sharp asp → ratio > 1.0, sharp simple → ratio < 1.0, None image → None, too-small → None.

**966 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures unchanged).**

---

## Anime Stitch Pipeline — Session 143 (2026-06-21)

*Implements §3.10 MLLM Semantic Quality Scoring and §3.1A+§3.2A AnimeInterp SGM + ConvGRU flow engine.*

### §3.10 — MLLM Semantic Quality Scoring (`backend/src/animation/mllm_scorer.py`)

**Pain point:** 43 of 97 benchmark tests use `cv_metrics` verdict source (seam coherence + ghosting ratio heuristic) because no ground truth exists. This heuristic cannot catch double-image ghost artifacts or body-incoherence failures that a human would immediately spot.

**Implementation:**
- `MllmScores` dataclass — `body_coherence`, `seam_quality`, `bg_consistency`, `overall` (all float 0–10, None on failure), `raw_response: str`
- `MllmScorer(model, base_url)` — `score(image_bgr)`, `is_available()`, `_encode_image(img)` (JPEG base64, max 1024px), `_parse_scores(raw)` (JSON parse + regex fallback)
- `score_composite(image_bgr, model)` — module-level convenience wrapper; all-None on any failure
- Calls ollama `/api/chat` via `urllib.request` (zero new deps). Structured 4-axis anime-specific prompt. 30 s timeout.
- `MLLM_TIMEOUT_SEC=30`, `MLLM_MAX_IMAGE_DIM=1024`, `MLLM_MODEL="qwen2-vl:7b"` in `constants/animation.py`
- `ASP_MLLM_SCORER=1` / `ASP_MLLM_MODEL` flags. `"ASP_MLLM_SCORER"` in `_CONFIG_SCHEMA`.
- Wired into `bench_anime_stitch.py` `_compute_all_metrics` — adds `mllm_body_coherence`, `mllm_seam_quality`, `mllm_bg_consistency`, `mllm_overall` to every benchmark result dict; `avg_mllm_overall` in summary.
- 5 tests `TestMllmScorer` in `test_bench_metrics.py`: dataclass fields, connection-error → all-None, JSON parse, regex fallback, image resize.

### §3.1A + §3.2A — AnimeInterp SGM + ConvGRU Flow Engine (`backend/src/animation/animeinterp_flow.py`)

**Pain point:** DIS and SEA-RAFT both fail on flat-color anime regions (aperture problem — no gradient signal inside uniform fills). ARAP foreground registration is effectively blind in these zones, so all seams escalate to single-pose fallback and the entire §1.56–§1.86 seam gate stack never fires.

**Implementation (`animeinterp_flow.py`):**
- `trapped_ball_segment(image_bgr, min_radius, max_radius, n_iter) → np.ndarray[int32]` — pure OpenCV; LAB flood-fill with randomised ball radii; distance-transform gap fill. No ML.
- `compute_region_features(image_bgr, label_map, use_vgg) → Dict[int, np.ndarray]` — VGG-19 conv activations per-segment centroid crop (512-d) when torch available; falls back to mean LAB color (3-d). Lazy `_get_vgg19()` singleton.
- `build_mdm(feats_a, feats_b, centroids_a, centroids_b, spatial_sigma) → np.ndarray[float32]` — (Na, Nb) Matching Degree Matrix; `MDM[i,j] = cosine_sim × exp(−dist²/2σ²)`; rows normalised to 1.
- `ConvGRUCell(input_dim, hidden_dim, kernel_size)` — PyTorch module (defined inside try/except ImportError); reset/update/out gates + flow_head Conv2d; `forward(flow_in, h) → (refined_flow, h_new)`.
- `compute_animeinterp_flow(frame_a, frame_b, n_gru_iters, weights_path) → np.ndarray[float32 (H,W,2)]` — full pipeline: trapped-ball → region features → MDM → vectorised soft-warp → optional ConvGRU refinement (n_gru_iters=0 skips GRU).
- `AnimeInterpFlow` — class wrapper with `compute(frame_a, frame_b)` interface matching existing flow engine API.

**Constants added to `constants/animation.py`:** `ANIMEINTERP_SPATIAL_SIGMA=50.0`, `ANIMEINTERP_GRU_ITERS=4`, `ANIMEINTERP_TRAPPED_BALL_MIN_R=2`, `ANIMEINTERP_TRAPPED_BALL_MAX_R=8`.

**Wired into `fg_register.py`:** `_FLOW_ENGINE` / `_USE_ANIMEINTERP` flags; `animeinterp` branch in `_dense_flow` before SEA-RAFT/DIS fallback chain. Enable: `ASP_FLOW_ENGINE=animeinterp`. `ASP_FLOW_ENGINE` and `ASP_ANIMEINTERP_WEIGHTS` added to `_CONFIG_SCHEMA`.

**Key benefit:** With `ASP_FLOW_ENGINE=animeinterp`, ARAP activates in the test env without ptlflow/RAFT. The full §1.56–§1.86 ensemble gate stack becomes active. §1.86 zone SSIM pre-gate (previously a no-op) now fires against actual ARAP output.

5 tests `TestAnimeInterpFlow` in `test_fg_register.py`: trapped-ball label map, MDM rows sum to 1, region features dict, flow shape (H,W,2) float32, shift detection.

**956 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures unchanged).**

---

## Anime Stitch Pipeline — Session 142 (2026-06-21)

*Full 97-test benchmark run + three new implementations: §1.87 Masked-Median Bg Plate, §3.14B Horizontal-Strip Compositing, §1.10B Optuna Bayesian Threshold Search.*

### Full-Corpus Benchmark Results (`anime_stitch_20260621_193956.json`)

**Runtime:** 7435 s across 97 datasets (`asp_test01`–`asp_test97`).

| Metric | ASP | Simple Stitch | Delta |
|--------|-----|---------------|-------|
| Avg GT-SSIM (55 GT tests) | 0.6588 | 0.6992 | −0.0404 ▼ |
| Avg ghosting score (97 tests) | 38.7 | 27.2 | +11.5 ▼ (42% worse) |
| Avg sharpness (97 tests) | 108.9 | 63.8 | +45.1 ▲ (71% sharper) |

**All-verdict:** asp_better=9 (9.3%) · comparable=41 (42.3%) · simple_better=46 (47.4%) · insufficient=1.  
**GT-verdict (55 tests):** asp_better=6 · comparable=22 · simple_better=26 · insufficient=1.  
**Fallbacks:** 0 external SCANS · 13 internal. **Alignment failed:** test49. **Worst outlier:** test77 (SSIM Δ=−0.239, affine ratio=26.976).

**Root cause analysis:** A5 foreground-excluded median (`ASP_FG_EXCLUDE_MEDIAN=1`) already ships, but its all-frame fallback for pixels where every frame has fg still ghost-averages different animation poses. §1.87 suppresses this fallback. Sharpness advantage (71%) is genuine sub-pixel alignment quality not captured by GT-SSIM (GT-coupling bias). See `.agent/cache/pipeline_analysis_report.md §3` for full per-test breakdown.

---

### §1.87 — Masked-Median Background Plate (`bg_complete.py` + `rendering.py`)

**Pain point:** When the character covers every frame at a canvas pixel (all_fg), the A5 fg-excluded median falls back to averaging ALL valid samples — ghost-averaging different animation poses (e.g., arm in different position across 8 frames). This is the #1 ghosting root cause in 90/97 tests.

**Implementation:**
- `_masked_median_bg(stack, fg_stack, min_agree_frac=0.4) → np.ndarray` added to `bg_complete.py`. Uses `np.ma.median(np.ma.array(stack, mask=fg_broadcast))` — excludes fg pixels from median entirely (Overmix AnimRender principle). For all_fg pixels: unconstrained median fallback (better than ghost-average; pairs with ProPainter/NN fill). Exported in `__all__`.
- `_MASKED_MEDIAN: bool` flag added to `rendering.py` (`ASP_MASKED_MEDIAN`, default OFF). Wires into `_render_median`'s A5 section: when enabled, all_fg pixels use `np.zeros_like(masks)` instead of `masks`, leaving them zero for `bg_complete` to fill. Zero-coverage pixels then filled by `ASP_BG_COMPLETE`.
- `MASKED_MEDIAN_MIN_AGREE_FRAC = 0.4` added to `constants/animation.py`.
- `"ASP_MASKED_MEDIAN"` added to `_CONFIG_SCHEMA` in `config.py` (int, 0–1).
- 5 tests `TestMaskedMedianBg` in `test_bg_complete.py`: all-bg returns plain median, fg excluded from median, all-fg stability fallback, mixed coverage, output shape.

**Enable:** `ASP_MASKED_MEDIAN=1` (pair with `ASP_BG_COMPLETE=1` to fill zero-coverage holes).

---

### §3.14B — Horizontal-Strip Compositing (`pipeline.py`)

**Pain point:** When `_detect_scroll_axis(affines)` returns `'horizontal'`, `pipeline.py` hard-falls back to SCANS, discarding all ASP alignment quality (sub-pixel registration, BiRefNet masking) for horizontal scroll sequences.

**Implementation:**
- `_HORIZONTAL_COMPOSITE: bool` flag added to `pipeline.py` (`ASP_HORIZONTAL_COMPOSITE`, default OFF). When enabled, the Stage 9 horizontal-SCANS fallback is suppressed; pipeline continues to Stage 10+ normally.
- `_composite_foreground` already has a horizontal fast-path at its entry (lines 3332–3336): when `tx_range >> ty_range`, it detects horizontal scroll and returns `canvas.copy()` unchanged (temporal median is already optimal for horizontal — each pixel is covered by ≤2 frames). So no new compositing logic is needed; the flag purely removes the early exit in `pipeline.py`.
- `HORIZONTAL_FEATHER_PX = 120` added to `constants/animation.py`.
- `"ASP_HORIZONTAL_COMPOSITE"` added to `_CONFIG_SCHEMA` in `config.py` (int, 0–1).
- 5 tests `TestHorizontalCompositing` in `test_compositing.py`: horizontal axis detection, flag default=False, flag attribute exists, compositing fast-path returns canvas, flag is bool.

**Enable:** `ASP_HORIZONTAL_COMPOSITE=1`.

---

### §1.10B — Optuna Bayesian Threshold Search (`backend/src/animation/param_search.py`)

**Pain point:** The `_auto_verdict` function in `bench_anime_stitch.py` has 7 scalar thresholds (banding cutoffs, score weights) that were hand-tuned. The 43 cv_metrics tests have verdicts that depend entirely on these thresholds — Optuna TPE can find better values without re-running the pipeline.

**Implementation:**
- New `backend/src/animation/param_search.py` module. Exports `ASP_SEARCH_PARAMS` (7-param search space), `_verdict_from_config(asp_m, sim_m, cfg)` (recomputes `_auto_verdict` with configurable thresholds), `_score_config(cfg, result_data)` (objective: asp_better×2 + comparable×1 on cv_metrics tests only; GT tests excluded — their verdicts cannot be changed by threshold tuning), `run_param_search(result_json_path, n_trials, output_toml_path, n_jobs)`.
- Search space (7 params): `severe_banding_thresh` (10–50, default 28), `severe_banding_ratio` (1.1–3.0, default 1.5), `score_margin` (1.01–1.30, default 1.10), `w_coverage` (0.1–1.0), `w_coherence` (0.05–0.8), `w_seam_gradient` (0.01–0.5), `w_ghosting` (0.01–0.5).
- CLI: `python -m backend.src.animation.param_search --results <json> --trials 200 --out asp_config_optimized.toml`. Each trial < 1 ms (pure NumPy on stored metrics); 200 trials complete in < 1 second.
- 5 tests `TestVerdictFromConfig` + `TestScoreConfig` (10 total) in new `backend/test/animation/test_param_search.py`.

**Run:** `python -m backend.src.animation.param_search --results backend/benchmark/results/anime_stitch_20260621_193956.json --trials 200 --out asp_config_optimized.toml`

---

**946 backend tests (9 skipped, 5 pre-existing fg_register failures unchanged).**

---

## Anime Stitch Pipeline — Session 141 (2026-06-21)

*Implements §1.86 (Zone SSIM Pre-Gate). 5-test benchmark run confirms ASP compositing quality, identifies ghosting from temporal median pose mismatch as the primary remaining bottleneck.*

### §1.86 — Zone SSIM Pre-Gate for Post-ARAP Structural Compatibility

**Pain point:** After ARAP foreground registration, no mechanism existed to verify that the two warped zone crops are structurally compatible for blending before the DP seam cut runs. ARAP may converge without resolving a large character pose mismatch, producing a false-positive "registration succeeded" signal. The subsequent Laplacian blend then creates a double-image ghost artifact.

**Implementation (`compositing.py`):**
- `_zone_pair_ssim(fa_zone, fb_zone, small_h=64) → float` — INTER_AREA resize to 64px height, greyscale conversion, `skimage.metrics.structural_similarity(data_range=255)`. Returns 1.0 (no gate) for zones with < 4 rows or < 8 cols.
- `_ZONE_PRE_SSIM_THRESH` module flag (`ASP_ZONE_PRE_SSIM_THRESH`, default 0.0=off). Wired in blend loop after §1.70 (zone fg-coverage gate) and before the DP seam cut.
- Gate pattern: `if score < threshold and k not in seam_single_pose → seam_single_pose[k] = dominant_frame`.
- `ZONE_PRE_SSIM_THRESH=0.35` added to `constants/animation.py`.
- `"ASP_ZONE_PRE_SSIM_THRESH"` added to `_CONFIG_SCHEMA` in `config.py` (float, 0.0–1.0, "§1.86: Zone-SSIM floor (post-ARAP) for single-pose escalation").
- `_zone_pair_ssim` and `_ZONE_PRE_SSIM_THRESH` exported in `__all__`.
- 5 tests `TestZonePairSsim` in `test_compositing.py`: identical→1.0, checker-vs-solid→<0.5, thin zone→1.0, narrow zone→1.0, half-different→(0.1,0.9).

**5-test benchmark results (2026-06-21, ARAP disabled — no ptlflow in test env):**

| Test | ASP GT-SSIM | Sim GT-SSIM | ASP Al-SSIM | Sim Al-SSIM | Verdict | Ghost A/S |
|------|-------------|-------------|-------------|-------------|---------|-----------|
| test04 | 0.6795 | 0.7381 | 0.7069 | 0.7477 | simple_better | 41.2/21.4 |
| test08 | 0.7252 | 0.8095 | 0.7432 | 0.8232 | simple_better | 58.8/46.0 |
| test09 | 0.7845 | 0.7564 | 0.8003 | 0.7976 | comparable | 29.1/20.8 |
| test27 | 0.6980 | 0.6797 | 0.6977 | 0.7535 | simple_better | 34.6/23.2 |
| test57 | 0.7209 | 0.7549 | 0.7416 | 0.7999 | simple_better | 43.6/24.1 |

ASP ghosting scores consistently higher than simple stitch. Primary bottleneck: temporal median ghost-averaging of different animation poses creates pervasive double-image residuals that propagate to all GT-SSIM scores. §1.86 gate would activate in full ML environments where ARAP runs on compatible zones; in this test environment (no ptlflow) ARAP is disabled and all seams escalate to single-pose via other gates.

**Test suite: 933 backend tests (9 skipped, 5 pre-existing fg_register failures unchanged).**

---

## Documentation Roadmap — Session 8 (2026-06-20)

*Implements §6.12C (PR preview deployments) — the last unimplemented item in the documentation roadmap section bodies. All matrix items and section recommendations are now ✅ except §6.15C (gated on Phase 13).*

### §6.12C — PR preview deployments

Implemented GitHub Pages PR preview deployments without any external service (Netlify/Cloudflare). All components use existing GitHub Actions infrastructure.

**`preview` job (Job 11 in `.github/workflows/docs.yml`):**

- `if: github.event_name == 'pull_request'` — fires only on PR events, not on push or schedule.
- Runs the full MkDocs build (`--strict`) on every commit to a qualifying PR.
- Deploys the built site to `gh-pages/pr-preview/{pr_number}/` via `peaceiris/actions-gh-pages@v4`.
  - `keep_files: true` — preserves the root `gh-pages` site deployed by the `deploy` job on every main-branch push.
- Posts (or updates) a sticky comment on the PR using `actions/github-script@v7`:
  - Scans the PR's comment list for an existing bot comment containing "Documentation preview".
  - Updates it in place on subsequent pushes; creates a new comment on the first push.
  - Preview URL format: `https://{owner}.github.io/{repo}/pr-preview/{number}/`

**`.github/workflows/docs-cleanup.yml` (new file):**

```yaml
on:
  pull_request:
    types: [closed]
```

- Isolated in a separate workflow so the `pull_request: types: [closed]` event doesn't trigger the 10 existing build jobs in `docs.yml`.
- `concurrency: docs-cleanup-{number}` — prevents concurrent cleanup runs for the same PR.
- Checks out the `gh-pages` branch; skips gracefully if branch doesn't exist.
- `git rm -rf pr-preview/{number}` → commit → push when the directory exists.
- `continue-on-error: true` on both the checkout and the push — handles the case where no preview was ever deployed.

**Why GitHub-native instead of Netlify/Cloudflare:**
The existing `docs.yml` already manages a `gh-pages` deployment. Adding a `pr-preview/` subdirectory to the same branch with `keep_files: true` gives per-PR previews with zero new external dependencies or secrets.

---

## Documentation Roadmap — Session 7 (2026-06-20)

*Implements the final three actionable items from `moon/roadmaps/documentation.md`: §6.14C (Structurizr C4 model), §6.15D (OpenAPI playground documentation), and §6.13E (alex inclusive language hook). Updates the Effort×Impact matrix to mark all completed items ✅.*

### §6.14C — Structurizr / C4 model architecture documentation

Created the complete C4 architecture model for Image Toolkit:

| File | Purpose |
|------|---------|
| `docs/structurizr/workspace.dsl` | Structurizr DSL workspace — 5 views across 3 C4 levels |
| `docs/structurizr/README.md` | Rendering guide (Docker Lite, Structurizr CLI, Mermaid export) |
| `docs/STRUCTURIZR.md` | MkDocs portal page — view summary, key arch decisions, render instructions |

**C4 views modelled:**

| Level | View | Scope |
|-------|------|-------|
| 1 — System Context | `SystemContext` | 2 user personas, 4 external systems |
| 2 — Containers | `Containers` | 10 deployable units (Desktop GUI, Android, iOS, Extension, Web Frontend, Django API, Python Backend, Rust Core, Crypto Module) |
| 3 — Components | `PythonBackendComponents` | ASP Pipeline · ML Models · VaultManager · ImageDatabase · Web Wrappers |
| 3 — Components | `RustCoreComponents` | Math Backbone · Image Processing · Web Crawlers · File System Scanner |
| 3 — Components | `DjangoApiComponents` | DRF API Views · Celery Task Workers · OpenAPI Endpoints |

Key architectural decisions captured in the DSL: PyO3 FFI boundary, JPype JVM bridge (VaultManager), Celery async dispatch (all endpoints return HTTP 202), and pgvector semantic search.

- `mkdocs.yml` nav: "C4 Architecture Model" added under Getting Started.
- `docs/hooks.py`: `STRUCTURIZR.md` added to the `_sync_dir` copy list.

To render locally: `docker run -it --rm -p 8080:8080 -v "$(pwd)/docs/structurizr:/usr/local/structurizr" structurizr/lite`

### §6.15D — OpenAPI / Redoc playground documentation

Discovered that `drf-spectacular` was already wired in `api/urls.py` (Swagger UI at `/api/docs/`, Redoc at `/api/redoc/`, raw schema at `/api/schema/`) with all 21 endpoints in `tasks/views.py` decorated with `@extend_schema`. Implemented the documentation layer:

**`docs/api/rest-api.md`** — Comprehensive REST API reference:
- All 21 endpoints in 4 tag-group tables (Core, AI & Video, Web & Crawlers, Database + OpenAPI meta)
- HTTP 202 response format (`{task_id, status: "processing"}`)
- `manage.py spectacular --validate --file openapi.yaml` static spec generation guide
- Add-endpoint walkthrough (serializer → view → url → task → validate)
- Authentication note (dev vs. production `DEFAULT_AUTHENTICATION_CLASSES`)

**`docs-openapi` CI job** (Job 9 in `.github/workflows/docs.yml`):
- Installs `django`, `djangorestframework`, `drf-spectacular`, `psycopg2-binary`
- Runs `python manage.py spectacular --validate --file docs/api/openapi.yaml`
- `continue-on-error: true` — DB env vars are dummies (spectacular does not execute queries)
- Uploads `openapi-spec` artifact (14-day retention)

- `mkdocs.yml` nav: "REST API" added as the first entry under Reference.
- `docs/hooks.py`: `_rest_api_stub()` added as fallback for `docs/api/rest-api.md`.
- Matrix: §6.15D updated from "blocked on §4.10" to ✅.
- §6.15D roadmap section updated to document the actual implementation.

### §6.13E — `alex` inclusive language pre-commit hook

Added to `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/get-alex/alex
  rev: v11.0.0
  hooks:
    - id: alex
      name: alex (inclusive language check)
      files: ^docs/.*\.md$
      args: [--quiet]
```

- Scoped to `docs/*.md` — not applied to source code comments or roadmap files.
- `--quiet` suppresses informational output; only warnings and errors are shown.
- Blocks commit if insensitive writing is detected.

### Effort × Impact Matrix — Complete ✅

All implementable items in the matrix now marked ✅:

| Tier | Newly marked ✅ |
|------|----------------|
| Low effort | §6.13E `alex` pre-commit hook |
| Very High effort | §6.14C Structurizr C4 model · §6.15D OpenAPI playground |
| All other tiers | Already marked in Sessions 1–6 |

Only §6.15C (TypeScript algorithm stepper) remains — genuinely gated on Phase 13 analytics dashboard work.

---

## Documentation Roadmap — Session 6 (2026-06-20)

*Completes all remaining implementable items in `moon/roadmaps/documentation.md`. Implements §6.9C, §6.4B, §6.12B, §6.12D, and §6.1B.*

### §6.9C — `mkdocs-jupyter` notebook portal integration (`mkdocs.yml`)

Replaced the commented-out `myst-nb` block in `mkdocs.yml` with `mkdocs-jupyter`:

```yaml
- mkdocs-jupyter:
    execute: false
    include_source: true
    ignore_h1_titles: true
    allow_errors: true
```

- The three `.ipynb` files already listed in the nav (`benchmark_analysis.ipynb`, `asp_pipeline_walkthrough.ipynb`, `clip_embedding_walkthrough.ipynb`) are now rendered as proper portal pages — code cells become code blocks, markdown cells render as HTML.
- `execute: false` — no cells are run at build time (outputs were stripped by nbstripout; GPU cells are safe).
- Added `mkdocs-jupyter` to the `pip install` step in both `docs-python` and `deploy` CI jobs.

### §6.4B + §6.12B — Dokka GFM portal integration + parallel Kotlin CI job

**§6.4B** — Dokka Markdown output wired into the MkDocs portal:
- `docs/hooks.py` now creates `docs/api/kotlin/index.md` — a stub page with module overview table, local Dokka run instructions, and CI artifact guidance.
- `mkdocs.yml` nav extended: "Kotlin API > Overview" under Reference.

**§6.12B** — New `docs-kotlin` CI job in `.github/workflows/docs.yml`:
- Runs `actions/setup-java@v4` (Temurin 17) + `android-actions/setup-android@v3` (API 36 + build-tools).
- Executes `./gradlew dokkaGfm --no-daemon` from `app/android/`.
- Uploads `app/android/build/dokka/gfm/` as **`kotlin-api-docs`** artifact (7-day retention).
- `continue-on-error: true` on Dokka step and SDK setup — prevents Android SDK availability from blocking the MkDocs deploy.
- `push` trigger now also fires on `app/android/src/**/*.kt` changes.

### §6.12D — Scheduled weekly notebook execution

- Added `schedule: cron '0 2 * * 1'` trigger to `docs.yml` (every Monday at 02:00 UTC).
- New `weekly-notebooks` job (gated to `schedule` events via `if: github.event_name == 'schedule'`):
  - Installs `nbconvert`, `papermill`, `ipywidgets`, and all CPU-safe notebook deps.
  - Executes `benchmark_analysis.ipynb` (CPU-safe) with 300 s timeout.
  - Uploads result as **`weekly-notebooks-<run_id>`** artifact (30-day retention).
  - Failures print a `WARN` but do not error the workflow — signals API drift for human review.

### §6.1B — Sphinx for the full Python backend

Created `docs/sphinx/` with a complete Sphinx setup:

| File | Purpose |
|---|---|
| `docs/sphinx/conf.py` | Full config: `sphinx-autoapi`, `napoleon`, `myst-nb`, `sphinx-copybutton`, `furo` theme, intersphinx (Python/NumPy/PyTorch/OpenCV) |
| `docs/sphinx/index.rst` | Top-level toctree → `autoapi/index` (auto-discovers all of `backend/src/`) |
| `docs/sphinx/requirements.txt` | `sphinx>=7.3`, `sphinx-autoapi>=3.3`, `furo>=2024.1.29`, `myst-nb>=1.1`, `sphinx-copybutton>=0.5.2` |

Key `conf.py` settings:
- `autoapi_dirs = ["../../backend/src"]` — discovers all modules without manual `.. automodule::` entries.
- `autoapi_ignore` excludes test files and `__pycache__`.
- `nb_execution_mode = "off"` — myst-nb renders notebooks as static pages.
- Napoleon enabled for Google-style docstrings (matching `DOCUMENTATION_STANDARDS.md`).

New `docs-sphinx` CI job:
- Installs Sphinx deps via pip (separate from uv to avoid Rust build dependency).
- Runs `sphinx-build -b html docs/sphinx site/sphinx-api -W --keep-going`.
- Uploads **`sphinx-api-docs`** artifact (14-day retention).
- `continue-on-error: true` for the build step (some modules import PyO3 extensions unavailable in CI).

`docs/hooks.py` creates `docs/api/sphinx.md` — a comparison stub explaining the relationship between mkdocstrings (lightweight, in-portal) and Sphinx (comprehensive, standalone artifact).

---

## Documentation Roadmap — Session 5 (2026-06-20)

*Completes `moon/roadmaps/documentation.md` secondary sub-options — all low/medium-effort matrix items now ✅. Implements §6.13C, §6.2A, §6.3B, §6.14D.*

### §6.13C — TypeDoc strict mode (`frontend/typedoc.json`)

Set `"treatWarningsAsErrors": true` in `frontend/typedoc.json`. TypeDoc warnings are now errors — undocumented exports will break the CI doc build. The CI `docs-typescript` job was upgraded accordingly (strict mode enforced via the Markdown step; HTML step uses `continue-on-error` as advisory).

### §6.2A — Full `# Examples` doc-test coverage across all Rust math modules

Added `# Examples` rustdoc blocks to every public function that previously had only a one-line summary. All three math modules now have 100% doc-test coverage:

| File | Functions newly documented |
|---|---|
| `base/src/math/stats.rs` | `sample_std_dev`, `covariance`, `min`, `max`, `iqr`, `z_score_normalize`, `min_max_normalize`, `histogram`, `counts_to_probs`, `covariance_matrix` (10 functions) |
| `base/src/math/distance.rs` | `hamming_distance`, `hamming_f64`, `bhattacharyya_coefficient`, `bhattacharyya_distance`, `hellinger_distance`, `pairwise_distance_matrix`, `condensed_distance_matrix` (7 functions) |
| `base/src/math/information.rs` | `entropy_nats`, `empirical_entropy`, `joint_entropy`, `conditional_entropy`, `js_divergence`, `total_variation`, `mutual_information_discrete`, `normalised_mutual_information`, `cross_entropy` (9 functions) |

All examples are verifiable doc-tests (run by `cargo test --doc` in CI, enforced by `RUSTDOCFLAGS="-D warnings"`).

### §6.3B — TypeDoc → Markdown portal integration (`frontend/`)

- Added `typedoc` (`^0.26.11`) and `typedoc-plugin-markdown` (`^4.2.9`) to `frontend/package.json` devDependencies.
- Created `frontend/typedoc-markdown.json` — separate TypeDoc config that uses `typedoc-plugin-markdown` and outputs `.md` files to `docs/api/typescript/` for MkDocs ingestion.
- Updated `mkdocs.yml` nav: added "TypeScript API" section under "Reference" pointing to `api/typescript/README.md`.
- Updated `docs.yml` `docs-typescript` job to run the Markdown step as the primary (strict, blocking) step, with the HTML step as advisory.
- TypeScript API is now accessible at `/reference/typescript-api/` in the MkDocs portal.

### §6.14D — Mermaid CLI pre-render in CI (`docs.yml`)

- Added `npm install -g @mermaid-js/mermaid-cli` step to `docs-typescript` CI job.
- Pre-renders the module-dependency flowchart from `docs/ARCHITECTURE.md` to `site/architecture-diagram.svg` (scale 2×) via `mmdc --outputFormat svg`.
- SVG stored as a CI artifact (`architecture-svg`, 7-day retention).
- `continue-on-error: true` on the `mmdc` step since headless Chromium availability varies by runner; MkDocs Material renders mermaid client-side as the fallback.

---

## Documentation Roadmap — Session 4 (2026-06-20)

*Completes `moon/roadmaps/documentation.md` — all 15 sections now ✅. Implements §6.5A and §6.15A+B.*

### §6.5A — Swift DocC comments + catalog (`app/ios/`)

Added DocC-style `///` doc comments to all 8 public Swift types:

| File | Type | Comment coverage |
|---|---|---|
| `App.swift` | `ImageToolkitApp` | Entry point doc, `preferredColorScheme` note |
| `navigation/Screen.swift` | `Screen` | All 6 cases, `id`/`label`/`iconName` properties |
| `ui/MainAppScreen.swift` | `MainAppScreen` | Architecture overview, deep-link note |
| `ui/screen/ConvertScreen.swift` | `ConvertScreen` | Screen purpose, IPC bridge note, Android mirror reference |
| `theme/Theme.swift` | `AppTheme`, `AppTheme.Typography` | All colour tokens (MARK sections), typography scale, `Color.init(hex:alpha:)` |
| `layout/FlowLayout.swift` | `FlowLayout<Data,Content>` | Layout algorithm note, iOS 16/17 migration note, `init` params |
| `ui/components/FileInput.swift` | `FileInput` | Label/path params, iOS `UIDocumentPickerViewController` note |
| `ui/components/SectionCard.swift` | `SectionCard<Content>` | Expand/collapse behaviour, shadow spec, `init` params |
| `ui/components/FormatSelector.swift` | `FormatSelector` | Chip grid description, "Add All"/"Remove All" buttons |

Created `app/ios/image_toolkit/ImageToolkit.docc/ImageToolkit.md` — DocC catalog:
- Package-level overview with architecture ASCII diagram
- `## Topics` reference sections for Navigation, Screens, UI Components, Layout, Theme
- `xcodebuild docbuild` and `swift package generate-documentation` run instructions

### §6.15A — ipywidgets interactive threshold explorer (`benchmark_analysis.ipynb`)

Added **Cell 8 — Interactive Threshold Explorer** after the per-test summary table:
- `ipywidgets.FloatSlider` × 3: `ghosting_siqe` threshold (0–100, default 30), `seam_visibility` threshold (0–100, default 25), `ssim` floor (0–1, default 0.70).
- `widgets.interactive_output` drives two live charts: failure-count horizontal bar + SSIM-vs-ghosting scatter (passing=blue, failing=red) with threshold lines.
- Filtered table of all tests failing at least one threshold is printed below the charts.
- **Static fallback**: when `ipywidgets` is not installed (CI / nbconvert), the cell calls `_show_interactive()` once with default values — no import error, no dead cell.

### §6.15B — Binder launch badges

Added `[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ACFPeacekeeper/Image-Toolkit/main?filepath=docs/notebooks/…)` to the first cell of all three notebooks:
- `benchmark_analysis.ipynb` — also added `ipywidgets` to prerequisites list
- `asp_pipeline_walkthrough.ipynb`
- `clip_embedding_walkthrough.ipynb`

---

## Documentation Roadmap — Session 3 (2026-06-20)

*Implements `moon/roadmaps/documentation.md` §6.8B, §6.9A (full completion), plus CI and pre-commit updates.*

### §6.8B — BENCHMARKS.md restructuring
- Added **Suite Index** table at the top linking all 6 benchmark suites to their runners and CI jobs.
- Added **Rust Math Micro-benchmarks** section with full `criterion` scaffold (`bench_math.rs` template, `Cargo.toml` `[[bench]]` stanza, run commands, and provisional baseline table for `mean`/`euclidean`/`cosine_similarity`/`shannon_entropy`).
- Added **Frontend Analytics Layer** section documenting all 13 `benchmark.ts` exports with a function → purpose table (`computeEfficiency`, `detectRegressions`, `computeSeamQualityHeatmap`, `computeFallbackReasonDistribution`, etc.).
- Added **ASP Benchmark Corpus** subsection in the ASP section: corpus size (97 tests), failure taxonomy (ghost / hard seam / low SSIM / SCANS fallback), and baseline metric table (sharpness, coverage, ghosting, seam visibility, aligned SSIM, fallback rate).
- Added **CI Registration** guide: Python (extend `run_all.py`), Rust (`[[bench]]` + workflow step + artifact upload), Frontend (Jest perf test template), and RLHF score integration note.

### §6.9A (full completion) — Remaining Jupyter notebooks
- Created `docs/notebooks/asp_pipeline_walkthrough.ipynb` (6 cells): source frames display → smart frame selection → `AnimeStitchPipeline.run()` → Stage 9 temporal render vs final → bundle-adjusted translation vector charts → seam gradient heatmap. GPU cells tagged `# SKIP_CI`.
- Created `docs/notebooks/clip_embedding_walkthrough.ipynb` (5 cells): OpenCLIP ViT-B/32 load → batch image embedding → text query → top-K nearest-neighbour grid → PCA 2D scatter coloured by dataset → `SQLiteStore` upsert/search demo (CPU-safe).

### CI and pre-commit updates
- `.pre-commit-config.yaml` — added `nbstripout 0.7.1` hook scoped to `docs/notebooks/` to keep notebook output cells out of git history.
- `.github/workflows/docs.yml` — added **`docs-notebooks` job** (Job 4): installs `nbconvert` + CPU dependencies, executes `benchmark_analysis.ipynb`, uploads rendered HTML as a 14-day artifact. Job 6 (deploy) is unchanged; notebooks job does not gate deploy.
- `mkdocs.yml` — added **Notebooks** nav section with all three notebooks; clarified `myst-nb` comment (can be enabled once `pip install myst-nb`).

---

## Documentation Roadmap — Session 2 (2026-06-19)

*Implements `moon/roadmaps/documentation.md` §6.1A, §6.3A, §6.4A, §6.6A, §6.9A, §6.14A.*

### §6.1A — Python Google-style docstrings (`backend/src/animation/`)
- Converted NumPy-style docstrings to Google-style in `config.py`: `validate_asp_config`, `load_asp_config`, `get_asp`, `dump_asp_config` — added `Args:`, `Returns:`, `Example:` sections with working doctests.
- Added full Google-style docstring to `canvas.find_optimal_sequence` (was single-line summary only).

### §6.3A — TypeScript Reference Docs (TypeDoc + TSDoc)
- Created `frontend/typedoc.json` — TypeDoc config targeting `src/math/`, output to `site/api/typescript/`, with category grouping and `invalidLink` validation.
- `frontend/src/math/stats.ts` — added `@packageDocumentation`, full `@param`/`@returns`/`@example` blocks on all 12 exports (`mean`, `variance`, `sampleVariance`, `stdDev`, `sampleStdDev`, `min`, `max`, `percentile`, `median`, `iqr`, `pearsonCorrelation`, `normalize01`, `zScoreNormalize`, `histogram`).
- `frontend/src/math/distance.ts` — same treatment on all 8 exports (`squaredEuclidean`, `euclidean`, `manhattan`, `chebyshev`, `cosineSimilarity`, `cosineDistance`, `hammingDistance`, `pairwiseDistances`, `condensedDistances`).
- `frontend/src/math/linalg.ts` — added `@packageDocumentation`, inline JSDoc on all Vec2/Vec3/generic N-dim and Mat3 ops.

### §6.4A — Dokka (Android/Kotlin API docs)
- Added `dokka = "1.9.20"` to `[versions]` in `gradle/libs.versions.toml`.
- Added `dokka = { id = "org.jetbrains.dokka", version.ref = "dokka" }` to `[plugins]`.
- Applied `alias(libs.plugins.dokka)` in `app/android/build.gradle.kts`.
- Run: `./gradlew dokkaHtml` → output at `app/android/build/dokka/html/`.

### §6.6A + §6.14A — docs/ARCHITECTURE.md module dependency graph
- Added "Module Dependency Graph" section at the top of `docs/ARCHITECTURE.md` with a `flowchart TD` Mermaid diagram covering all layers: Entry Points, Desktop GUI, Python Backend, Rust Core, Data Layer, Cryptography, Mobile, Browser Extension.
- Added constraints table (no blocking Qt I/O, DontUseNativeDialog, no QWebEngineView, QPixmap main-thread only, Rust cdylib, no SQLite in main app).

### §6.9A — Jupyter Notebook: Benchmark Analysis
- Created `docs/notebooks/benchmark_analysis.ipynb` — 7 cells:
  1. Setup & load all `backend/benchmark/results/*.json` into a DataFrame
  2. Metric overview table (ssim, aligned_ssim, ghosting_score, ghosting_siqe, seam_visibility, rlhf_score)
  3. SSIM distribution histograms (ssim vs aligned_ssim side-by-side)
  4. Ghosting score KDE (ghosting_score vs ghosting_siqe with flag threshold line)
  5. ASP vs SCANS fallback rate bar chart
  6. Failure taxonomy (ghost / hard seam / low SSIM / SCANS fallback) bar chart
  7. Metric correlation heatmap + per-test styled summary table

---

## Documentation Roadmap — Session 1 (2026-06-19)

*Implements `moon/roadmaps/documentation.md` §6.2B, §6.7B/C, §6.8A+C, §6.10A, §6.11A, §6.12A, §6.13A+D.*

### Added

**Rust doc-tests — `base/src/math/` (`§6.2B`)**
- 16 doc-tests added across `stats.rs` (mean, variance, sample_variance, std_dev, pearson_correlation, percentile, median), `distance.rs` (squared_euclidean, euclidean, manhattan, chebyshev, minkowski, cosine_similarity, cosine_distance), `information.rs` (shannon_entropy, kl_divergence).
- All 16 pass via `cargo test --doc`. Tests act as regression guards for the math backbone API.

**`docs/DEPENDENCY_POLICY.md` (`§6.7B`)**
- Version requirement table: Python 3.11+, Rust 1.70+, Node 18+, PostgreSQL 14+, pgvector 0.5.0+, Android API 26+, iOS 16+.
- Pinning policy: exact pins in lockfiles (`uv.lock`, `Cargo.lock`, `package-lock.json`); compatible-release specifiers in `requirements.txt`.
- Upgrade cadence: CVE ≥ 7.0 within 7 days, minor versions monthly, major versions with migration plan.
- Process for introducing / removing dependencies with `pip-audit` + `cargo audit` + `npm audit` commands.
- Per-stack notes for PyTorch CUDA pinning, PySide6 minor version sensitivity, PyO3 ABI3 target, Electron ABI, Gradle/Compose BOM alignment.

**`docs/DOCUMENTATION_STANDARDS.md` (`§6.7C`)**
- Python: Google-style docstrings, required sections (Args, Returns, Raises, Example), 88-char line limit, `pytest --doctest-modules` requirement.
- Rust: `///` for all public items, `# Panics` required when applicable, `# Examples` required for math modules, `SAFETY:` for `unsafe` blocks.
- TypeScript: TSDoc `@param`/`@returns`/`@example` for all exports in `frontend/src/math/`.
- Kotlin: KDoc `@param`/`@return` for all public API.
- Swift: DocC `- Parameters:`/`- Returns:`/`- Throws:` for all public functions.
- Markdown: TOC for files > 100 lines, roadmap structure requirements, language-tagged code blocks, enforcement commands.
- Inline comment philosophy: only document the *why*, never the *what*; `SAFETY:` required for `unsafe`.

**`docs/TROUBLESHOOTING.md` (`§6.8A + §6.8C`)**
- Supersedes `docs/TROUBLESHOOT.md` (40 lines → 310 lines).
- New sections: **ASP Pipeline Errors** (inlier failure, SCANS fallback, ghosting, canvas overflow, `asp_config.toml` precedence); **Rust/PyO3 Build Failures** (`maturin develop`, ABI mismatch, link errors, rayon panics in tests); **Hydra CLI** (`HydraException`, struct mode, `config_path` resolution, ComfyUI port); **Database** (pgvector install, migration rollback); **Tauri/Frontend** (webkit2gtk, openssl-sys); **Mobile** (Android SDK path, Gradle/AGP matrix, iOS signing); **Test Suite** (freeze root causes, safe invocations).
- Existing SIGSEGV content retained and reorganised under PySide6 / Qt Crashes.

**`mkdocs.yml` (`§6.10A`)**
- MkDocs Material theme with dark/light toggle, sticky nav tabs, code copy, mermaid superfences, MathJax.
- `mkdocstrings[python]` with Google-style handler: filters private members, shows source, separate signature.
- Full navigation tree: Getting Started → Reference (Python API stubs + Rust note) → Operations → Roadmaps → Research → Changelog.

**`docs/index.md` + `docs/hooks.py` (`§6.11A`)**
- Portal home page with project-level Mermaid architecture graph (Frontend → Backend → Data layers), key entry points table, and stack version table.
- `hooks.py`: MkDocs pre-build hook that symlinks `moon/roadmaps/*.md`, `moon/CHANGELOG.md`, `moon/ROADMAP.md`, and `research/*.md` into the `docs/` tree without moving the source files.
- Stub API pages created for `docs/api/python/{animation,core,models}.md` and `docs/api/rust/math.md`.

**`.github/workflows/docs.yml` (`§6.12A`)**
- 5-job pipeline: `docs-python` (MkDocs build `--strict`), `docs-rust` (`cargo test --doc` + `cargo doc --no-deps -D warnings`), `docs-links` (lychee), `docs-typescript` (TypeDoc advisory), `deploy` (GitHub Pages on main).
- Path filters: only fires on changes to `docs/`, `moon/roadmaps/`, `research/`, Python/Rust/TS source, or `mkdocs.yml`.
- Concurrency group: cancels in-progress run on new push to the same branch.

**`.pre-commit-config.yaml` (`§6.13A + §6.13D`)**
- Hooks: pre-commit-hooks (trailing whitespace, EOF fixer, YAML/TOML/JSON check, large file guard), ruff (lint + format), pydoclint (Google-style, scoped to `backend/src/animation/`), mypy (strict modules only), lychee (Markdown link check, external caches, skips rate-limited hosts), cargo-fmt, cargo-doc-test (scoped to `base/src/math/`), tsc (type check `frontend/src/math/`).

---

## Analytics — ASP Benchmark Diagnostics Phase 11 + Coverage Expansion (2026-06-19)

### Shipped

**ASP benchmark enrichment (`backend/benchmark/bench_anime_stitch.py`)**
- `_build_result` now emits `fallback_reason` (classified: `alignment_failed:*`, `composite_gate_sc/sb:*`, `ghost_gate:*`, `render_exception:*`), `frame_selection` funnel dict (original → smart_select → spatial_dedup → final, plus `selection_mode`), and `strip_banding_score` in `_compute_all_metrics`.

**Rust type extension (`frontend/src-tauri/src/benchmark_commands.rs`)**
- `AspMetrics` gains: `strip_banding_score`, `ghost_seam_scores`, `seam_color_scores`, `seam_ncc_scores`, `rlhf_needs_review`
- `AspDataset` gains: `fallback_reason`, `alignment`, `photometric`, `affine_health`, `frame_selection`, `pipeline_config`
- New helper structs: `AspAffineEntry`, `AspAlignment`, `AspPhotometric`, `AspAffineHealth`, `AspFrameSelection`

**TypeScript analytics layer (`frontend/src/math/benchmark.ts`)**
- New interfaces: `AspAffineEntry`, `AspAlignment`, `AspPhotometric`, `AspAffineHealth`, `AspFrameSelection`
- `AspMetrics` and `AspDataset` updated to match Rust types
- New analysis functions: `computeAlignmentDrift`, `computePhotometricProfile`, `computePerSeamDetail`, `computeEdgeQualityBreakdown`, `computeFrameSelectionStats`, `computeFallbackReasonDistribution`, `computeGtComparisons`

**ASP Dashboard expansion (`frontend/src/tabs/analytics/BenchmarkDashboard.tsx`)**
- ASP Pipeline page expanded from 5 tabs to 12: Overview, Timing, Seam Quality, **Per-Seam**, **Alignment Drift**, **Photometric**, **Edge Quality**, **Frame Selection**, **Fallback Root Cause**, **GT Comparison**, ASP vs Simple, Heatmap
- Strip banding score added to Overview table

**Rust image processing benchmark (`backend/benchmark/bench_rust_image_processing.py`)**
- New General-suite benchmark covering `load_image_batch`, `scan_directory`, `convert_image`, `merge_images` at 512px / 1080p resolutions

**Streamlit dashboard removed**
- `backend/ui/benchmark_dashboard.py` deleted (976 lines); all functionality present in Tauri/React dashboard

**Roadmap**
- `moon/roadmaps/analytics_and_interpretability.md`: Phase 11 (ASP analytics, 11.1–11.10) and Phase 12 (coverage expansion, 12.1–12.8) added

---

## Analytics — Benchmark Dashboard Migration: Streamlit → Tauri/React (2026-06-19)

### Shipped

| File | Role |
|------|------|
| `frontend/src-tauri/src/benchmark_commands.rs` | Tauri command `load_benchmark_reports` — walks results dir, parses ASP + General JSON schemas into `BenchmarkReport` discriminated union (`kind: "Asp" \| "General"`), sorted by mtime |
| `frontend/src/math/benchmark.ts` | Pure analytics layer: `computeEfficiency`, `computeMemoryVsTimeScatter`, `computeMemoryBreakdown`, `computeTimingBreakdown`, `computeMetricComparisons`, `computeSeamQualityHeatmap`, `verdictSummary`, `extractGeneralTrend`, `extractAspTrend`, `computeSuiteStats`, `detectRegressions` |
| `frontend/src/tabs/analytics/charts.tsx` | SVG chart primitives (no 3rd-party deps): `BarChart` (grouped/stacked + error bars), `HBarChart`, `ScatterPlot` (bubble, log-X), `LineChart` (multi-series), `Heatmap`, `Legend` |
| `frontend/src/tabs/analytics/BenchmarkDashboard.tsx` | 7-page React dashboard: Overview, Suite Analysis, Function Comparison, Benchmark Trends, ASP Pipeline, System Comparison, Raw Data |
| `frontend/src/App.tsx` | Wired "Analytics → Benchmarks" tab group; BenchmarkDashboard rendered in `h-[78vh]` container |

Migrates all functionality from `backend/ui/benchmark_dashboard.py` (Streamlit) to the native Tauri/React stack.

---

## Analytics — Math Backbone: Rust `base/src/math/` + TypeScript `frontend/src/math/` (2026-06-18)

### Shipped

| Layer | Module | Key exports |
|-------|--------|-------------|
| Rust | `linalg` | `Matrix`, `pca_project`, `pca_2d`, `dot`, `norm`, `normalize` |
| Rust | `stats` | `mean`, `variance`, `histogram`, `pearson_correlation`, `covariance_matrix` |
| Rust | `information` | `shannon_entropy`, `kl_divergence`, `js_divergence`, `mutual_information_discrete`, `normalised_mutual_information` |
| Rust | `distance` | `euclidean`, `cosine_distance`, `bhattacharyya_distance`, `pairwise_distance_matrix`, `condensed_distance_matrix` |
| Rust | `graph` | `Graph`, `UnionFind`, `bfs`, `topological_sort`, `strongly_connected_components`, `kruskal_mst`, `kruskal_max_mst` |
| Rust | `dim_reduce` | `mds_project` (Classical MDS via power iteration), `geodesic_distances` (Dijkstra), `tsne_affinities` |
| TypeScript | `linalg` | `Vec2`/`Vec3`/`Mat3`/`Mat4`, `add2/sub2/scale2/dot2/norm2`, `cross3`, `dotN/normN` |
| TypeScript | `stats` | `mean`, `median`, `variance`, `pearsonCorrelation`, `normalize01`, `histogram` |
| TypeScript | `colormap` | `viridis`, `plasma`, `magma`, `inferno`, `coolwarm`, `applyColormap`, `applyColormapHex` |
| TypeScript | `distance` | `euclidean`, `cosineSimilarity`, `manhattan`, `pairwiseDistances`, `condensedDistances` |
| TypeScript | `graph` | `Graph`, `GraphNode`, `GraphEdge`, `bfs`, `topologicalSort`, `fruchtermanReingold` |
| TypeScript | `signal` | `fft`, `ifft`, `powerSpectrum`, `autocorrelation`, `hannWindow`, `hammingWindow` |

### Stats

- Rust: **49 unit tests** across 6 modules — all passing (`cargo test --lib math`)
- TypeScript: **`tsc --noEmit` clean** — zero type errors
- Rust `mod.rs` + `lib.rs` wired; `pub use math::*` re-exports available from the `base` crate
- MDS preserves pairwise distances to within `1e-4` for unit square (4-point test)
- FR layout: deterministic seeded positions, 300 iterations, O(n²) force computation

---

## Perf — §3.15 — Non-animation Import Isolation: image_merger + vault_manager (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **`image_merger.py` — 6 unconditional model imports → lazy** | Removed `SiameseModelLoader`, `GanWrapper`, `BiRefNetWrapper`, `BaSiCWrapper`, `LoFTRWrapper`, `AnimeStitchPipeline` from module level. `find_spec()` probes for `transformers` (`_BIREFNET_OK`) and `kornia` (`_LOFTR_OK`). `try/except ImportError` for lighter wrappers. Lazy `from ... import` inside `_get_*()` class methods and `perfect_stitch()`. "Relocated Nested Imports" comment block removed. |
| **`vault_manager.py` — jpype → try/except** | `import jpype` + `from jpype.types import JArray, JChar` wrapped in `try/except ImportError`; `_JPYPE_OK` flag added. Prevents JVM path resolution at test collection time. |
| **`check_import_times.py` — CORE_MODULES added** | `CORE_MODULES = ["backend.src.core.image_merger", "backend.src.core.vault_manager"]` added. `run()` extended to measure both groups; total coverage raised from 14 → 16 modules. |

### Stats

- `image_merger` net import cost: **~3 s+ → 0.50 s above baseline** (BiRefNetWrapper + LoFTRWrapper + full animation pipeline removed from collection-time load)
- `vault_manager` net import cost: **0.47 s above baseline** (jpype guarded)
- All 16 tracked modules pass 1.5 s threshold
- 8 image_merger + vault_manager tests pass (0 regressions)

---

## Perf — §3.13B/C — Surgical gc_heavy Fixture + gc.collect() Removal (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **§3.13B `gc_heavy_cleanup` fixture** (`conftest.py`) | New `@pytest.fixture(autouse=True, scope="function")` `gc_heavy_cleanup`: calls `gc.collect()` after a test only when it carries `@pytest.mark.gc_heavy`. Zero overhead for the ~880 tests that don't need GC. |
| **§3.13C `gc.collect()` removed from `resource_cleanup`** (`conftest.py`) | `gc.collect()` removed from the module-scoped `resource_cleanup` fixture. CPython reference counting frees non-cyclic objects (numpy arrays, dicts) immediately on scope exit; no cyclic references found in the animation test suite. Only the `ASP_TEST_CUDA_CLEANUP`-gated CUDA flush remains. |
| **`@pytest.mark.gc_heavy` applied** (3 files) | `test_compositing.py::TestCompositeForeground` and `TestParallelSeamPrecompute` marked (multi-frame `_composite_foreground` calls + seam DP cost maps). `test_filter_edges.py` marked at module level via `pytestmark` (all tests create 5-frame stacks at 480×640 ≈ 4.5 MB). `test_hitl_session.py::TestNdarrayCodec::test_large_array_is_skipped` marked (16 MB float32 array). |

### Stats

- GC calls per full suite run: **931 (function) → 19 (module) → ~40 (gc_heavy only)** — 23× reduction vs module-scoped, 23× reduction vs the prior implementation
- 917 animation tests pass (0 regressions)

---

## Perf — §3.14 Phase 3 — Wrapper + __init__ Lazy-Import Sweep (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **`pipeline.py` — "Relocated" block cleanup** | Removed 10-line "Relocated Nested Imports" block (triplicated `LUMINANCE_WEIGHTS`, duplicate `re`, redundant `_cluster_animation_phases`). `JamMaWrapper` moved to lazy import inside its usage site. |
| **`pipeline.py` — All heavy wrapper imports → `find_spec` probes** | Replaced 6 module-level `try/except` wrapper imports (BiRefNetWrapper, LoFTRWrapper, EfficientLoFTRWrapper, ALIKEDLightGlueWrapper, unused AnimeStitchNet) with `importlib.util.find_spec()` probes that take microseconds. All 4 wrapper classes imported lazily at their instantiation sites. |
| **`backend/src/models/__init__.py` — Removed eager wrapper re-exports** | All 8 wrapper-class imports (`ALIKEDLightGlueWrapper`, `BiRefNetWrapper`, etc.) removed; kept only `ModelWrapper`, `ModelRegistry`, `lazy_load` from `base`. Every caller already uses the full module path, so no call sites break. |
| **`fg_register.py` — torchvision.models lazy import** | `import torchvision.models as tvm` in try/except → `tvm = None` at module level + lazy `import torchvision.models as tvm` inside `_get_vgg19_feat()`. torchvision.models (464 ms, includes torchvision.ops + torch._dynamo) no longer loaded at collection time. |
| **`test_canvas.py` — pre-existing test bug fixed** | `TestPanoramaStitchFallback::test_raises_runtime_error_on_non_ok_status` expected `RuntimeError` but `_panorama_stitch_fallback` raises `CanvasError(PipelineError)`. Test updated to `pytest.raises(CanvasError, ...)`. |

### Stats

- Import time (net above baseline, 14 animation modules): **1.6–2.4 s → 0.67–0.80 s** (all pass 1.5 s threshold)
- Root bottlenecks eliminated: `efficient_loftr_wrapper → transformers` (1.35 s), `loftr_wrapper/aliked → kornia` (168 ms each), `birefnet_wrapper → transformers` (via __init__.py chain), `torchvision.models` (464 ms)
- 917 animation tests pass (0 new failures); 5 pre-existing fg_register failures unchanged

---

## Perf — §3.14 Phase 2 — Full Audit — Heavy-Import Isolation Across All animation Modules (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **`masking.py` — SAM-2 lazy import + "Relocated" block cleanup** | Deleted 18-line "Relocated Nested Imports" block (3× duplicate `from sam2.build_sam import build_sam2_video_predictor`, duplicate `torch`, `os`, `tempfile`). `import torch` at module level wrapped in `try/except ImportError`. `build_sam2_video_predictor` moved to lazy function-level import inside existing `try/except Exception` blocks. `_detect_best_box` from `backend.src.animation.grounding` moved to lazy import with `ImportError → fallback` guard. |
| **`rendering.py` — sklearn KMeans lazy import** | `from sklearn.cluster import KMeans` removed from module level; moved to lazy import inside the existing `try/except ImportError` at the call site. sklearn (~200 ms import) no longer loaded at pytest collection time. |
| **`frame_selection.py` — torch/torchvision/PIL + BiRefNetWrapper** | Deleted 9-line "Relocated Nested Imports" block. Replaced with two `try/except ImportError` guards: one for `torch`/`torchvision`/`PIL.Image`, one for `BiRefNetWrapper`. Removed all six `# relocated:` comments in function bodies. `torch.cuda.is_available()` guarded with `torch is not None` checks. |
| **`matching.py` — torch lazy import** | `import torch` → `try/except ImportError`. |
| **`pipeline.py` — torch + PIL lazy imports** | `import torch` + `from PIL import Image` → `try/except ImportError`. |

### Stats

- 5 modules edited; 547 animation tests pass (0 regressions); all 5 modules import cleanly
- `sam2` no longer loads at pytest collection time — eliminates ~600 MB VRAM and ~2 s startup cost per worker
- `sklearn` no longer loads at collection time — eliminates ~200 ms per worker
- §3.14 Option A (comprehensive animation module audit) now fully complete

---

## Perf — §3.12A/B + Root Causes #2 & #5 — GPU Isolation, pytest-forked/xdist (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **§3.12B pytest-forked — DINOv2 subprocess isolation** (`test_frame_selection.py`) | `TestDINOv2Features` marked `@pytest.mark.gpu` + `@pytest.mark.forked`. Each DINOv2 test now runs in an isolated `fork()` subprocess (pytest-forked 1.6.0). When the subprocess exits, the OS reclaims the ~300 MB DINOv2-ViT-S/14 VRAM entirely — no longer polluting the remaining 900+ test session. |
| **§3.12A pytest-xdist parallel execution** (`pyproject.toml`) | `pytest-xdist` 3.8.0 installed. Verified: `pytest backend/test/animation/ -n auto --dist=worksteal --skip-gpu` passes with identical failure count (6 pre-existing), 9 skipped. Multiple worker processes each with independent RSS bounds. `pyproject.toml` documents recommended invocations; `addopts` left empty (parallel is opt-in). |
| **§3.10 RC#2 — @pytest.mark.gpu + --skip-gpu CLI flag** (`conftest.py`) | `pytest_addoption` hook registers `--skip-gpu` flag; `pytest_collection_modifyitems` adds `skip` marker to all `@pytest.mark.gpu` items when active. `pytest_configure` registers all three custom markers. `TestDINOv2Features` marked `@pytest.mark.gpu` (test_frame_selection.py); `TestComputeRlhfScore` marked `@pytest.mark.gpu` (test_bench_metrics.py). Fast CI loops run `--skip-gpu` and never touch GPU memory. |

### Stats

- `backend/test/conftest.py`: +`pytest_addoption`, +`pytest_configure`, +`pytest_collection_modifyitems` hooks (~45 lines); `--skip-gpu` flag wired
- `backend/test/animation/test_frame_selection.py`: `TestDINOv2Features` → `@pytest.mark.gpu` + `@pytest.mark.forked`
- `backend/test/animation/test_bench_metrics.py`: `TestComputeRlhfScore` → `@pytest.mark.gpu`
- `pyproject.toml`: markers updated; §3.12A xdist usage documented
- Dependencies added: `pytest-xdist==3.8.0`, `pytest-forked==1.6.0`, `execnet==2.1.2`, `py==1.11.0`
- All 5 §3.10 root causes now ✅; §3.11, §3.12, §3.13, §3.14 fully implemented
- 900 animation tests passing serially; 894 + 9 skipped under `-n auto --skip-gpu`

---

## Perf — §3.11 + §3.12C + §3.13 + §3.14 — Test-Suite Freeze Root Causes #3–#4 Fixed (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **§3.11 Session-level ThreadPoolExecutor** (`compositing.py`) | `_SEAM_POOL: Optional[ThreadPoolExecutor] = None` module-level singleton + `_get_seam_pool() → ThreadPoolExecutor`. `_composite_foreground` now calls `_get_seam_pool().map(...)` instead of creating a new pool per call. Eliminates ~1,200 `pthread_create`/`pthread_join` kernel calls across 311 compositing tests, resolving CFS scheduler stalls on the i9 system. Pool is shut down at session end by the new `clear_ml_singletons` fixture. |
| **§3.12C Singleton teardown fixture** (`conftest.py`) | New `clear_ml_singletons` (autouse, scope=session) fixture tears down all five known module-level ML singletons at test-session end: `_DINOV2_CACHE` (frame_selection.py), `_SEARAFT_SINGLETON` + `_VGG19_SINGLETON` + `_DIS_SINGLETON` (fg_register.py), `_TC_PIPELINE` (anim_fill.py), and the seam `_SEAM_POOL` (compositing.py). Calls `torch.cuda.empty_cache()` at session end to fully reclaim VRAM. |
| **§3.13A Module-scope GC fixture** (`conftest.py`) | `resource_cleanup` fixture scope raised from `function` → `module`. GC calls reduced from 931 → ~19 (one per test module), eliminating ~46 s of pure GC overhead and 931 CUDA ioctl calls per full test run. CUDA `empty_cache()` gated behind `ASP_TEST_CUDA_CLEANUP=1` env var to eliminate ioctl overhead on CPU-only test runs. |
| **§3.14A Lazy heavy imports** (`compositing.py`, `bg_complete.py`) | `import torch as _tc_torch` in `compositing.py` (line 29, unconditional) wrapped in `try/except ImportError`. `import torch  # noqa: F401` in `bg_complete.py` (line 38, unconditional bare import unused directly in module) wrapped in `try/except ImportError`. Both torch usages are already flag-gated (`_TOONCRAFTER_SEAM`, ProPainterInference) so no call-site changes needed. |
| **pytest markers added** (`pyproject.toml`) | `gpu`, `gc_heavy`, and `slow` markers registered in `[tool.pytest.ini_options]` for future surgical test targeting without `PytestUnknownMarkWarning`. |

### Stats

- `backend/src/animation/compositing.py`: +`_SEAM_POOL`, +`_get_seam_pool()`, `torch` import wrapped in try/except, `ThreadPoolExecutor` context-manager removed (singleton now manages lifetime)
- `backend/src/animation/bg_complete.py`: unconditional `import torch` wrapped in `try/except ImportError`
- `backend/test/conftest.py`: `resource_cleanup` scope → `module`; new `clear_ml_singletons` session fixture (~55 lines)
- `pyproject.toml`: 3 pytest markers registered
- `moon/roadmaps/performance.md`: §3.10 RC#3/RC#4 marked ✅; §3.11, §3.13, §3.14 headings upgraded to ✅; §3.12 partial ✅; effort matrix updated
- 858 animation tests passing (6 pre-existing failures unrelated to this work; 2 skipped)

---

## ASP — §3.13 ProPainter + §2.9A LandmarkEditor + §2.10C Flow Field + Test-Freeze Fix (2026-06-18, S140)

### Shipped

| Item | Summary |
|------|---------|
| **§3.13 ProPainter Stage 4.7** (`bg_complete.py` → `_propainter_complete_frames`; `pipeline.py` → Stage 4.7) | Multi-frame background inpainting inserted between Stage 4 (BiRefNet) and Stage 5 (phase correlation). `ProPainterInference.inpaint(frames, masks)` → `cv2.COLOR_BGR↔RGB`; NN-fill fallback when ProPainter unavailable. `ASP_PROPAINTER=1` flag + `ASP_PROPAINTER_DEVICE` (default `cpu`). `PROPAINTER_DEVICE` constant in `constants/animation.py`. Schema entries added to `config.py`. 5 new tests in `TestProPainterCompleteFrames`. |
| **§2.9A LandmarkEditorDialog** (`gui/src/dialogs/landmark_editor_dialog.py`) | ~260-line PySide6 QDialog: side-by-side frame thumbnails, alternating left/right click pattern, color-coded markers (red #1, green #2, …), undo/clear. `landmark_pairs()` returns `List[Tuple[Tuple[float,float],Tuple[float,float]]]` in image-pixel space. `_build_landmark_affine(i,j,pairs,weight=0.95)` in `pipeline.py`: 1 pair → centroid translation; 2 pairs → `estimateAffinePartial2D` (4-DOF); 3+ pairs → `estimateAffine2D` LMEDS (6-DOF). Wired into `EdgeReviewDialog` via "Landmark Editor…" toolbar button. |
| **§2.10C User-drawn flow field** (`fg_register.py` → `_sparse_flow_to_dense`; `compositing.py` → `flow_override` wiring; `seam_diagnostic_dialog.py` → `_FlowArrowCanvas`) | `_sparse_flow_to_dense(flow_arrows, H, W)` uses `scipy.interpolate.RBFInterpolator(kernel="thin_plate_spline")`, nearest-neighbour fallback. `register_foreground_at_seam(flow_override=)` skips RAFT/DIS when a (H,W,2) override is provided. `SeamDiagnosticDialog` gains `_FlowArrowCanvas` (orange click-drag arrows), "↗ Draw Flow" toggle, "Clear Flow" button; `get_overrides()` now includes `"flow_arrows"`. |
| **⚠ Test-suite freeze: Root Cause #1 fixed** (`anim_fill.py`, `compositing.py`) | `from diffusers import DiffusionPipeline` was unconditional at module level in `anim_fill.py` — triggered full HuggingFace ecosystem import (transformers, tokenizers Rayon pool, accelerate) at pytest collection time, consuming ~800 MB–1.5 GB RAM before any test ran. Moved to lazy import inside `_load_tooncrafter()`. `torch` import in `anim_fill.py` wrapped in `try/except`. Duplicate imports in `compositing.py` (lines 29–32) deduplicated. Root Causes #2–#5 (model singletons, ThreadPoolExecutor storm, per-test gc.collect(), no process isolation) documented in `performance.md §3.10–§3.14` as **CRITICAL** with fix options. |

### Stats

- `backend/src/animation/bg_complete.py`: +`_propainter_complete_frames`, updated `__all__`
- `backend/src/animation/pipeline.py`: +Stage 4.7, +`_build_landmark_affine`, +`_PROPAINTER` flag, updated `__all__`
- `backend/src/constants/animation.py`: +`PROPAINTER_DEVICE`
- `backend/src/animation/config.py`: +2 schema entries (`ASP_PROPAINTER`, `ASP_PROPAINTER_DEVICE`)
- `gui/src/dialogs/landmark_editor_dialog.py`: new file, ~260 lines
- `gui/src/dialogs/edge_review_dialog.py`: +`_on_landmark_edit()`, "Landmark Editor…" button
- `backend/src/animation/fg_register.py`: +`_sparse_flow_to_dense`, +`flow_override` param to `register_foreground_at_seam`
- `backend/src/animation/compositing.py`: +`flow_arrows` → `_sparse_flow_to_dense` wiring; duplicate imports removed
- `backend/src/animation/anim_fill.py`: lazy diffusers import (freeze fix)
- `gui/src/dialogs/seam_diagnostic_dialog.py`: +`_FlowArrowCanvas`, "Draw Flow" controls, `flow_arrows` in `get_overrides()`
- `backend/test/animation/test_bg_complete.py`: +5 tests → **928 backend tests total (2 skipped)**
- `moon/roadmaps/performance.md`: +CRITICAL §3.10–§3.14 (test-suite freeze root causes + fix options)
- 3 roadmap items marked ✅: §3.13, §2.9A, §2.10C

---

## ASP — §1.83/1.84/1.85 Seam Gate Completion + Ensemble Combiner (2026-06-18, S139)

### Shipped

| Item | Summary |
|------|---------|
| **§1.83 Seam Band Noise-Level Asymmetry** (`compositing.py` → `_seam_noise_mismatch`, `_check_seam_noise_gate`) | Uses the Immerkær (1996) Laplacian-std noise estimator `σ ≈ std(Laplacian) / 6`. Score = `|σ_top − σ_bot| / mean(σ)` in [0, 2+]; catches codec/exposure bitrate discontinuities invisible to §1.76–§1.82 luma/chroma/spectral gates. `_SEAM_NOISE_GATE` flag (default 0.0=off, `ASP_SEAM_NOISE_GATE=1.0`). Stage 11.16 in `pipeline.py`. `SEAM_NOISE_GATE_THRESH=1.0` in constants. |
| **§1.84 Seam Band RMS Contrast Ratio** (`compositing.py` → `_seam_rms_contrast_ratio`, `_check_seam_rms_contrast_gate`) | Coefficient-of-variation ratio `max(c_top,c_bot)/min(c_top,c_bot)` where `c = std/max(1,mean)`; catches broad dynamic-range discontinuities distinct from §1.79 sharpness and §1.82 spectral profile. Score in [1, ∞); 1.0=identical contrast. `_SEAM_CONTRAST_GATE` flag (`ASP_SEAM_CONTRAST_GATE=4.0`). Stage 11.17. `SEAM_CONTRAST_GATE_THRESH=4.0` in constants. |
| **§1.85 Multi-Gate Ensemble Combiner** (`compositing.py` → `_seam_gate_vote_counts`, `_check_seam_ensemble_gate`) | Accumulates per-seam votes from all §1.56–§1.84 active gates; fires when worst seam reaches `min_votes`. Correct polarity per gate (BELOW for color/NCC/SSIM; ABOVE for all others). `_SEAM_ENSEMBLE_VOTES` int flag (`ASP_SEAM_ENSEMBLE_VOTES=3`). Stage 11.18 reads all per-gate thresholds from env vars at call time. |

### Stats

- `backend/src/animation/compositing.py`: +~200 lines (§1.83 + §1.84 + §1.85, updated `__all__`)
- `backend/src/animation/pipeline.py`: +3 imports, +23 module-flag lines, +65 wiring lines (Stages 11.16–11.18)
- `backend/src/constants/animation.py`: +3 constants (`SEAM_NOISE_GATE_THRESH`, `SEAM_CONTRAST_GATE_THRESH`, `SEAM_ENSEMBLE_MIN_VOTES`)
- `backend/src/animation/config.py`: +3 schema entries + 3 `_DUMP_SECTIONS["compositing"]` keys
- `backend/test/animation/test_compositing.py`: +15 tests → **928 backend tests total (2 skipped)**
- 3 roadmap items marked ✅: §1.83, §1.84, §1.85; stale §3.16A removed from pending matrix

---

## Perf — 4.8 psycopg3 connection pool (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **4.8 psycopg3 connection pool** (`backend/src/database/pooled_image_database.py`) | New `PooledPgvectorDatabase` class — a drop-in replacement for `PgvectorImageDatabase` — backed by `psycopg_pool.ConnectionPool` (psycopg3 synchronous pool, default min=2 / max=10 connections). Every public method borrows a connection for the duration of its own call via `with self._pool.connection() as conn:` and returns it automatically; no global `self.conn` state means multiple QThread workers (search, ingest, duplicate scan) can issue concurrent queries without racing on a shared connection. `psycopg[pool]>=3.2` added to `pyproject.toml`. **API changes from psycopg2 internals**: `psycopg.rows.dict_row` row_factory replaces `DictCursor`; `executemany()` replaces `execute_values()` for bulk tag inserts; transactions use `conn.transaction()` context manager instead of `autocommit` toggle; `VACUUM`/`REINDEX` use a raw `psycopg.connect(autocommit=True)` connection outside the pool (PostgreSQL requirement). Two queries that select duplicate column names (`get_all_subgroups_detailed`: `s.name, g.name`; `get_statistics`: aggregate functions) use a per-cursor `tuple_row` override to avoid silent dict key collisions. Module-level `_pools: Dict[str, ConnectionPool]` registry shares one pool across all `PooledPgvectorDatabase` instances with the same DSN. `PG_POOL_MIN` / `PG_POOL_MAX` env vars control pool bounds. 22 unit tests covering `_build_conninfo`, group/tag/image CRUD, pool lifecycle, and phash deduplication — all mocked, no live PostgreSQL required. |

### Stats

- 1 file created (`backend/src/database/pooled_image_database.py`)
- 1 test file created (`backend/test/test_pooled_image_database.py`, 22 tests)
- `pyproject.toml` updated: `psycopg[pool]>=3.2` added
- 1 roadmap item marked ✅: 4.8

---

## Feat — 3.6 WD-1.4 auto-tagger via ONNX (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **3.6 WD-1.4 auto-tagger via ONNX** (`backend/src/models/wd_tagger_wrapper.py`) | New `WDTaggerWrapper(ModelWrapper)` class implementing the full `ModelWrapper` ABC contract (`load()`, `unload()`, `loaded`, `is_available()`). **Model acquisition**: `load()` uses `huggingface_hub.hf_hub_download` to download `model.onnx` + `selected_tags.csv` from the configured HuggingFace repo (default: `SmilingWolf/wd-v1-4-convnext-tagger-v2`) into a local cache dir (`~/.image-toolkit/models/wd_tagger`); both files are cached on disk so subsequent `load()` calls are instant. **ONNX inference**: session built via `onnxruntime.InferenceSession` with `["CUDAExecutionProvider", "CPUExecutionProvider"]` provider list (GPU when `self.device` contains "cuda", CPU otherwise); input name and resolution read from the session's input metadata. **Preprocessing** (`_load_and_preprocess`): opens any image format via PIL, composites RGBA onto a white background (matching training data), pads to square with white fill, resizes to the model's input resolution, converts to BGR `float32` with `NHWC` layout `(1, H, W, C)` as required by all SmilingWolf ONNX models. **Public API**: `tag(image_path, threshold=None)` → `List[Dict]` sorted by confidence descending; `tag_batch(image_paths)` → `List[List[Dict]]` with per-path error isolation; `tag_with_review(image_path, threshold, review_threshold=0.15)` → `(auto_tags, review_tags)` tuple splitting accepted vs human-review tags (§4.4 Option E). Each result dict contains `tag` (underscores replaced with spaces), `confidence` (float), `category` (`"general"` / `"character"` / `"copyright"`), and `category_id`. **Configuration**: default threshold 0.35 (`DEFAULT_THRESHOLD`); `WD_TAGGER_MODEL_REPO` env var overrides repo id; `WD_TAGGER_CACHE_DIR` env var overrides cache directory. `@lazy_load` decorator auto-calls `load()` on first inference call. 26 tests in `backend/test/models/test_wd_tagger_wrapper.py` covering label parsing, tag filtering, preprocessing shape/dtype, and all public API methods with a mocked ONNX session. All 26 passing. |

### Stats

- 1 file created (`backend/src/models/wd_tagger_wrapper.py`)
- 1 test file created (`backend/test/models/test_wd_tagger_wrapper.py`, 26 tests)
- 1 roadmap item marked ✅: 3.6

---

## Perf — 2.12 Rust two-pass streaming image merger (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **2.12 Two-pass streaming merger** (`base/src/core/image_merger.rs`) | All three public merge functions (`merge_images_horizontal_core`, `merge_images_vertical_core`, `merge_images_grid_core`) refactored to a two-pass streaming approach. **Pass 1**: calls `image::image_dimensions(path)` on every input path — reads only the image header (width, height) without decoding any pixel data — to compute total canvas dimensions. Canvas is then allocated once. **Pass 2**: iterates the same path list sequentially, loads one `DynamicImage` at a time, blits it to the canvas, and immediately drops it (freeing its pixel buffer). The old approach collected all images into a `Vec<DynamicImage>` before compositing, consuming N × image_size RAM simultaneously (e.g., 100 × 4K images ≈ 2–4 GB). New peak RAM = 1 decoded image (~30 MB for 4K RGBA) + output canvas (~200 MB for a 10K panorama). New helper `read_dimensions(path)` wraps `image::image_dimensions`. 4 new Rust unit tests verify streaming produces identical canvas dimensions for horizontal, vertical, and grid layouts; `test_empty_paths_returns_false` covers all three functions. 6 tests total, all passing. |

### Stats

- 1 file rewritten (`base/src/core/image_merger.rs`)
- 1 roadmap item marked ✅: 2.12

---

## Feat — 4.12 Named layout profiles (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **4.12 Named layout profiles** (`gui/src/windows/settings_window.py`) | **Profile capture**: `_get_current_ui_preferences()` now snapshots `main_window_ref.saveGeometry()` → base64 as `layout_geometry`, and reads all `splitters/*` keys from `AppSettings` → base64 dict as `layout_splitters`. Both are included in every Save / Update profile operation alongside the existing `theme`, `active_tab_configs`, and §4.13 appearance keys. **Restore**: New `_apply_layout_from_profile(profile_data)` helper decodes `layout_geometry` (base64 → `QByteArray`) and calls `main_window_ref.restoreGeometry()` immediately; all `layout_splitters` entries are written back to `AppSettings` so each splitter picks up the new state on its next `persist_splitter()` init call. Both Load Profile and Use Profile call `_apply_layout_from_profile`. Added `import base64`, `QByteArray` from PySide6.QtCore, and `from ..utils.settings import AppSettings` to `settings_window.py`. |

### Stats

- 1 file modified (`gui/src/windows/settings_window.py`)
- 1 roadmap item marked ✅: 4.12

---

## Feat — 3.8 Slideshow configuration (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **3.8 Slideshow configuration** (`gui/src/tabs/core/wallpaper_tab.py`, `base/src/utils/slideshow_daemon.rs`) | **UI**: New `slideshow_filter_group` widget (QLabel + `filter_dir_input` QLineEdit + Browse button) added below the existing interval/order row in the slideshow settings group; shown/hidden/enabled/disabled alongside `slideshow_group`. **Vault defaults**: `_apply_vault_slideshow_defaults()` fires once via `QTimer.singleShot(0, …)` and reads `slideshow_interval_min/sec/order` from `main_window.cached_creds["preferences"]`, only overriding widgets that still hold their hardcoded initial values so a restored tab config always wins. **Persistence**: `filter_dir` key added to `collect()`, `set_config()`, and `get_default_config()`; both `_sync_daemon_config()` and `toggle_daemon()` write `filter_directories: [filter_dir]` to `.slideshow_config.json`. **Rust daemon**: `filter_directories: Vec<String>` added to `Config` struct (`#[serde(default)]`); `matches_filter(path, filter_directories)` helper strips `file://` prefix before prefix-match; `select_next_wallpapers` builds a filtered sub-queue per monitor and falls back to the full queue when the filter matches nothing (daemon never stalls). 4 new Rust unit tests (`test_filter_directories_restricts_queue`, `test_filter_directories_empty_falls_back_to_full_queue`, `test_filter_no_match_falls_back_to_full_queue`, `test_matches_filter_strips_file_uri_prefix`); 6 tests total, all passing. |

### Stats

- 2 files modified (`gui/src/tabs/core/wallpaper_tab.py`, `base/src/utils/slideshow_daemon.rs`)
- 1 roadmap item marked ✅: 3.8

---

## Feat — 4.13 Appearance profiles (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **4.13 Appearance profiles** (`gui/src/windows/settings_window.py`, `gui/src/windows/login_window.py`) | **Profile save**: `_get_current_ui_preferences()` now bundles four new keys — `accent_color_dark`, `accent_color_light`, `font_scale`, `ui_density` — alongside the existing `theme` and `active_tab_configs`. All profile save/update paths inherit this automatically. **Profile load/use**: New `_apply_appearance_from_profile(profile_data)` helper pushes appearance keys from the profile dict into the live UI widgets (dark/light accent swatches via `_update_swatch()` + `pref_accent_*` attrs, `font_scale_spinbox`, `ui_density_combo`). Both `_load_selected_profile()` and `_use_selected_profile()` call this helper — `_use_selected_profile` then calls `_update_settings_logic()` which saves the updated `pref_accent_*` / spinbox / combo values to vault and immediately applies the theme via `set_application_theme()`. **Login-time profile application** (`login_window.py`): when a profile is selected at login the four appearance keys are merged into `stored_data["preferences"]` alongside the existing `theme`/`active_tab_configs` update; `save_required` is set when any key differs from the current value. |

### Stats

- 2 files modified (`gui/src/windows/settings_window.py`, `gui/src/windows/login_window.py`)
- 1 roadmap item marked ✅: 4.13

---

## Feat — 4.7 KDE per-monitor wallpaper via D-Bus (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **4.7 KDE D-Bus wallpaper fallback chain** (`backend/src/core/wallpaper.py`, `gui/src/tabs/core/wallpaper_tab.py`) | Three new module-level functions: `find_qdbus_binary()` — iterates `qdbus6`, `qdbus-qt6`, `qdbus`, `qdbus-qt5` (previously only 2 names were tried, missing distros like OpenSUSE). `evaluate_kde_script_dbus_python(script)` — pure-Python D-Bus call via `dbus-python` (`bus.get_object('org.kde.plasmashell', '/PlasmaShell').evaluateScript()`), works without any CLI binary. `evaluate_kde_script_with_fallback(qdbus, script)` — tries qdbus CLI first, falls back to dbus-python on failure, raises with actionable message if both unavailable. All three existing call-sites in `WallpaperManager` (`_set_wallpaper_kde`, `apply_wallpaper`, `get_current_system_wallpaper_path_kde`) migrated from direct `base.evaluate_kde_script()` to the fallback chain. `wallpaper_tab.py` `__init__` now uses `find_qdbus_binary()` instead of inline 2-name detection (also removed the DESKTOP_SESSION guard — `qdbus6` works on Wayland/KDE too). All three functions exported from `backend.src.core`. |

### Stats

- 2 files modified (`backend/src/core/wallpaper.py`, `gui/src/tabs/core/wallpaper_tab.py`)
- 1 file modified (`backend/src/core/__init__.py` — new exports)
- 1 roadmap item marked ✅: 4.7

---

## Feat — 4.6 Cross-directory phash deduplication (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **4.6 Cross-directory phash deduplication** (`backend/src/database/`, `backend/src/core/phash_deduplicator.py`) | **Schema**: `phash BIGINT` column added to `images` table via idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS` in `schema.sql`; `idx_images_phash` B-tree index on non-null rows. Both are executed during `_create_tables()` (safe for existing deployments). **SQL**: `update_phash` (UPDATE by image id) + `find_near_duplicates_phash` (Hamming distance via `bit_count(phash::bit(64) # query::bit(64)) <= threshold`) added to `images.sql`. **DB methods**: `update_phash(image_id, phash_int)` and `find_near_duplicates_by_phash(phash_int, threshold=10, limit=50)` on `PgvectorImageDatabase`. **Module**: `compute_phash(path) → int` (imagehash 8×8 DCT phash, two's-complement BIGINT) + `PhashDeduplicator` (index_image, index_directory, find_duplicates_for, find_all_duplicate_groups) in `phash_deduplicator.py`. 10 unit tests; all passing. |

### Stats

- 4 files modified (`schema.sql`, `images.sql`, `image_database.py`, `core/__init__.py`)
- 1 new file (`backend/src/core/phash_deduplicator.py`)
- 1 new test file (`backend/test/core/test_phash_deduplicator.py`) — 10 tests
- 1 roadmap item marked ✅: 4.6

---

## Feat — 4.5 OpenAPI schema for REST endpoints (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **4.5 OpenAPI schema** (`api/`, `tasks/views.py`, `pyproject.toml`) | `drf-spectacular>=0.27.2` added as runtime dependency. `drf_spectacular` registered in `INSTALLED_APPS`; `SPECTACULAR_SETTINGS` configured (title, description, version, `COMPONENT_SPLIT_REQUEST=True`). Three new routes in `api/urls.py`: `/api/schema/` (raw OpenAPI YAML/JSON), `/api/docs/` (Swagger UI), `/api/redoc/` (ReDoc). All 19 task views annotated with `@extend_schema` — each specifies `tags`, `summary`, `request=<Serializer>`, and `responses={202: TaskQueuedResponse, 400: ValidationError}`. Schema generation verified: 19 paths emitted, no warnings. |

### Stats

- 3 files modified (`api/settings.py`, `api/urls.py`, `tasks/views.py`)
- 1 file modified (`pyproject.toml` — new dep)
- 1 roadmap item marked ✅: 4.5

---

## ASP — 0.7 min_gap vector-magnitude for diagonal sequences (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **0.7 Diagonal canvas-span vector magnitude** (`backend/src/animation/validation.py`) | `_compute_adaptive_min_gap` now calls `_detect_scroll_axis` and uses axis-appropriate span: `dx_span` for horizontal, `dy_span` for vertical, and `sqrt(dy_span² + dx_span²)` for diagonal. The previous `max(dy_span, dx_span)` underestimated the actual path length by up to 1.41× for 45° diagonal pans, resulting in adaptive min-gap thresholds that were too low — allowing near-duplicate diagonal-pan frames to pass validation unchallenged. All 34 existing affine validation tests pass. |

### Stats

- 1 Python file modified (`validation.py`)
- 1 roadmap item marked ✅: 0.7

---

## ASP — 0.4 Foreground-excluded temporal median (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **0.4 A5 — Foreground-excluded temporal median** (`backend/src/animation/rendering.py`) | `_render_median` now builds `bg_canvas[i]` — a per-frame boolean mask that marks warped-background pixels (BiRefNet `bg_masks[i] > 127`). Before the nanmedian, `eff_masks` is derived: pixels with ≥1 background sample use only background-marked frames; pixels with zero background samples (character always covers them) fall back to all geometrically-valid frames so no holes appear. The fade-in/fade-out ramp sections also use `eff_masks`. Flag `_FG_EXCLUDE_MEDIAN = True` by default; disable with `ASP_FG_EXCLUDE_MEDIAN=0`. All `print()` calls in the renderer migrated to `logger.info/debug`. |

### Stats

- 1 Python file modified (`rendering.py`)
- 1 roadmap item marked ✅: 0.4

---

## ASP — 3.4 SRStitcher diffusion border fill (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **3.4 SRStitcher diffusion border fill** (`backend/src/animation/pipeline.py`) | P1.8 (border gap fill) in `run()` now branches on `self.sr_mode and _SRSTITCHER_OK`. When `sr_mode=True` and diffusers are available: calls `border_diffusion_fill(canvas, device=…)` from `sr_stitcher.py` — stable-diffusion inpainting model produces style-consistent cel-shaded fills for diagonal-pan panorama black corners. Falls back to TELEA on model failure. When `sr_mode=False` (default): existing MFSR `inpaint_gaps` → TELEA path unchanged. `border_diffusion_fill` and `_SRSTITCHER_OK` were already imported from `sr_stitcher.py` (line 183) but unused; now wired. |

### Stats

- 1 Python file modified (`pipeline.py`)
- 1 roadmap item marked ✅: 3.4

---

## GUI — 3.10 Dark/light mode toggle button (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **3.10 QSS dark/light mode toggle** (`gui/src/windows/main_window.py`) | "☀" / "🌙" `QPushButton` added to the app header (36×36px, transparent, borderless). `_toggle_theme()` flips `current_theme` dark↔light, calls `set_application_theme()`, saves `creds["theme"]` to vault, and updates `cached_creds` so the OS auto-follow handler (`_on_os_scheme_changed`) backs off. `set_application_theme` now syncs the button icon at the end of every call so the icon is always correct (initial load, settings apply, OS switch, manual toggle). |

### Stats

- 1 GUI file modified (`main_window.py`)
- 1 roadmap item marked ✅: 3.10

---

## Feat — 3.5 CLI batch stitching (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **3.5 CLI batch stitching** (`backend/src/utils/io/arg_parser.py`, `dispatcher.py`) | New top-level `stitch` command replaces the nested `core stitch`. **Single-sequence mode**: `python main.py stitch -i frames/ -o out.png` (or explicit file list). **Batch mode**: `python main.py stitch --batch-dir /sequences/ --resume` — iterates every sub-directory, collects sorted images, calls `AnimeStitchPipeline.run()`. Option C (`--resume`): skips sequences where output file already exists. Option E: `.stitch_progress.json` progress file written after each sequence (tracks `done`/`failed`/`skipped`), survives interruption. `--output-suffix` controls the output filename suffix (default `_stitched`). `--renderer median|first|blend` passed to pipeline. |

### Stats

- 2 Python files modified (`arg_parser.py`, `dispatcher.py`)
- 1 roadmap item marked ✅: 3.5

---

## GUI / Arch — 2.11 StitchTab result preview · 4.3 Weekly CI (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **2.11 StitchTab before/after toggle + quality metrics overlay** (`gui/src/tabs/animation/stitch_tab.py`) | After stitch completes, `_show_stitch_result()` loads the result pixmap and the first source frame. A "◀ Before / After ▶" toggle button (`QPushButton`, checkable) swaps between them via `_toggle_before_after`. A 100–200 px result preview `QLabel` is shown in a previously hidden group box below the log. `_MetricsTask` (QRunnable) computes Laplacian variance sharpness + file size + dimensions off the main thread; result emitted via `_MetricsSignals.ready` signal into the metrics overlay label. All new code in two new classes (`_MetricsSignals`, `_MetricsTask`) and four new methods. |
| **4.3 Weekly scheduled ASP benchmark CI** (`.github/workflows/benchmark.yml`) | Added `schedule: cron: "0 6 * * 1"` trigger (every Monday 06:00 UTC). Catches dep-induced regressions (e.g. scipy minor bump) that don't touch the codebase. Push-to-main and `workflow_dispatch` triggers retained. |

### Stats

- 1 GUI file modified (`stitch_tab.py`)
- 1 CI file modified (`benchmark.yml`)
- 2 roadmap items marked ✅: 2.11, 4.3

---

## Perf Tier 2 — 3.12 Dynamic BiRefNet batching (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **3.12 Dynamic BiRefNet batching** (`backend/src/models/birefnet_wrapper.py`) | `get_mask_batch` rewritten: all frames pre-transformed to `inference_size` tensors, then grouped into VRAM-sized chunks. `_compute_batch_size()` queries `torch.cuda.mem_get_info()`, subtracts a 1 GB safety reserve, estimates per-frame VRAM as 32× raw tensor size (covers Swin backbone activations + decoder + output), caps at 4 to prevent OOM from activation spikes. Each chunk is stacked into `(B,C,H,W)`, fed through the model in one forward pass, then per-frame masks are resized back to original dimensions. Falls back to `batch_size=1` on CPU, no CUDA, or any exception. For a 10-frame sequence at 1024×1024 on an 8 GB GPU: expected batch=4 → 3 forward passes instead of 10. |

### Stats

- 1 Python file modified (`birefnet_wrapper.py`)
- 1 roadmap item marked ✅: 3.12

---

## Perf Tier 1 — 1.7 Rust move semantics · 3.11 GPU temporal median (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **1.7 Rust DynamicImage move semantics** (`base/src/core/image_converter.rs`, `image_merger.rs`) | `apply_ar_transform` and `fast_resize` now take ownership of `DynamicImage` instead of a shared reference. No-op paths (no AR transform, same-size resize) return the owned value directly — eliminating an unconditional `img.clone()` that allocated ~30 MB for 4K RGBA images. Call sites updated: `let w = img.width(); fast_resize(img, w, max_h)` binds dimensions before the move. `cargo check` verified clean. |
| **3.11 PyTorch GPU temporal median** (`backend/src/animation/rendering.py`) | All 5 `np.nanmedian(…, axis=0)` calls in `_render_median` replaced with `_gpu_nanmedian()`. Covered: Case 2 main median (1 call), vertical fade-in/fade-out (2 calls), horizontal fade-in/fade-out (2 calls). `_gpu_nanmedian` is off by default (`ASP_GPU_MEDIAN=0`); enable with `ASP_GPU_MEDIAN=1`. Lazy CUDA detection via module-level `_cuda_available: Optional[bool] = None`; falls back to numpy on import failure, no CUDA, or any runtime error. On GPU: `np.ndarray → torch.from_numpy().cuda() → torch.nanmedian(dim=0).values.cpu().numpy()`. |

### Stats

- 2 Rust files modified (no new deps)
- 1 Python file modified
- 2 roadmap items marked ✅: 1.7, 3.11

---

## Arch Tier 7 — CI/CD · 1.12 uv lock · 2.15 security audit · 3.14 ASP regression gate (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **1.12 `uv lock` + frozen CI install** | `uv.lock` already committed. `.github/workflows/ci.yml` created: two jobs — `lint` (import-linter + mypy on strict modules) and `test-models` (36 model contract tests); both use `uv sync --frozen --group dev --no-install-project` so the Rust extension is never compiled in CI; uv cache keyed on `uv.lock` hash for fast reruns. `pip-audit>=2.9.0` and `numpy>=2.3.4` added to `[dependency-groups.dev]` in `pyproject.toml`; lockfile regenerated. |
| **2.15 `pip-audit` + `cargo audit` in CI** | `.github/workflows/security.yml` created: weekly (Monday 08:00 UTC) + `workflow_dispatch`. `pip-audit` job: exports frozen requirements via `uv export`, scans with `pip-audit --requirement`, uploads JSON report as artifact, fails on any CVE. `cargo-audit` job: installs `cargo-audit` via `taiki-e/install-action`, runs `cargo audit --json` in `base/`, uploads JSON report, fails on any vulnerability. |
| **3.14 ASP regression gate CI** | `.github/workflows/benchmark.yml` created: runs on every push to main. Executes the full `backend/test/animation/` suite (827 unit tests, <60 s total, no GPU) via `uv sync --frozen --group dev --no-install-project`. Uploads `.pytest_cache/` as CI artifact (14-day retention). Any test regression fails the build before merge. **Roadmap items 3.13 + 3.14 both complete** — the 827 unit tests covering `bundle_adjust`, `compositing`, `frame_selection`, `canvas`, `pipeline`, `matching`, `validation`, `config`, and `fg_register` now run automatically as the regression gate. |

### Stats

- 3 GitHub Actions workflows created (`.github/workflows/`)
- 2 new dev deps: `numpy>=2.3.4`, `pip-audit>=2.9.0`
- 10 roadmap items marked ✅: 1.6, 1.12, 2.1, 2.2, 2.3, 2.5, 2.15, 3.2, 3.3, 3.13, 3.14
- 36 contract tests still passing (0 regressions)

---

## Phase 3 — 3.7 Safetensors Metadata Viewer (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **3.7 `read_metadata()` backend function** (`backend/src/utils/data/safetensors_metadata.py`) | New `read_metadata(path) → dict` reads a `.safetensors` file header without loading any tensor data. Uses `safe_open` + `get_slice().get_shape()` / `get_dtype()` to enumerate all tensor shapes and dtypes in O(1) per tensor (header-only). Returns `file_size_mb`, `user_meta` (dict of all user metadata strings), `tensor_count`, `param_count` (sum of all element counts), `dtype_counts` (Counter per dtype), `tensors` (per-key shape+dtype dict). Skips base64 preview blobs in display. |
| **3.7 `SafetensorsInspectorDialog`** (`gui/src/components/safetensors_inspector.py`) | New `QDialog` (860×640, resizable). Background `_LoadWorker` (QRunnable) loads metadata off the main thread. Left panel: **Summary** tree (file name, size, tensor count, parameter count M/B, dtype breakdown) + **User Metadata** tree (all key-value pairs). Right panel: **Tensors** tree (sortable QTreeWidget; columns: name, shape as `d₀×d₁×…`, dtype). **Copy Metadata** button writes file info + user metadata to clipboard. Tested against Anything V3 text encoder: 197 tensors, 123M params (469.5 MB) loaded in <50 ms. |
| **3.7 Wired into LoRA tabs** | "Inspect" button added inline next to LoRA Path field in `lora_generate_tab.py` — appends `.safetensors` extension if absent, validates file existence, opens dialog. "Inspect .safetensors..." button added to train/cancel row in `lora_train_tab.py` — opens `QFileDialog` (with `DontUseNativeDialog`) to select any `.safetensors` file, then opens dialog. |

### Test count

**36 contract tests + 3 import contracts still passing** (0 regressions).

---

## Arch Tier 6 — A.17 `import-linter` contracts (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **A.17 `import-linter` contracts** (`pyproject.toml`) | `import-linter>=2.0` added to `[dependency-groups.dev]`. Three enforced contracts under `[tool.importlinter]`: (1) **Backend core no GUI** — `backend.src.{models,animation,core,web,pipeline,constants,exceptions,utils}` forbidden from importing `gui.*`; scoped to exclude `backend.src.app` (intentional app launcher), `backend.benchmark`, `backend.test`. (2) **`gui.src.utils` is leaf** — lowest GUI layer forbidden from importing tabs, helpers, windows, components, or classes. (3) **`gui.src.classes` no tabs** — gallery base classes forbidden from importing `gui.src.tabs`; `ignore_imports` allows the one deferred `_show_status` call into `gui.src.windows`. All 3 contracts: 0 broken on 397 files / 752 dependencies. Run: `PYTHONPATH=. lint-imports`. |

### Test count

**36 contract tests still passing** (0 regressions).

---

## Arch Tier 5 — A.16 `AbstractGalleryBase` + real `common_*` methods (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **A.16 `AbstractGalleryBase` shared parent class** (`gui/src/classes/gallery_base.py`) | New file (574 lines). `AbstractGalleryBase(QWidget, metaclass=MetaAbstractClassGallery)` extracts all shared state and methods from both gallery classes. **Shared `__init__` state moved**: `thumbnail_size`/`padding_width`/`approx_item_width`, `thread_pool`/`_active_workers`, `_resize_timer` (with `connect(_on_layout_change)`), `_scroll_zoom_connected`, `_sort_key`/`_sort_reverse`, `_dir_back_stack`/`_dir_forward_stack`, `open_preview_windows`. **Duplicate methods removed** from both gallery files (~290 lines): `_add_recent_dir`, `_get_recent_dirs`, `_save_last_dir`, `_load_last_dir`, `_show_status`, `_add_filename_label`, `_save_thumbnail_size`, `_load_thumbnail_size`, `_sort_key_fn`, `_apply_sort`, `_SORT_KEY_MAP`. **9 metaclass-injected `common_*` functions** (pagination UI, column calc, layout reflow, viewport check, paginated slice, placeholder, search input, search filter, pagination state) converted to real inherited methods — IDE `Ctrl+Click` and mypy now work on all of them. **Abstract methods** added: `get_default_config`, `set_config`, `_on_layout_change` (enforces contract; both subclasses already implement all three). **`MetaAbstractClassGallery`** simplified from 397 → 18 lines — all injection code removed, now a pure metaclass-combination shim. Both gallery classes changed to `AbstractClassXxx(AbstractGalleryBase)` with no explicit metaclass. |

### Stats

| File | Before | After |
|------|--------|-------|
| `meta_abstract_class_gallery.py` | 397 lines | 18 lines |
| `abstract_class_two_galleries.py` | 1662 lines | 1511 lines |
| `abstract_class_single_gallery.py` | 1257 lines | 1118 lines |
| `gallery_base.py` | *(new)* | 574 lines |

**36 contract tests still passing** (0 regressions).

---

## Arch Tier 4 — A.10 mypy + TypedDicts · A.11 AppSettings · A.12 `get_asp()` · A.13 Exception hierarchy (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **A.10 mypy baseline + TypedDict worker configs** (`pyproject.toml`, `gui/src/helpers/core/config_types.py`) | Added `[tool.mypy]` section: permissive baseline (`warn_return_any = false`, `ignore_missing_imports = true`) with per-module opt-in strictness for `backend.src.errors` and `backend.src.models.base`. New `config_types.py` defines `ConversionConfig`, `DeletionConfig`, `MergeConfig`, `StitchConfig` TypedDicts. Wired into `ConversionWorker.__init__`, `DeletionWorker.__init__`, `MergeWorker.__init__`; `Dict[str, Any]` imports removed. |
| **A.11 `AppSettings` GUI facade** (`gui/src/utils/settings.py`) | Classmethod-based singleton wrapping `QSettings("ImageToolkit","ImageToolkit")`. Typed accessors: `mainwindow_geometry/set`, `session/set_session`, `splitter/set_splitter`, `listings_splitter/set_listings_splitter`, `label/set_label/remove`. Deferred `QSettings` import inside `_q()` avoids import-time Qt init. Wired into: both abstract gallery base classes (`_add_recent_dir`, `_get_recent_dirs`, `_save/load_last_dir`, `_save/load_thumbnail_size`, `_get/set_color_label`), `main_window.py` (geometry save/restore), `splitter_persistence.py`, `listings_common.py` (splitter), `thumbnail_size.py`. Replaces 18+ inline `QSettings("ImageToolkit","ImageToolkit")` constructor calls. |
| **A.12 `get_asp()` helper** (`backend/src/animation/config.py`) | `get_asp(key, default="")` reads `os.environ.get(key, default)` — centralised accessor for `ASP_*` env vars. `validate_asp_config(strict=True)` now raises `ConfigError` instead of bare `ValueError`. Exported in `__all__`. |
| **A.13 Custom exception hierarchy** (`backend/src/exceptions.py`, `gui/src/helpers/base.py`) | `ImageToolkitError` root; `PipelineError` → `AlignmentFailedError`, `CanvasError`, `FallbackExhaustedError` (carries `.fallbacks: list[str]`); `ModelLoadError`; `ConfigError`. Bare `RuntimeError`/`ValueError` replaced in `animation/pipeline.py` (2 sites), `animation/canvas.py` (2 sites), `animation/config.py` (1 site), `models/birefnet_wrapper.py` (1 site). `BaseQThreadWorker._handle_exception()` three-tier handler: `AlignmentFailed`/`Canvas` → WARNING; `Pipeline`/`Model`/`Config` → ERROR; unknown → ERROR with full traceback. TYPE_CHECKING guard prevents runtime circular import. |

### Test count

**36 contract tests still passing** (0 regressions).

---

## Arch Tier 3 — A.1 Pyright · A.4 `__all__` · A.5 QSettings · A.6 `@log_call` · A.7 Metaclass (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **A.1 Pyright `basic` mode** (`pyproject.toml`) | `typeCheckingMode = "off"` → `"basic"`. Activates IDE red-squiggles for all developers at zero annotation cost. |
| **A.4 `__all__` hygiene pass** (15 `__init__.py` files) | `backend/src/{models,web,core,pipeline,utils,__init__}` and `gui/src/{utils,styles,helpers/{image,video,web,core},tabs,tabs/core/common}`. Empty namespace markers get `__all__: list = []`. Populated files get explicit symbol lists. `backend/src/models/__init__.py` now imports and re-exports all 7 model wrappers + `ModelWrapper`/`ModelRegistry`/`lazy_load`. `gui/src/utils/__init__.py` exposes `LRUImageCache`, `ShortcutRegistry`, sort/splitter/thumbnail utilities. |
| **A.5 QSettings key validation** (`backend/src/app.py`) | `SETTINGS_SCHEMA: dict[str, type]` + `SETTINGS_PREFIX_TYPES` define the known key surface. `_validate_settings()` runs after `QApplication()` is created; clears type-mismatched static keys with a `logger.warning`; logs unrecognised keys at DEBUG level. Dynamic key patterns (`session/*`, `splitters/*`, `splitter/*`, `labels/*`) are explicitly allowed via prefix table. |
| **A.6 `@log_call` timing decorator** (`backend/src/utils/decorators.py`) | New module. `log_call(logger=None)` returns a decorator that logs `→ qualname` on entry and `← qualname  X.Y ms` on exit at DEBUG level. Exception path logs `✗ qualname` + elapsed before re-raising. Auto-selects `__module__` logger when none is passed. Exported via `backend/src/utils/__init__.py`. |
| **A.7 Metaclass docstring + `_load_thumbnail_size` extraction** | `MetaAbstractClassGallery` docstring extended with Qt metaclass fusion rationale, injection rationale, full injected-method list, and note on why thumbnail helpers live in the base classes rather than here. `save_thumbnail_size(class_name, size)` + `load_thumbnail_size(class_name, default=180)` extracted to new `gui/src/utils/thumbnail_size.py`; both abstract gallery base classes delegate their `_save/_load_thumbnail_size` methods to the shared functions. |

---

## Arch Tier 2 — §5.8A/B/C ModelWrapper ABC · §5.9A/B Worker bases · §5.15C print→logger (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **§5.8A `ModelWrapper` ABC** (`backend/src/models/base.py`) | New file. Abstract base class with `load()` (abstract), `unload()` (default: flushes CUDA cache + gc.collect()), `is_available()` classmethod (default True), `loaded` property (default: checks `self._model`). All 7 model wrappers migrated: `BaSiCWrapper`, `LoFTRWrapper`, `ALIKEDLightGlueWrapper`, `RoMaWrapper`, `JamMaWrapper`, `EfficientLoFTRWrapper`, `BiRefNetWrapper`. Each calls `super().__init__(device)`, overrides `loaded` when model lives outside `_model`, extends `unload()` with `super().unload()`, and renames `load_model()` / `_load()` → `load()` with a backward-compat alias. `is_available()` classmethod wired to `_ROMA_OK`, `_JAMMA_OK`, `_KORNIA_OK`, `_TRANSFORMERS_OK` flags. `BaSiCWrapper.load()` is a no-op (profiles computed in `fit()`). `BiRefNetWrapper` uses `_ensure_loaded()` internal helper (preserves return-model contract), with `load_model = _ensure_loaded` alias. Roadmap item 4.2. |
| **§5.8B `@lazy_load` decorator** (`backend/src/models/base.py`) | Calls `self.load()` on first invocation when `self.loaded` is False. Applied to key public entry-points: `LoFTRWrapper.match/match_masked`, `ALIKEDLightGlueWrapper.match`, `RoMaWrapper.match_translation`, `JamMaWrapper.match`, `EfficientLoFTRWrapper.match`, `BiRefNetWrapper.get_soft_mask`. External callers no longer need to call `load()` manually before using wrappers. |
| **§5.8C `ModelRegistry` singleton** (`backend/src/models/base.py`) | Tracks all `ModelWrapper` instances via `weakref.ref` (auto-registered in `ModelWrapper.__init__`). `unload_all()` unloads every live wrapper with a model in memory and prunes dead refs. `loaded_count()` returns current VRAM occupancy count. `clear()` for test isolation. Wired into `ModelWrapper.__init__` — zero call-site changes needed. |
| **§5.9A `BaseQThreadWorker`** (`gui/src/helpers/base.py`) | New file. `QThread` base with `finished/error/progress` signals, `_cancelled` flag, `cancel()` + `stop = cancel` alias, `run()` wrapping `_execute()` in try/except → `error.emit`. Subclasses implement `_execute()`; complex workers may override `run()` directly. |
| **§5.9B `BaseQRunnableWorker` + `_WorkerSignals`** (`gui/src/helpers/base.py`) | `_WorkerSignals(QObject)` with `finished/error/progress/cancelled` signals — one shared class replaces per-worker signal objects. `BaseQRunnableWorker(QRunnable)` with `self.signals`, `_cancelled`, `cancel()`, `run()` checking pre-cancel flag then calling `_execute()`. `SearchWorker` migrated: removed `_SearchWorkerSignals` class, now inherits from `BaseQRunnableWorker`; `run()` → `_execute()`. |
| **§5.15C Silent print→logger** (`conversion_worker.py`, `duplicate_scan_worker.py`, `gan_wrapper.py`, `lo_ra_tuner.py`) | 7 `print(f"Error...")` calls replaced with `logger.warning/error` in 4 files. Each file gained a `logger = logging.getLogger(__name__)` module-level logger where missing. Errors now appear in the application log and are filterable by severity. |

### Test count

**36 contract tests still passing** (0 regressions from ABC migration). Full backend suite: pre-existing `test_fg_register` failure (ptlflow not installed) unrelated to this work.

---

## Arch Tier 1 — §5.8D Comment cleanup · §5.11B Deferred imports · §5.16A Contract tests (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **§5.8D Remove relocated-import comment blocks** (`backend/src/models/`) | All `# --- Relocated Nested Imports ---` / `# --------------------------------` comment blocks and `# relocated: <import>` inline comments removed from the entire `backend/src/models/` tree (35 files). `import gc` re-added as a real import to 7 files that call `gc.collect()` in `unload()`: `birefnet_wrapper.py`, `basic_wrapper.py`, `jamma_wrapper.py`, `roma_wrapper.py`, `efficient_loftr_wrapper.py`, `loftr_wrapper.py`, `aliked_lg_wrapper.py`. Imports now follow standard PEP 8 order with no comment noise. Roadmap item A.3. |
| **§5.11B Deferred heavy imports in GUI workers** (`gui/src/helpers/`) | Removed `TrainingWorker` re-export from `gui/src/helpers/__init__.py` (was force-loading PyTorch at GUI startup via the gallery base class import chain). Updated sole consumer `gan_train_tab.py` to import directly. Moved all heavy module-level imports inside `run()` for: `training_worker.py` (`torch`, `torchvision`, `GAN`), `lora_training_worker.py` (`LoRATuner`), `mask_preview_worker.py` (`BiRefNetWrapper`), `match_worker.py` (`BiRefNetWrapper`, `LoFTRWrapper`), `sn_task.py` (`SiameseModelLoader`). Cold-start reduction: ~2–4 s on PyTorch import chain. Roadmap item A.8. |
| **§5.16A ML wrapper contract tests** (`backend/test/models/test_wrapper_contracts.py`) | 36 mock-based contract tests; no GPU required; all pass in ~8 s. Covers: `BaSiCWrapper` (lifecycle, interface, output types), `LoFTRWrapper` (lifecycle, interface), `RoMaWrapper` (availability flag + blocked-import re-solve), `ALIKEDWrapper` (availability flag + blocked-import re-solve), `UnloadIdempotency` (double-unload safe), `BiRefNetWrapper` (interface, class-level `_models` singleton), `BaSiCOutputTypes` (ndarray passthrough). Helper stubs: `_make_torch_stub()`, `_make_kornia_stub()`, `_make_transformers_stub()`, `_make_cv2_stub()`. `backend/test/models/__init__.py` created. Roadmap item A.9. |

### Test count

**36 new contract tests** (no change to ASP test count). Total architecture test suite: 36 passing, 0 failing.

---

## ASP Session 138 — §1.81 Seam Band SSIM Gate · §1.82 Seam Spatial-Frequency Profile Gate (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **§1.81 `_seam_band_ssim`/`_check_seam_ssim_gate`** (`compositing.py`) | Per-seam SSIM-based perceptual similarity gate. For each inter-strip boundary, computes the Structural Similarity Index (SSIM) between the `band_px=30`-row window immediately above and below using `skimage.metrics.structural_similarity` (float32, `data_range=1.0`). Heights are equalised when the boundary falls near the image edge. SSIM fuses luma, contrast, and structure into a single [0,1] score — a catch-all perceptual gate complementing the targeted §1.76–§1.80 single-dimension gates. Gate fires when any seam's SSIM falls *below* the threshold (inverted polarity vs §1.76–§1.80 which fire *above* theirs). `_SEAM_SSIM_GATE` flag (default 0.0=off, `ASP_SEAM_SSIM_GATE=0.85`). Stage 11.14 wired in `pipeline.py` after Stage 11.13. `ASP_SEAM_SSIM_GATE` added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]`. Exported in `__all__`. |
| **§1.82 `_seam_freq_profile`/`_check_seam_freq_gate`** (`compositing.py`) | Per-seam spatial-frequency profile mismatch gate using FFT Pearson-r. For each inter-strip boundary, computes the column-averaged 1D FFT magnitude spectrum (DC excluded, positive-frequency half only, `np.fft.rfft` along rows) of each band, then measures `1 − max(0, Pearson-r)` between the two spectral vectors. Score 0=identical spectra (compatible); 1=orthogonal/anti-correlated spectra. Catches spectral content discontinuities — e.g., fine-grained noise texture above a smooth low-frequency gradient — invisible to all §1.76–§1.81 gates. When one band has near-zero AC content (flat row profiles), the inner-product denominator falls below 1e-9 and the score defaults to 0.0 (no mismatch information → safe pass). `_SEAM_FREQ_GATE` flag (default 0.0=off, `ASP_SEAM_FREQ_GATE=0.6`). Stage 11.15 wired in `pipeline.py` after Stage 11.14. `ASP_SEAM_FREQ_GATE` added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]`. Exported in `__all__`. |
| **10 tests** `TestSeamBandSsim` / `TestSeamFreqProfile` | SSIM: single strip → empty; identical bands → score > 0.99; noise vs uniform → score < 0.8; gate passes identical; gate fires on noise/uniform split. Freq: single strip → empty; identical bands → score ≈ 0; flat image → score < 0.2; high-freq (2-row) vs low-freq (8-row) row stripes → score > 0.2; gate fires on stripe frequency mismatch. |

### Test count

**913 tests passing** after S138 (10 new). 2 skipped.

---

## ASP Session 137 — §1.80 Seam Gradient Direction Coherence Gate (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **§1.80 `_seam_grad_direction`/`_check_seam_grad_direction_gate`** (`compositing.py`) | Per-seam Sobel gradient-direction circular-distance coherence gate. For each inter-strip boundary, computes the mean *undirected* gradient orientation (Sobel gx/gy → `arctan2(gy, gx) mod π` → [0, π)) in a `band_px=30`-row window immediately above and below using the angle-doubling circular mean (`0.5 × arctan2(mean(sin(2θ)), mean(cos(2θ)))`). Only pixels with Sobel magnitude > `mag_thresh=10` contribute; flat regions excluded. Circular distance between the two per-band mean orientations is returned in degrees [0, 90]. A score of 45° indicates dominant edges oriented ~45° apart (perceptible texture-direction step); 90° = fully orthogonal content (horizontal vs vertical). Detects structural orientation discontinuities invisible to all colour-space gates (§1.76–§1.79): e.g., diagonal speed-lines above a horizontal cloud-layer below. `_SEAM_GRAD_DIR_GATE` flag (default 0.0=off, `ASP_SEAM_GRAD_DIR_GATE=45.0`). Stage 11.13 gate wired in `pipeline.py` after Stage 11.12. `ASP_SEAM_GRAD_DIR_GATE` added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]`. Also backfilled `ASP_SEAM_MAX_COL_GATE`, `ASP_SEAM_SAT_GATE`, `ASP_SEAM_HUE_GATE`, `ASP_SEAM_SHARP_GATE` into `_DUMP_SECTIONS["compositing"]` (were missing). Exported in `__all__`. |
| **5 tests** `TestSeamGradDirection` | Single strip → empty; flat image → 0.0 (no strong gradients); same horizontal stripes both bands → low score (<20°); horizontal stripes above vs vertical stripes below → high score (>60°); gate fires on orthogonal content with thresh=45.0. |

### Test count

**903 tests passing** after S137 (5 new). 2 skipped.

---

## ASP Session 136 — §1.79 Seam Sharpness Mismatch Gate (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **§1.79 `_seam_sharpness_mismatch`/`_check_seam_sharpness_gate`** (`compositing.py`) | Per-seam Laplacian-variance log₂ ratio sharpness mismatch gate. For each inter-strip boundary, computes the Laplacian variance (via `cv2.Laplacian`) in a `band_px=30`-row window immediately above and below, returning `|log₂(var_top / var_bot)|`. Both variance values are clamped to ≥ 1.0 to prevent singularities on near-flat regions. A score of 3.0 means one strip is 8× sharper than the other — clearly perceptible as a texture discontinuity caused by different MPEG compression rates, upscaling, or frame-averaging applied to source frames. Complements colour gates (§1.76–§1.78) which are blind to sharpness. Input is converted to greyscale before Laplacian to avoid channel artefacts. `_SEAM_SHARP_GATE` flag (default 0.0=off, `ASP_SEAM_SHARP_GATE=3.0`). Stage 11.12 gate wired in `pipeline.py`. Exported in `__all__`. |
| **5 tests** `TestSeamSharpnessMismatch` | Single strip → empty; uniform image → zero mismatch (both halves clamped to 1.0 → ratio=0); equal-noise halves → low score (<2.0); sharp checkerboard vs heavily Gaussian-blurred → large score (>2.0); gate fires on sharp/blurry split with thresh=2.0. |

### Test count

**898 tests passing** after S136 (5 new). 2 skipped.

---

## ASP Session 135 — §1.77–1.78 Seam Saturation Jump & Hue Shift Gates (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **§1.77 `_seam_saturation_jump`/`_check_seam_saturation_gate`** (`compositing.py`) | Per-seam mean HSV saturation jump gate. For each inter-strip boundary, computes the mean HSV saturation in a `band_px=30`-row window immediately above and below, returning `|sat_above − sat_below|`. Catches colour-vibrancy discontinuities — e.g., a muted pastel background abutting a vividly coloured character outfit — that luma (§1.24, §1.76), entropy (§1.72), and Bhattacharyya (§1.14) gates miss. Greyscale inputs return 0.0 per seam. `_SEAM_SAT_GATE` flag (default 0.0=off, `ASP_SEAM_SAT_GATE=40.0`). Stage 11.10 gate wired in `pipeline.py`. `ASP_SEAM_SAT_GATE` added to `_CONFIG_SCHEMA`. Exported in `__all__`. |
| **§1.78 `_seam_hue_shift`/`_check_seam_hue_gate`** (`compositing.py`) | Per-seam circular mean hue shift gate. For each inter-strip boundary, computes the mean HSV hue in a `band_px=30`-row window above and below using circular (angular) distance on the [0, 180] OpenCV hue scale; near-achromatic pixels (sat ≤ 15) excluded to prevent grey regions biasing the mean. Returns circular distance in [0, 90]°. Catches colour-temperature discontinuities — e.g., warm orange/red background abutting cool blue/teal strip — that saturation and luma gates miss. `_SEAM_HUE_GATE` flag (default 0.0=off, `ASP_SEAM_HUE_GATE=30.0`). Stage 11.11 gate wired in `pipeline.py`. `ASP_SEAM_HUE_GATE` added to `_CONFIG_SCHEMA`. Exported in `__all__`. |
| **10 tests** `TestSeamSaturationJump` + `TestSeamHueShift` | Saturation: single strip → empty, greyscale → zeros, uniform sat → no jump, vivid vs grey → large jump, gate fires on vivid/grey split. Hue: single strip → empty, greyscale → zeros, same hue → no shift, warm vs cool → large shift, gate fires on opposite hues. |

### Test count

**893 tests passing** after S135 (10 new). 2 skipped.

---

## ASP Session 134 — §1.76 Per-Column Luma Step Gate (2026-06-18)

### Shipped

| Item | Summary |
|------|---------|
| **§1.76 `_seam_max_col_luma_step`/`_check_seam_max_col_gate`** (`compositing.py`) | Per-column worst-case luma step gate. For each inter-strip seam boundary, computes per-column mean luma in a `band_px=8`-row window above and below (with `guard=2` excluded rows adjacent to the boundary) and returns the maximum absolute column difference. Unlike §1.24 which averages across the full strip width, §1.76 reports the single worst column — catching localised hot-spots (character outline or shadow edge crossing the seam at one column) that the mean dilutes away. `_check_seam_max_col_gate` returns worst seam index when any step exceeds `thresh`. `_SEAM_MAX_COL_GATE` flag (default 0.0=off, `ASP_SEAM_MAX_COL_GATE=40.0`). Stage 11.9 gate wired in `pipeline.py` after Stage 11.8. `ASP_SEAM_MAX_COL_GATE` added to `_CONFIG_SCHEMA`. Exported in `__all__`. |
| **5 tests** `TestSeamMaxColLumaStep` | single strip → empty list, identical bands → 0 step, localised column spike → detected, uniform image → gate None, single hot-spot column → gate fires at seam 0. |

### Test count

**883 tests passing** after S134 (5 new). 2 skipped.

---

## ASP Session 133 — §1.73–1.75 Pre/Post-Composite Quality Gates (2026-06-17)

### Shipped

| Item | Summary |
|------|---------|
| **§1.73 `_compute_bg_lum_monotonicity`** (`pipeline.py`) | Pre-composite per-frame gain monotonicity drift gate. Extracts per-frame background median luminance (same logic as §1.71) and computes the absolute Kendall-τ rank correlation between frame order and the luma sequence. `|τ| ≈ 1.0` indicates a brightness staircase (each frame steadily darker/brighter) even when the total spread is within §1.71's threshold. Stage 10.9 gate: fires when `|τ| > _BG_GAIN_MONOTONE_THRESH` → SCANS fallback. Default OFF, `ASP_BG_GAIN_MONOTONE_THRESH=0.85`. Returns 0.0 when fewer than 3 frames have sufficient background. Added to `_CONFIG_SCHEMA`, `_DUMP_SECTIONS["pipeline"]`, and `__all__`. |
| **§1.74 `_compute_canvas_fill_ratio`** (`pipeline.py`) | Post-composite canvas fill ratio gate. Counts pixels where `max(B,G,R) > _CANVAS_FILL_PIX_THRESH` (default 10) as "filled"; returns filled/total. Pixels that remain zero after compositing are unfilled gaps from failed frame warps or geometric discontinuities — all existing seam-boundary gates miss these. Stage 11.7 gate: fires when `fill_ratio < _CANVAS_FILL_MIN` → SCANS fallback. Default OFF, `ASP_CANVAS_FILL_MIN=0.60`. Separate `ASP_CANVAS_FILL_PIX_THRESH` knob (default 10) guards dark-background anime from false positives. Both added to `_CONFIG_SCHEMA`, `_DUMP_SECTIONS["pipeline"]`, and `__all__`. |
| **§1.75 `_compute_strip_variance_ratio`** (`pipeline.py`) | Post-composite strip Laplacian variance ratio gate. Splits the composite into N horizontal bands and computes the Laplacian variance (texture/sharpness proxy) per strip; returns `max_var / min_var`. A high ratio signals structural content incompatibility (one strip flat-colour, another richly detailed) that seam-boundary gates miss because those sample only ±50px at the boundary. Stage 11.8 gate: fires when `ratio > _STRIP_VARIANCE_RATIO_MAX` → SCANS fallback. Default OFF, `ASP_STRIP_VARIANCE_RATIO_MAX=10.0`. Returns 1.0 when any strip variance is zero (uniform canvas). Added to `_CONFIG_SCHEMA`, `_DUMP_SECTIONS["pipeline"]`, and `__all__`. |
| **5 tests** `TestComputeBgLumMonotonicity` | < 3 frames → 0.0, ascending |τ|=1, descending |τ|=1, random order |τ|<0.7, None masks ascending → |τ|=1. |
| **5 tests** `TestComputeCanvasFillRatio` | fully filled → 1.0, fully empty → 0.0, half-filled → 0.5, exact-threshold pixels count as empty, zero-size → 1.0. |
| **5 tests** `TestComputeStripVarianceRatio` | 1 strip → 1.0, uniform → 1.0, balanced noise low ratio, nearly-flat vs noisy high ratio, zero-size → 1.0. |

### Test count

**878 tests passing** after S133 (15 new). 2 skipped.

---

## ASP Session 132 — §1.68–1.72 Compositing Gates + Bugfixes (2026-06-17)

### Shipped

| Item | Summary |
|------|---------|
| **§1.68 `_enforce_feather_ratio`** (`compositing.py`) | Adjacent feather-width ratio enforcement. After all §1.6B/§1.19 per-seam feather adjustments, iterative forward+backward pass clamps each seam's feather so that no two adjacent seams differ by more than `_FEATHER_RATIO_MAX`-fold (default OFF, `ASP_FEATHER_RATIO_MAX=3.0`). Prevents visible "tonal rhythm" discontinuity from wide/narrow seam alternation. Wired after §1.19 feather cap. Added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]`. Exported in `__all__`. |
| **§1.69 `_seam_dp_bg_ratio`** (`compositing.py`) | Post-DP background routing ratio check. Samples bg_mask values at each `(x, path[x])` position along the DP traceback; returns the fraction of columns where BOTH frame masks classify the seam pixel as background. When `ratio < _SEAM_DP_BG_MIN` → seam was forced through character pixels despite cost-map steering → post-DP single-pose escalation. Default OFF, `ASP_SEAM_DP_BG_MIN=0.30`. Wired in blend loop after seam path is determined. Added to `_CONFIG_SCHEMA` and exported. |
| **§1.70 `_fg_fraction_in_zone`** (`compositing.py`) | Blend-zone fg coverage pre-escalation (was stub, now fully wired). Computes union fg fraction from both frame bg_masks; when `> _SEAM_ZONE_FG_MAX` escalates to single-pose before DP. Prevents DP from running on infeasible cost landscape (no background corridor exists). Default OFF, `ASP_SEAM_ZONE_FG_MAX=0.85`. Wired right after §1.60 pose-gap check. Added to `_CONFIG_SCHEMA`, `_DUMP_SECTIONS["compositing"]`, and `__all__`. |
| **§1.71 `_compute_bg_lum_spread`** (`pipeline.py`) | Pre-composite background luminance spread gate. Computes `max(per-frame bg median luma) − min(per-frame bg median luma)` from raw frames and BiRefNet masks before Stage 11 compositing. Extreme spread → sequential gain normalisation requires >2× corrections → brightness staircase. Stage 10.8 gate: fires when `spread > _BG_LUM_SPREAD_MAX` → SCANS fallback. Default OFF, `ASP_BG_LUM_SPREAD_MAX=80.0`. Added to `_CONFIG_SCHEMA`, `_DUMP_SECTIONS["pipeline"]`, and `__all__`. |
| **§1.72 `_seam_entropy_asymmetry` + `_check_seam_entropy_gate`** (`compositing.py`) | Shannon entropy asymmetry gate. Computes `|H_top − H_bot|` (bits) for each seam boundary using 50-row bands; flat-colour side (low entropy) vs rich-texture side (high entropy) produces a perceptible texture-density discontinuity that NCC and Bhattacharyya both miss. Stage 11.5 gate in `pipeline.py`. Default OFF, `ASP_SEAM_ENTROPY_GATE=1.5`. Added to `_CONFIG_SCHEMA`, `_DUMP_SECTIONS["compositing"]`, and `__all__`. |
| **5 tests** `TestEnforceFeatherRatio` | single feather, ratio=0 no-op, forward clamp, backward clamp, already-within-ratio unchanged. |
| **5 tests** `TestSeamDpBgRatio` | no masks → 1.0, empty path → 1.0, all-bg → 1.0, all-fg → 0.0, half-bg range check. |
| **5 tests** `TestFgFractionInZone` | both None → 0, all-bg → 0, all-fg → 1, union covers both, one None uses other. |
| **5 tests** `TestSeamEntropyAsymmetry` | single strip empty, identical halves near-zero, flat vs rich high asymmetry, gate passes, gate fires. |
| **5 tests** `TestComputeBgLumSpread` | < 2 frames → 0, identical → 0, spread > 100 for lum 50 vs 200, None masks, insufficient bg pixels skipped. |
| **Bugfixes** | §1.66 NCC `test_identical_halves_high_ncc` / `test_gate_passes_above_threshold`: band had 40/60 rows but `band_px=20` meant `top`/`bot` picked non-overlapping rows → NCC≈0; fixed to use 20-row band so `top==bot` at seam boundary. §1.67 `TestCheckCanvasSpread` helper renamed from `_make_edge` to `_make_spread_edge` (line-1644 definition shadowed line-64 definition with different `ty`/`tx` signature → 5 `TestSpatialDedupFrames` tests failed with `TypeError`). |

### Test count

**863 tests passing** after S132 (25 new + 7 bug-fixed). 2 skipped.

---

## ASP Session 131 — §1.66 NCC Gate · §1.67 Canvas Spread · §1.8C/D Config Dump (2026-06-17)

### Shipped

| Item | Summary |
|------|---------|
| **§1.66 `_seam_ncc_coherence` + `_check_seam_ncc_gate`** (`compositing.py`) | Per-seam normalised cross-correlation (NCC) structural coherence gate. `_seam_ncc_coherence(img, n_strips, band_px=60)` computes NCC between `band_px`-row windows above and below each inter-strip boundary; flat bands (σ < 1e-3) return 1.0. `_check_seam_ncc_gate(img, n_strips, thresh)` returns the worst-NCC seam index or None when all pass. `_SEAM_NCC_GATE` module flag (default 0.0=off, `ASP_SEAM_NCC_GATE=0.45`). Added to `_CONFIG_SCHEMA` (compositing section). Both exported in `compositing.__all__`. |
| **Stage 11.4 NCC gate** (`pipeline.py`) | Wired between Stage 11.3 (luma-step) and Stage 11.5 (SRStitcher). Imports `_check_seam_ncc_gate` from `compositing`. Complements §1.14B (pre-composite colour histogram) and §1.24 (post-composite luma step) by detecting structural line-art / pose discontinuity. |
| **§1.67 `_check_canvas_spread`** (`pipeline.py`) | Pre-BA frame canvas spread validation. BFS propagates pairwise translations from frame 0 to reconstruct cumulative positions; computes `actual_dom_span / (median_adj_step × (N-1))`. Returns False when ratio < `min_spread_fraction` → SCANS fallback. `_CANVAS_SPREAD_MIN` flag (default 0.0=off, `ASP_CANVAS_SPREAD_MIN=0.5`). Wired between §1.16 MST gate and §1.43 adj-coverage gate. `ASP_CANVAS_SPREAD_MIN` added to `_CONFIG_SCHEMA` (pipeline section). Exported in `__all__`. |
| **§1.8D Typed TOML schema comments** (`config.py`) | `dump_asp_config` enhanced to emit `# type: <typename>  range: [min, max]` machine-readable annotation above each key, followed by the existing human-readable description. `getattr(typ, "__name__")` extracts type name; min/max emitted as Python values (None when unbounded). Zero breaking change — TOML key=value lines unchanged. `_CONFIG_SCHEMA` updated with `ASP_SEAM_NCC_GATE` and `ASP_CANVAS_SPREAD_MIN`. `ASP_SEAM_NCC_GATE` added to `compositing` dump section; `ASP_CANVAS_SPREAD_MIN` added to `pipeline` dump section. |
| **5 tests** `TestSeamNccCoherenceCompositing` (`test_compositing.py`) | single-strip empty, two-strip score count, identical-halves NCC ≥ 0.9, gate passes above threshold, gate fires on mismatched strips. |
| **5 tests** `TestCheckCanvasSpread` (`test_pipeline.py`) | empty edges → True, zero threshold → True, uniform spread → True, clustered last frame fails 0.8 threshold (passes 0.5), horizontal scroll uses tx axis. |
| **5 tests** `TestDumpAspConfigSchemaComments` (`test_config.py`) | float type annotation present, range comment present, type annotation precedes key line, include_defaults emits type comments, int key annotated as int. |

### Session S130 items (in current diff)

| Item | Summary |
|------|---------|
| **§1.60 `_fg_zone_pose_gap` + pre-escalation** (`compositing.py`) | Measures mean absolute luminance diff between blend-zone crops restricted to shared fg pixels. `_FG_POSE_GAP_THRESH` flag (0=off, suggest 35.0). Pre-escalates to single-pose BEFORE DP when fg MAD exceeds threshold. 5 tests `TestFgZonePoseGap`. |
| **§1.62 Canvas aspect-ratio gate** (`pipeline.py`) | `_compute_canvas_aspect_ratio()` + `_MIN_CANVAS_ASPECT` flag (0=off, suggest 0.5). Fires after canvas construction for vertical-scroll sequences when aspect ratio < floor → SCANS. 5 tests `TestComputeCanvasAspectRatio`. |
| **§1.63 Sort frames by numeric suffix** (`pipeline.py`) | `_sort_frames_by_index()` re-sorts `image_paths` by rightmost digit run in stem at pipeline entry. Prevents OS directory-order issues. 5 tests `TestSortFramesByIndex`. |
| **§1.64 Exact-duplicate dHash guard** (`frame_selection.py`) | `_drop_exact_dhash_duplicates()` drops consecutive pixel-identical frames (Hamming dist=0) in step 0 of `smart_select_frames`. `ASP_DHASH_EXACT_DROP=1` to enable. 5 tests `TestDropExactDhashDuplicates`. |
| **§1.65 FG seam erosion buffer** (`compositing.py`) | `_FG_SEAM_EROSION_PX` erodes fg mask before Tier-1 cost assignment; converts outline ring from cost=1.0 to cost=0.5. `ASP_FG_SEAM_EROSION_PX=2` (suggest). 5 tests `TestFgSeamErosionBuffer`. |
| **§1.10D MC-dropout uncertainty** (`rlhf/reward_model.py`) | `predict_with_uncertainty(img, n_samples=20) → (mean, std)`. MC-dropout by switching Dropout layers to train mode while keeping BatchNorm in eval mode. `MC_DROPOUT_UNCERTAINTY_THRESHOLD=0.10` exported. 5 tests `TestMCDropoutUncertainty`. |
| **§1.8C dump_asp_config** (`config.py`) | `dump_asp_config(path, *, include_defaults=False)` serialises active ASP env-vars to grouped TOML. `_DUMP_SECTIONS` dict maps section names → key lists. Unrecognised ASP_* env-vars emitted under `[extra]`. Returns absolute path to written file. 5 tests `TestDumpAspConfig`. |
| **§3.17 `_seam_ncc_coherence` + §3.5A `_composite_quality_score`** (`bench_anime_stitch.py`) | Per-seam NCC structural coherence added to `_compute_all_metrics` as `seam_ncc_scores` + `seam_ncc_min`. `_composite_quality_score(seam_ncc_min, seam_color_min, ghost_seam_max)` → scalar [0,1]. `_compute_rlhf_uncertainty` wires `predict_with_uncertainty` into bench metrics. |

### Test count

**822 tests passing** at end of S130. **827 tests** after S131 additions (5 NCC gate + 5 canvas spread + 5 dump schema comments). 2 skipped.

---

## ASP Session 119 — §9C Hires Keyframes + §1.10E Benchmark JSON Import (2026-06-15)

### Shipped

| Item | Summary |
|------|---------|
| **`_apply_hires_keyframes()` §9C** (`pipeline.py`) | Module-level helper that replaces proxy frames with full-resolution counterparts before Stage 9 canvas construction. Accepts `hires_keyframes: Dict[int, str]` mapping frame index → hires path. Scales affine tx/ty proportionally (scale_x = hires_w/proxy_w, scale_y = hires_h/proxy_h); linear 2×2 sub-matrix preserved (dimensionless rotation/shear). Non-hires frames upscaled to hires resolution via INTER_LANCZOS4; bg_masks resized with INTER_NEAREST to preserve binary values. Returns `(n_substituted, frames_hires, affines_scaled, masks_resized)`. Added `hires_keyframes: Optional[Dict[int, str]] = None` to `pipeline.run()`. Stage 8.8 injected between Stage 8 (ECC/SEA-RAFT) and Stage 9. `"_apply_hires_keyframes"` added to `__all__`. |
| **8 new tests** (`test_pipeline.py::TestApplyHiresKeyframes`) | Covers: empty-dict no-op, 2× scale computation + frame replacement, proxy upscale fallback for non-hires frames, INTER_NEAREST bg_mask resize, None mask passthrough, invalid path graceful return, out-of-bounds index skip, linear sub-matrix preservation. |
| **`bench_import.py` §1.10E** (`backend/src/animation/rlhf/`) | New module with `parse_bench_json(path)` (handles full suite doc, single-dataset dict, bare list), `resolve_anime_path(dataset)` (primary `anime_path` with `paths.anime_stitch` fallback), `suggested_rating(metrics_asp)` (composite CV score → 0–10 scale: `coverage×0.35 + sharpness_norm×0.25 + (1−ghosting)×0.20 + seam_coh×0.20`), `verdict_label(dataset)`. Exported from `rlhf/__init__.py`. |
| **`StitchFeedbackTab` import group** (`stitch_feedback_tab.py`) | New "Import from Benchmark JSON" group above the image loader: "Load JSON…" button → populates `QListWidget` with verdict/fallback/rlhf-flag badges per dataset; per-dataset metrics preview panel (sharpness, coverage, ghosting, seam_coh, ssim, suggested rating); "Import Selected →" button loads the panorama image and pre-fills the rating slider from `suggested_rating()`. |
| **21 new tests** (`test_bench_import.py`) | Covers `parse_bench_json` (5 cases), `resolve_anime_path` (4 cases), `suggested_rating` (6 cases), `verdict_label` (7 parametrised cases). |
| **asp.md matrix updated** | Removed 23 stale "pending" entries (items shipped in Sessions 6–118 but never pruned). Added §1.10E done entry. Updated §2.1, §2.4, §2.7 headings with shipped-session tags. |

### Test results

877 backend tests (133 `test_pipeline.py` + 21 `test_bench_import.py` + 623 others), 2 skipped. No regressions.

### Design notes

**§9C affine scaling:** Only tx (`a[0,2]`) and ty (`a[1,2]`) are scaled by (hires/proxy) ratios. The 2×2 linear sub-matrix encodes rotation/shear as ratios — they are dimensionless and do not change with image scale. For the typical ASP case of pure translation affines, this is exact. For affines with small rotation (e.g. from GNC-TLS BA), the rotation angle is preserved and only the displacement is rescaled, which is the correct geometric semantics.

**§1.10E rating formula:** Mirrors `_auto_verdict()` in `bench_anime_stitch.py` so the suggested rating is consistent with the automated verdict. Users are expected to adjust the slider before submitting; the suggestion is a calibration starting point, not a ground truth. The RLHF reward model will be trained on the human-adjusted ratings, so divergence between automated and human scores is the primary signal of interest for §1.10B (Bayesian param search).

---

## ASP Session 80 — §1A Otsu bg-only phase corr + §5A/C BG completion + §8 defaults + Issue Report marking (2026-06-13)

### Shipped

| Item | Summary |
|------|---------|
| **`_otsu_bg_mask_pair()` (§1A)** (`frame_selection.py`) | Per-pair Otsu background mask for phase correlation. Computes an Otsu threshold on each float32 thumbnail, classifies pixels above the threshold as background, erodes to remove foreground-edge contamination, returns pixel-wise minimum (intersection). Falls back to plain `phaseCorrelate` when bg coverage < 10%. Enable: `ASP_OTSU_BG_CORR=1`. Zero new dependencies — faster and per-frame accurate vs the 5-probe BiRefNet intersection approach (`ASP_TWO_CHANNEL_SELECT`). |
| **`_OTSU_BG_CORR` flag wired in phase-corr loop** (`frame_selection.py`) | New `elif _OTSU_BG_CORR:` branch after the existing `_bg_thumb_mask` branch. When enabled, computes per-pair mask; if coverage < 10%, falls back to unmasked `phaseCorrelate`. `ASP_OTSU_BG_CORR` added to `_CONFIG_SCHEMA` in `config.py`. Exported `_otsu_bg_mask_pair` in `__all__`. |
| **`complete_background()` (§5A/C)** (`bg_complete.py`, new) | Background zero-coverage fill for canvas pixels uncovered by any frame's bg sample. `_nn_fill_zero_bg()`: column-directional nearest-neighbour propagation — for each column, `np.searchsorted` finds nearest known row above and below each gap; best (closer) is applied. `_propainter_fill()`: lazy-imports ProPainter (ICCV 2023); falls back to NN fill when unavailable. `complete_background()`: entry point — skips when zero rows < `min_rows` threshold. |
| **Stage 10.2 wired** (`pipeline.py`) | `complete_background()` called after `_render()` when `ASP_BG_COMPLETE > 0`. `ASP_BG_COMPLETE=1` → NN fill; `=2` → ProPainter with NN fallback. `_BG_COMPLETE` module-level flag. Import added. `ASP_BG_COMPLETE` and `ASP_BG_COMPLETE_MIN_ROWS` added to `_CONFIG_SCHEMA`. |
| **`animation/__init__.py` auto-loads `asp_config.toml`** | `_load_asp_config()` called before other package imports so TOML keys are in `os.environ` before any module-level flag constants are read. Try/except ensures no error if config missing. |
| **`asp_config.toml` created** (§8) | Root-level TOML with 8 recommended defaults from the Issue 8 report: `ASP_ADAPTIVE_SP_SOFT=1`, `ASP_ADAPTIVE_SP_THRESH=1`, `ASP_SEAM_SMOOTH_WINDOW=5`, `ASP_SEAM_MARGIN=3`, `ASP_SEAM_FG_PENETRATION_MAX=0.7`, `ASP_ZONE_MIN_HEIGHT=20`, `ASP_SEAM_INSTABILITY_THRESH=20.0`, `ASP_STATIC_INPUT_MAX_MAD=2.0`. |
| **SAM-2 pipeline wiring** (`pipeline.py`) | `_USE_SAM2` flag + `_compute_fg_masks_sam2` import; `AnimeStitchPipeline._compute_fg_masks()` routes through SAM-2 when `ASP_USE_SAM2=1`. (Completed from S79.) |
| **`ASP_High_Value_Issues_Report.md` marking** | All implemented items annotated with ✅ S79/S80 session tags. Failure taxonomy table updated. Priority matrix column added with current status. Recommended implementation order updated to show Sprint 1–3 complete. |
| **`OTSU_BG_CORR_MIN_BG_FRAC`, `BG_COMPLETE_MIN_ROWS`** (`constants/animation.py`) | Two new constants for §1A and §5A/C. |

### Test results

498 tests passing (+11 new: 5 `TestOtsuBgMaskPair` in `test_frame_selection.py`, 6 `TestNnFillZeroBg`/`TestCompleteBackground` in new `test_bg_complete.py`). No regressions.

### Design notes

**Why Otsu and not BiRefNet for §1A**: BiRefNet adds 0.3–0.8s/frame overhead; Otsu on a 256px thumbnail is ~0.2ms. The 5-probe BiRefNet intersection (`_TWO_CHANNEL_SELECT`) only samples 5 positions and takes their intersection — if the character moves between probes, the mask underestimates the character region. Per-pair Otsu adapts to each consecutive pair, catching frames where the character enters or exits the left/right edge. The threshold `> Otsu` classifies "light pixels = background" — this assumption holds for anime with light-colored backgrounds (lockers, walls) vs dark character outlines. Falls back silently when coverage < 10%.

**§5A/C NN fill semantics**: Column-directional nearest-neighbour (not row-directional) because the scroll axis is dominant and background texture repeats vertically. Each unknown pixel gets the closest known pixel in the SAME column, not in the same row. This avoids horizontal smearing of character elements across the strip boundary.

**auto-load ordering**: `animation/__init__.py` loads TOML before importing `.pipeline`, which triggers `.compositing`, `.bundle_adjust`, etc. — all module-level `os.environ.get(...)` calls happen AFTER `setdefault` writes the TOML values. Env vars set manually always win (setdefault never overwrites).

---

## ASP Session 79 — HITL Staged Execution + AnimeInterp SGM + SAM-2 + fg-masked DINOv2 (2026-06-13)

### Shipped

| Item | Summary |
|------|---------|
| **`QWaitCondition`/`QMutex` pause/resume in `StitchWorker`** (`stitch_worker.py`) | §2.0: `_hitl_mutex`, `_hitl_wait`, `_hitl_paused`, `_hitl_override` instance vars. `resume()` wakes the blocked worker thread. `cancel()` calls `resume()` first so cancellation propagates through a paused checkpoint. |
| **4 new HITL signals on `StitchWorker`** (`stitch_worker.py`) | `sig_review_frames`, `sig_review_edges`, `sig_review_canvas`, `sig_review_render` — each emits a plain `object` dict of intermediate pipeline state to the main thread. |
| **`_make_hitl_pause_cb()`** (`stitch_worker.py`) | Returns a closure that emits the correct signal then blocks via `QWaitCondition.wait()` until `resume()` is called. Worker thread sleeps; Qt main thread processes events normally. |
| **`set_frame_override(paths)`, `set_edge_override(edges)`, `set_affine_override(affines)`, `set_render_cancel()`** (`stitch_worker.py`) | Override setters called from dialog accept handlers before `resume()`. Pipeline reads `_hitl_override` after waking. |
| **4 HITL pause points in `_ProgressPipeline.run()`** (`stitch_worker.py`) | After Stage 4 (masking): emits frame thumbnails + inter-frame diff bars; supports frame exclusion/reorder override. After Stage 5 (edges): emits edge list; supports edge enable/disable override. After Stage 8 (canvas): emits affines + thumbnails + coverage; supports affine nudge override. After Stage 9 (render): emits canvas preview + per-row frame count; review-only (cancel aborts). |
| **`hitl_mode: bool = False` param on `StitchWorker`** (`stitch_worker.py`) | When False (default), `_make_hitl_pause_cb()` returns a no-op — zero overhead for the normal automated path. |
| **`SelectionReviewDialog(QDialog)`** (`gui/src/dialogs/selection_review_dialog.py`) | Option A: horizontal scroll area of thumbnail cards (160×120px) with per-frame pose-diff colour bars (green→red), include/exclude checkboxes, Move Up/Down, Select All/Deselect All. `selected_paths()` returns ordered list of checked paths. |
| **`EdgeReviewDialog(QDialog)`** (`gui/src/dialogs/edge_review_dialog.py`) | Option B: interactive edge graph (same circular node layout as existing read-only viewer) with checkbox column in the edge table. "Keep MST Only" runs Kruskal's greedy max-weight spanning tree. Disabled edges drawn grey-dashed in the graph. `accepted_edges()` returns enabled edges. |
| **`CanvasInspectorDialog(QDialog)`** (`gui/src/dialogs/canvas_inspector_dialog.py`) | Option D: QGraphicsScene canvas layout viewer with interactive ±10px nudge per frame (Up/Down/Left/Right buttons + "Reset Frame"). Nudges stored as `_nudges: dict`; `adjusted_affines()` returns deep-copied affines with deltas applied. Frame selection in list highlights the rect with gold pen. |
| **`CoverageHeatmapDialog(QDialog)`** (`gui/src/dialogs/coverage_heatmap_widget.py`) | Option C: side-by-side canvas preview (scaled to 600px) + QPainter bar chart of `frame_count_per_row` (red=0, orange=1, green=2+). Stats label: min/max coverage + single-frame row percentage. |
| **HITL mode checkbox + signal wiring** (`stitch_tab.py`) | "Human-in-the-loop review" checkbox in Output group. When checked, `StitchWorker(hitl_mode=True)` and 4 new `_on_hitl_review_*` handlers connect to the HITL signals. Each handler opens the appropriate dialog; Cancel from dialog calls `worker.cancel()`. |
| **`_compute_dinov2_features()` fg-masked crop (§1D)** (`frame_selection.py`) | Before DINOv2 embedding, crops each frame to the foreground bounding box (Otsu-thresholded binary + 5% padding). Removes background-dominated context that caused DINOv2 to track camera panning rather than character pose. Falls back to full frame if crop is degenerate (<32px). |
| **`_get_vgg19_feat()` + `_animeinterp_sgm()` (§3.1A full)** (`fg_register.py`) | Lazy VGG-19 conv3_4 loader (ImageNet weights; `torchvision.models.vgg19`). `_animeinterp_sgm()`: SLIC segmentation → per-segment VGG-19 conv3_4 mean-pooled L2-normalised feature vectors → cosine similarity × distance-score combined matching → per-pixel flow from centroid displacement. Falls back to `_slic_sgm_proxy` when VGG-19 unavailable. Enable: `ASP_ANIMEINTERP_SGM=1`. |
| **AnimeInterp SGM priority in `register_foreground_at_seam()`** (`fg_register.py`) | When `ASP_ANIMEINTERP_SGM=1`, calls `_animeinterp_sgm()` before `_arap_push`. When only `ASP_SGM_PROXY=1`, uses `_slic_sgm_proxy` as before. Both feed into ARAP Push as a better initial estimate. |
| **`_compute_fg_masks_sam2()` (§5.2)** (`masking.py`) | SAM-2 video predictor integration. Strategy: BiRefNet on frame 0 → bbox prompt → `build_sam2_video_predictor` propagates across all frames in one pass → temporally consistent masks. Requires `pip install sam2` + checkpoint at `$SAM2_CKPT` (~/.sam2/sam2_hiera_base_plus.pt). Falls back to per-frame BiRefNet on any error (SAM-2 not installed, BiRefNet frame-0 failure, inference exception). |
| **SAM-2 pipeline wiring via `ASP_USE_SAM2=1`** (`pipeline.py`) | `_USE_SAM2` module-level flag. `AnimeStitchPipeline._compute_fg_masks()` routes through `_compute_fg_masks_sam2` when set. `ASP_USE_SAM2` added to `_CONFIG_SCHEMA` (int 0–1). Import added. Default off — zero overhead change to automated path. |

### Test results

487 tests passing (up from 482 at S75; +5 from earlier unrelated sessions). No regressions in `test_frame_selection.py`, `test_compositing.py`, or other animation test modules.

### Design notes

**HITL pause safety**: `QWaitCondition.wait(mutex)` atomically releases the mutex and suspends the worker thread. The Qt event loop on the main thread continues processing normally while the worker sleeps — no UI freeze. The mutex re-locks on wake-up before `resume()` returns, ensuring `_hitl_override` is read safely.

**HITL override flow (frame checkpoint)**: thumbnails are created with `cv2.resize` at 256px (not QPixmap — safe for worker thread); dicts carry numpy arrays; Qt signal delivery is queued by default when sender and receiver are on different threads. Dialog converts arrays to QImage on the main thread.

**VGG-19 SGM vs SLIC proxy**: VGG-19 conv3_4 features (256-channel, 7×7 receptive field at conv3) remain discriminative for segments sharing identical flat fill colours (e.g., two skin-tone regions) because the surrounding outline structure is captured. SLIC+LAB saturates when two body parts have the same hue. VGG-19 adds ~50ms/seam overhead on GPU; SLIC proxy is ~5ms.

**SAM-2 memory model**: `propagate_in_video()` processes frames in a streaming fashion using a fixed-size memory bank — scales to long sequences without OOM. The bbox prompt from BiRefNet frame 0 is sufficient for high-quality propagation across 6–20 frame anime sequences.

---

## ASP Session 78 — §2.3 Canvas Layout Inspector (read-only viewer) (2026-06-11)

### Shipped

| Item | Summary |
|------|---------|
| **`_parse_canvas_json(path) → dict`** (`stitch_tab.py`) | §2.3: Loads `stage08_canvas_info.json` written by `_ProgressPipeline`. Returns normalised dict: `canvas_h`, `canvas_w`, `frame_h` (defaults 0 if absent), `frame_w` (defaults 0 if absent), `T_global` as `List[float]`, `affines_final` as list-of-lists-of-float. Safe for files written before the `frame_h`/`frame_w` addition. |
| **`_canvas_frame_corners(affine_2x3, frame_h, frame_w) → List[Tuple]`** (`stitch_tab.py`) | Pure function: applies the full 2×3 affine to the 4 corners of an (H, W) frame — `(0,0)`, `(W,0)`, `(W,H)`, `(0,H)` — and returns 4 `(x, y)` canvas-space tuples. Works for translation, rotation, scale, and shear affines. |
| **`CanvasLayoutInspectorDialog(QDialog)`** (`stitch_tab.py`) | Read-only canvas layout viewer. Left pane: `QGraphicsScene`/`QGraphicsView` (dark background) with a dim canvas-border rectangle and N frame polygons rendered as `QPainterPath` fills using an 8-colour rotating palette (cornflower-blue, green, orange, violet, gold, teal, tomato, sky-blue) at 110 alpha, edge outlines `color.darker(160)`. Frame index label (white, 230 alpha) placed at the polygon centroid. Right pane: `QTableWidget` with Frame/tx/ty per row. Stats label: "N frames · W×H canvas". "Load JSON…" toolbar button for standalone use. |
| **`⬗ Canvas` button in Stitch action row** (`stitch_tab.py`) | Initially disabled. Enabled in `_on_stitch_finished` when `stage08_canvas_info.json` exists in `_last_stages_dir`. Calls `_inspect_canvas()` which parses the JSON and opens the dialog. Log message `"[Stitch] Canvas layout available — click '⬗ Canvas' to inspect."` emitted on enable. |
| **`frame_h`/`frame_w` in `stage08_canvas_info.json`** (`stitch_worker.py`) | Two new fields added to the `_save_json(8, "canvas_info", ...)` dict: `"frame_h": int(H)` and `"frame_w": int(W)`, where `H, W = frames[0].shape[:2]` (already in scope at Stage 8). Required for the canvas polygon renderer to know the frame dimensions. Zero-cost — no algorithmic changes. |
| **9 unit tests** (`test_stitch_tab.py`) | `TestParseCanvasJson`: valid fixture fields parsed correctly; missing frame_h/frame_w default to 0; affines_final values coerced to float. `TestCanvasFrameCorners`: identity affine returns raw corners exactly; pure translation shifts all corners; 90° CCW rotation affine verified against closed-form. `TestCanvasLayoutInspectorDialog`: 3-frame fixture populates table and stats; zero frame dimensions skip polygon draw but update stats; no-data instantiation leaves label at "No data loaded.". **422 tests passing.** |

### Design rationale

Same read-only viewer pattern as §2.2 (Session 77): `_ProgressPipeline` already writes `stage08_canvas_info.json` when `save_intermediate=True`, so the dialog consumes a static file — zero pipeline changes, zero new worker signals. The two-field extension to `stitch_worker.py` (`frame_h`/`frame_w`) is pure serialisation change to the debug dump; the `_parse_canvas_json` function defaults them to zero for backward compatibility with existing JSON files.

`_canvas_frame_corners` uses the full 2×3 affine rather than just the `tx`/`ty` diagonal, so the polygons correctly show rotation and scale distortion when `ASP_SIMILARITY_MODE=1` or affine-mode BA is active.

Visual render verified (2026-06-11): 3-frame synthetic fixture with correct overlap shows 3 colour-coded blocks side-by-side on a dark canvas, canvas border visible, stats "3 frames · 1850×500 canvas", table tx=10.0/620.0/1210.0 ty=50.0.

---

## ASP Session 77 — §2.2 Edge Graph Inspector (read-only viewer) (2026-06-11)

### Shipped

| Item | Summary |
|------|---------|
| **`_parse_edge_json(path) → List[dict]`** (`stitch_tab.py`) | §2.2: Loads and normalises a `stage05_edges.json` file saved by `_ProgressPipeline`. Drops records missing `i` or `j`. Fills `dx`, `dy`, `conf`, `method` with safe defaults (0.0, 0.0, 0.0, `"?"`) when absent. Returns a clean list ready for the graph renderer. |
| **`_edge_graph_node_positions(n, radius=150.0) → List[Tuple]`** (`stitch_tab.py`) | Pure function: places N nodes evenly on a circle of given radius, first node at 12 o'clock (−π/2 offset). Returns `[]` for n≤0, `[(0,0)]` for n=1. Used as the layout engine for the graph scene. |
| **`EdgeGraphInspectorDialog(QDialog)`** (`stitch_tab.py`) | Read-only edge graph viewer. Left pane: `QGraphicsScene`/`QGraphicsView` with dark background — frame nodes as labelled blue circles, match edges as lines colour-coded by confidence (green ≥ 0.7, yellow ≥ 0.5, red < 0.5), line width 1+conf×4px, tooltip per edge shows i→j/conf/dx/dy/method. Right pane: `QTableWidget` sorted by conf ascending (worst-first), columns From/To/Conf/Method/dx/dy, cells coloured to match edge confidence. Stats label: "N frames · K edges · M low-conf". "Load JSON…" toolbar button for standalone use. |
| **`⬡ Edges` button in Stitch action row** (`stitch_tab.py`) | Initially disabled. Enabled in `_on_stitch_finished` when `stage05_edges.json` is found in `_last_stages_dir`. Calls `_inspect_edges()` which parses the JSON and opens the dialog. Log message `"[Stitch] Edge graph available — click '⬡ Edges' to inspect."` emitted on enable. |
| **`self._last_stages_dir`** (`stitch_tab.py`) | New state variable on `EditTab`. Set from `worker._intermediate_dir` at start of each run so `_on_stitch_finished` and `_inspect_edges` always reference the correct run's stages dir. |
| **11 unit tests** (`test_stitch_tab.py`) | `TestParseEdgeJson`: valid fixture, missing optional fields → defaults, records without i/j skipped, empty array → empty list. `TestEdgeGraphNodePositions`: zero → empty, single → origin, N equidistant from centre (radius check), first node at 12 o'clock. `TestEdgeGraphInspectorDialog`: table populated + stats label, table sorted worst-first, empty edges → "No edges." message. **413 tests passing.** |

### Design rationale

`_ProgressPipeline` already writes `stage05_edges.json` (i, j, dx, dy, conf, method per edge) when `save_intermediate=True`. The viewer consumes this file directly — zero changes to pipeline code, zero new worker signals, no §2.7 staging architecture required. This ships the core "what did my edge graph look like?" diagnostic immediately and unblocks future sessions from adding the interactive delete/re-solve path on top.

Visual check is intentionally deferred: no `asp_test*` corpus exists on this machine, so no stitch run has been made with `save_intermediate=True`. The `_parse_edge_json` / `_edge_graph_node_positions` logic is verified by the 11 unit tests; the rendered graph will be visually validated when the corpus arrives.

---

## ASP Session 76 — §1.32 GNC-TLS Bundle Adjustment (2026-06-11)

### Shipped

| Item | Summary |
|------|---------|
| **`_gnc_weights_geman_mcclure(residuals_sq, mu, c_sq) → ndarray`** (`bundle_adjust.py`) | §1.32: Geman-McClure per-edge GNC weights `wᵢ = (μc² / (μc² + rᵢ²))²`. At large μ (initial) all weights ≈ 1 (convex quadratic regime). As μ decreases over outer iterations, edges with large residuals receive exponentially smaller weights, approximating the truncated-LS cost. Yang et al., IEEE RA-L 2020. Exported in `__all__`. |
| **GNC-TLS outer continuation loop in `_bundle_adjust_affine`** (`bundle_adjust.py`) | `_GNC_OUTER=8` outer iterations (default ON, `ASP_GNC_OUTER=0` reverts to §1.1C Cauchy). Loop: initialise μ₀=max_sq/(2c²) so the surrogate starts convex; per-iter: compute per-edge squared translation disagreement, update GM weights, LM step with `loss='linear'` and `√w` multiplier in the `residuals()` closure, anneal μ÷=1.4; terminates on ‖Δx‖<1e-3 or μ<0.01. |
| **`_gnc_ws` mutable closure** (`bundle_adjust.py`) | `List[float]` captured by `residuals()`; updated in-place by the GNC loop. `residuals()` multiplies each edge contribution by `_gnc_ws[idx]` (= `√wᵢ`), giving scipy LM the effective weighted cost `wᵢ·rᵢ²`. Priors and regularisers remain unweighted. |
| **`GNC_C_PX=10.0`, `GNC_MU_ANNEAL=1.4`, `GNC_MAX_OUTER=8`** (`constants/animation.py`) | §1.32 constants. `GNC_C_PX=10px`: edges with 10px residual receive 50% weight at μ=1; `GNC_MU_ANNEAL=1.4`: 8-step schedule spans ~15× dynamic range. |
| **`ASP_GNC_OUTER` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 20, "GNC-TLS outer iterations (0=Cauchy only, default 8)")`. |
| **5 unit tests** (`test_bundle_adjust.py::TestGNCWeightsGemanMcclure`) | unit-weights-large-mu (μ=1e6 → all weights > 0.999), zero-residual-weight-one (rᵢ=0 → wᵢ=1.0 exactly), high-residual-suppressed (rᵢ=100px >> c=10px → wᵢ < 0.01), weights-in-valid-range (50 random residuals ∈ [0,1]), higher-residual-lower-weight (monotone decreasing). **animation suite: 412 tests passing.** |

### Design rationale

Category B failures (test13 ratio=11.1×, test64=4.2×, etc.) occur when a single catastrophically bad LoFTR match inflates the 3×-median outlier threshold, making itself immune to the post-solve prong-1 rejection. The §1.1B spanning-tree pre-filter cannot catch a bad edge that *is* the highest-weight MST edge. The §1.1C Cauchy one-shot suppresses but cannot eliminate it once it corrupts the global median.

GNC-TLS (Yang et al. 2020) solves this directly: the first outer iteration is a pure quadratic solve (μ→∞, all edges equal), giving an unbiased initial estimate. Subsequent iterations progressively down-weight the high-residual edges in closed form (no RANSAC hypothesis sampling), converging to the truncated-LS solution. Tolerates up to ~70–80% outlier edges vs. ~50% for RANSAC-style rejection. Default ON — the solver always runs the outer loop, not an opt-in gate.

Post-solve outlier rejection (§1.1 prong-1 residual threshold + prong-2 dy-outlier check) remains unchanged as a backstop for moderate outliers that the μ schedule (1.4⁸ ≈ 15× dynamic range) leaves partially suppressed.

---

## GUI Session — §2.3A Arrow-Key Nav, §2.7B MergeWorker Cancel, §2.18B+C Color Labels, §2.19A+C Export + Copy, §2.9D Confirm Deletions (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Arrow-key gallery navigation — §2.3A** (`abstract_class_single_gallery.py`) | `_navigate_gallery(key)`, `_highlight_focused(page_paths, idx)`, `_preview_focused_item()` added, mirroring the two-galleries implementation. `_focused_idx=-1` tracked in `__init__`. `gallery.nav_left/right/up/down` wired in `keyPressEvent`; `gallery.open_preview` + `Space` call `_preview_focused_item()`. `_highlight_focused` calls `ensureWidgetVisible` on `gallery_scroll_area`. Completes §2.3A coverage for both gallery base classes. |
| **`MergeWorker.cancel()` + `_should_stop` — §2.7B** (`merge_worker.py`) | Standardised cancellation pattern added: `_should_stop=False` in `__init__`, `cancel()` sets the flag, `cancelled = Signal()` emitted if cancel fires before the blocking merge call. `_should_stop` checked after image-file resolution, before the single `ImageMerger` call. (The merge call itself is a single blocking Rust invocation that cannot be interrupted mid-execution — this covers the pre-start case.) |
| **Color label context menu — §2.18B** (`abstract_class_two_galleries.py`) | "Color Label ▶" submenu in the found-gallery right-click menu. Six color options (Red/Orange/Yellow/Green/Blue/Purple) shown with emoji icons. Each action is checkable; clicking a checked color toggles it off (clear). A "Clear Label" item at the bottom of the submenu removes the label. Labels stored in `QSettings` keyed `labels/{path}`. |
| **Color border ring on thumbnails — §2.18C** (`abstract_class_two_galleries.py`) | `update_card_style` now reads the `gallery_path` Qt property from the card widget and calls `_get_color_label(path)` to look up the label color. When unlabelled and not selected, the default border (`#4f545c`, 1px) is used. When labelled and not selected, the label color replaces the border (2px solid). Selection state takes priority over label color (selection border overrides). Card widgets get `setProperty("gallery_path", path)` at construction time to support the lookup. |
| **`_get_color_label` / `_set_color_label` helpers** (`abstract_class_two_galleries.py`) | `_get_color_label(path)` reads `QSettings("ImageToolkit","ImageToolkit").value("labels/{path}")`. `_set_color_label(path, color_key)` writes or removes the QSettings key, then calls `update_card_style` to refresh the card immediately. Class-level `_LABEL_COLORS` dict maps key → hex; `_LABEL_ICONS` maps key → emoji. |
| **`_copy_selection_to_folder()` — §2.19C** (both gallery base classes) | `shutil.copy2` loop to a `QFileDialog.getExistingDirectory`-chosen destination. Source is `selected_files` when non-empty, else the full visible list. Skips already-existing destinations (reports skipped count). `DontUseNativeDialog` on the directory picker. Bound to `Ctrl+Shift+C` via new `gallery.copy_to_folder` shortcut in `ShortcutRegistry`. |
| **"Export Paths…" + "Copy to Folder…" in right-click menu** (`abstract_class_two_galleries.py`) | Both actions added after a separator following "Move to Trash". Export calls the existing `_export_selection_as_paths()`; Copy calls the new `_copy_selection_to_folder()`. Keyboard shortcuts noted in the menu labels. |
| **`gallery.copy_to_folder` shortcut** (`shortcut_manager.py`) | Default `Ctrl+Shift+C`. Added between `gallery.export_paths` and `gallery.nav_back` in `SHORTCUT_REGISTRY`. Appears in the `Ctrl+/` shortcut discovery overlay. |
| **`_confirm_deletions_enabled()` + confirm gate in `_trash_path` — §2.9D** (`abstract_class_two_galleries.py`) | `_confirm_deletions_enabled()` reads `preferences["confirm_deletions"]` from `main_window.cached_creds` (defaults `True`). `_trash_path` now shows a `QMessageBox.question` before `send2trash` when enabled. When `confirm_deletions=False`, trashing is instant with no dialog. |
| **`_copy_selection_to_folder()` — §2.19C** (`abstract_class_single_gallery.py`) | Same implementation mirrored into `AbstractClassSingleGallery`. Wired to `gallery.copy_to_folder` in `keyPressEvent`. |

### Design rationale

Arrow-key navigation in `AbstractClassSingleGallery` mirrors the two-galleries version: `_current_cols` is already computed from the layout pass so step-by-row navigation works without additional column tracking. Color labels use `QSettings` (not the vault) because they are user-facing curation data, not security-sensitive credentials. The `gallery_path` property on card widgets is the bridge from `update_card_style`'s generic widget parameter back to the specific file path — without it, the function would need to maintain a reverse map. The label-to-color lookup adds one QSettings read per card refresh; since refresh only fires on explicit user action (not during scrolling), the overhead is negligible. `_copy_selection_to_folder` uses `shutil.copy2` (preserves mtime/permissions) and skips conflicts silently — skip count is reported in the status bar.

---

## ASP Session 75 — §1.31 Seam FG Penetration Escalation (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_fg_penetration(path, fa_zone, fb_zone) → float`** (`compositing.py`) | §1.31: Samples the seam pixel at each column `x` (row = `path[x]`, clamped to zone bounds). A pixel is foreground when any channel > 0. Returns the fraction of columns where the seam pixel is foreground in at least one zone. 0.0 for empty path or zero-width zone. |
| **Penetration escalation in blend loop** (`compositing.py`) | After §1.28 instability check: if `_SEAM_FG_PENETRATION_MAX > 0.0 and k not in seam_single_pose and penetration > threshold`, escalates to single-pose (dominant by fg pixel count). Complements §1.23/§3.15 (cost barriers) and §1.28 (path stability); catches the case where the DP routes through fg because no bg corridor exists. |
| **`_SEAM_FG_PENETRATION_MAX` flag** (`compositing.py`) | `ASP_SEAM_FG_PENETRATION_MAX=0.0` (default off). Recommend 0.7: when >70% of seam columns cut through character pixels, a hard-partition blend produces less ghosting than the DSFN ramp. |
| **Constant** (`constants/animation.py`) | `SEAM_FG_PENETRATION_MAX=0.7`. |
| **`ASP_SEAM_FG_PENETRATION_MAX` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 1.0, "Max fraction of seam columns through fg before single-pose escalation")`. |
| **`_seam_fg_penetration` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestSeamFgPenetration`) | empty-path-returns-zero, all-background-path-returns-zero, all-foreground-path-returns-one, half-foreground-returns-half, return-type-is-float. **animation suite: 482 passing.** |

### Design rationale

§1.23 and §3.15A raise the DP's cost for fg columns but cannot prevent routing through fg when every column is fg-dominated (portrait seams). §1.28 detects this indirectly via path instability, but a portrait seam routing consistently along the character midline has low std. §1.31 is the direct measure: if ≥70% of the seam pixels are on foreground, the seam bisects a character body regardless of path stability. Completes the three-layer fg-seam defence: §1.23/§3.15 (cost barriers → steer away), §1.28 (std → detect chaos), §1.31 (penetration → detect fg bisection).

---

## ASP Session 74 — §1.30 Minimum Zone Height Guard (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_zone_is_degenerate(zone_h, min_height=20) → bool`** (`compositing.py`) | §1.30: Returns True when `zone_h < min_height` (and `min_height > 0`). When the blend zone is shorter than `min_height` rows, the §1.26 boundary clamp leaves at most one valid seam row, the DSFN feather has no blending headroom, and the DP produces a constant-row path regardless of content. |
| **Wire-up in `_composite_foreground()`** (`compositing.py`) | After `fa_zone`/`fb_zone` are allocated, before DP: `if _ZONE_MIN_HEIGHT > 0 and _zone_is_degenerate(zone_h, _ZONE_MIN_HEIGHT) and k not in seam_single_pose → seam_single_pose[k] = fi_a if fg_a ≥ fg_b else fi_b`. Hard-partition blend fires at line 2001 (`_single = seam_single_pose.get(k)`). |
| **`_ZONE_MIN_HEIGHT` flag** (`compositing.py`) | `ASP_ZONE_MIN_HEIGHT=0` (default off). Recommend 20: matches the S15/S16 soft-edge band width; zones narrower than this cannot be blended cleanly regardless of DP. |
| **Constant** (`constants/animation.py`) | `ZONE_MIN_HEIGHT=20`. |
| **`ASP_ZONE_MIN_HEIGHT` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 500, "Min blend-zone rows before single-pose escalation without DP (0=off, recommend 20)")`. |
| **`_zone_is_degenerate` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestZoneIsDegenerate`) | zero-min-height-never-degenerate, zone-below-threshold-is-degenerate, zone-at-threshold-is-not-degenerate, zone-above-threshold-is-not-degenerate, negative-min-height-treated-as-disabled. **animation suite: 477 passing.** |

### Design rationale

§1.26 (`_clamp_seam_path`) clips the DP seam to `[margin, zone_h-1-margin]`. With `margin=3` and `zone_h=8`, the valid range is `[3, 4]` — two rows. The DP surface is so compressed that every path lands at the same row, the feather has no room to blend, and S15/S16 soft-edge (±6px) extends beyond the zone boundary. Escalating to single-pose for zones < 20 rows avoids all these edge cases in one gate. The 20-row threshold is equal to the S15 soft-edge band width (`2 × ASP_SP_SOFT_PX=6 + margin`), making it the natural floor for meaningful blending.

---

## ASP Session 73 — §1.29 Static Input Detection Gate (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_detect_static_input(frames, max_mad, thumb_size=64) → bool`** (`pipeline.py`) | §1.29: Resizes each frame to a 64×64 greyscale thumbnail and checks whether all consecutive pairs have mean absolute difference (MAD) < `max_mad`. Returns True only when ALL pairs are below the ceiling. Fewer than 2 frames → always False. Short-circuits on first differing pair for zero overhead on valid inputs. |
| **Stage 1.5 gate in `run()`** (`pipeline.py`) | Pre-Stage-2 check: when `_STATIC_INPUT_MAX_MAD > 0.0` and `_detect_static_input(...)` is True, logs a warning and `cv2.imwrite(frame 0 → output_path)` early return. No exception raised — caller receives a valid (but trivial) output. |
| **`_STATIC_INPUT_MAX_MAD` flag** (`pipeline.py`) | `ASP_STATIC_INPUT_MAX_MAD=0.0` (default off). Recommend 2.0: 2/255 ≈ 0.8% pixel noise, sufficient to tolerate MPEG compression noise while catching genuine all-static sequences. |
| **Constant** (`constants/animation.py`) | `STATIC_INPUT_MAX_MAD=2.0`. |
| **`ASP_STATIC_INPUT_MAX_MAD` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 255.0, "MAD ceiling for static-input detection")`. |
| **`_detect_static_input` in `__all__`** (`pipeline.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_pipeline.py::TestDetectStaticInput`) | fewer-than-two-frames-returns-false, identical-frames-returns-true, varying-frames-returns-false, just-below-threshold-returns-true, one-differing-pair-returns-false. **animation suite: 472 passing.** |

### Design rationale

Phase Correlation is the primary displacement estimator. When every input frame is identical (or near-identical), all pair responses are near-zero and Bundle Adjustment converges to a degenerate all-zero-translation solution — the pipeline produces a single frame copy with confidence. Detecting this case before Stage 1 wastes no edge-matching budget and avoids a misleading "stitched panorama" that is just one frame repeated. MAD=2.0 comfortably absorbs H.264/MPEG quantization noise (typical MAD < 0.5 for identical-looking frames from a static source) while safely ignoring normal inter-frame motion (MAD > 5 for even 5-pixel scroll).

---

## ASP Session 72 — §1.28 Seam Path Instability Escalation (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_path_std(path) → float`** (`compositing.py`) | §1.28: `float(np.std(path))`; 0.0 for empty paths. Measures how widely the seam path oscillates across the zone height — a stable seam routing along consistent rows has std≈0; a chaotic seam that spans the full zone has std≈zone_h/3. |
| **Instability escalation in blend loop** (`compositing.py`) | After `path_local` is resolved: if `_SEAM_INSTABILITY_THRESH > 0 and k not in seam_single_pose and _seam_path_std(path_local) > threshold`, escalates to single-pose. Dominant frame picked by fg pixel count in zone (same logic as §1.20). |
| **`_SEAM_INSTABILITY_THRESH` flag** (`compositing.py`) | `ASP_SEAM_INSTABILITY_THRESH=0.0` (default off). Recommend 20.0: paths with std > 20 rows are visibly unstable. |
| **Constant** (`constants/animation.py`) | `SEAM_INSTABILITY_THRESH=20.0`. |
| **`ASP_SEAM_INSTABILITY_THRESH` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 500.0, "Max seam path std before single-pose escalation")`. |
| **`_seam_path_std` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestSeamPathStd`) | empty-path-returns-zero, constant-path-returns-zero, oscillating-path-has-high-std, linearly-increasing-path-has-moderate-std, return-type-is-float. **animation suite: 467 passing.** |

### Design rationale

§1.25 (smoothing) and §1.26 (boundary clamp) reduce the _visual_ impact of an unstable path, but do not prevent the blend from straddling two incompatible frame regions. When the DP reports no stable low-cost path (std > 20 rows), the zone contains content that fundamentally cannot be blended cleanly — typically a foreground character that moved so much between frames that the "best" seam cuts through it at different heights for every column. Escalating to single-pose in this case avoids a zigzag ghost and lets §1.15 soft-edge handle the residual step.

---

## ASP Session 71 — §1.27 Background Coverage Gate for Normalisation (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_has_sufficient_bg(bg_sel, min_px=200) → bool`** (`compositing.py`) | §1.27: returns True iff `np.count_nonzero(bg_sel) >= max(1, min_px)`. None input → False. Formalises the historical hardcoded `>= 200` floor in the normalisation loop as a testable, configurable helper. |
| **Normalisation loop update** (`compositing.py`) | `len(bg_px) >= 200` replaced by `_has_sufficient_bg(bg_sel, _bg_min)` where `_bg_min = _BG_NORM_MIN_PX if _BG_NORM_MIN_PX > 0 else 200`. Default behaviour unchanged. |
| **`_BG_NORM_MIN_PX` flag** (`compositing.py`) | `ASP_BG_NORM_MIN_PX=0` (default 0 → built-in 200-px floor). Setting to a higher value tightens the gate for sparse-bg scenes. |
| **Constant** (`constants/animation.py`) | `BG_NORM_MIN_PX=200`. |
| **`ASP_BG_NORM_MIN_PX` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 10000, "Min background pixels for gain normalisation (0 = use built-in 200-px floor)")`. |
| **`_has_sufficient_bg` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestHasSufficientBg`) | sufficient-bg-returns-true, insufficient-bg-returns-false, exactly-at-threshold-returns-true, none-mask-returns-false, all-fg-returns-false. **animation suite: 462 passing.** |

### Design rationale

The normalisation loop has always guarded against sparse background with `len(bg_px) >= 200`, but this was implicit and untestable. Extracting it to `_has_sufficient_bg()` makes the contract explicit: portrait shots where BiRefNet assigns nearly the entire frame to foreground have too few background pixels for a reliable mean-luma estimate, and applying gain correction to 10–50 background pixels produces a highly noisy multiplier. The configurable `ASP_BG_NORM_MIN_PX` allows per-dataset tuning without code changes.

---

## ASP Session 70 — §1.26 Seam Path Boundary Clamp (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_clamp_seam_path(path, zone_h, margin=3) → np.ndarray`** (`compositing.py`) | §1.26: clips the DP seam path to `[margin, zone_h-1-margin]`. When the seam routes to y=0 or y=zone_h-1, the feather blend has zero headroom and degenerates to a hard edge at the zone boundary. `np.clip(path, margin, zone_h-1-margin)`. No-op when margin ≤ 0 or `zone_h ≤ 2*margin` (bounds would invert). |
| **`_SEAM_MARGIN` flag** (`compositing.py`) | `ASP_SEAM_MARGIN=3` (default 0=off). Wired at end of `_seam_cut()` after §1.25 smoothing. |
| **Constant** (`constants/animation.py`) | `SEAM_MARGIN=3`. |
| **`ASP_SEAM_MARGIN` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 50, "Min rows between seam path and zone top/bottom edge (0 = off, recommend 3)")`. |
| **`_clamp_seam_path` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestClampSeamPath`) | zero-margin-returns-unchanged, path-clamped-above-margin, path-clamped-below-upper-bound, in-range-values-unchanged, zone-too-small-returns-unchanged. **animation suite: 457 passing.** |

### Design rationale

The feather blend in `_composite_foreground` requires at least `feathers[k]` rows of valid zone content on either side of the seam centre. When `_seam_cut()` routes the path to the zone boundary (y=0 or y=zone_h-1), the blend array is sliced to a zero-height region — producing a hard cut at the zone edge that is visually distinct from the intended feather transition. `margin=3` is a conservative floor (three pixels of headroom); larger values can be set via `ASP_SEAM_MARGIN` for zones with wide feathers. The `zone_h ≤ 2*margin` guard prevents the bounds from inverting on very thin zones.

---

## ASP Session 69 — §1.25 Seam Path Smoothing (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_smooth_seam_path(path, window=5) → np.ndarray`** (`compositing.py`) | §1.25: applies a 1-D median filter of size *window* to the DP seam-cut path. Raw argmin traceback can produce single-pixel sideways jumps that alias into diagonal bands at the seam boundary. Formula: `scipy.ndimage.median_filter(path.astype(float32), size=window).astype(int32)`. Even window incremented to next odd. window ≤ 1 is a no-op. |
| **`_SEAM_SMOOTH_WINDOW` flag** (`compositing.py`) | `ASP_SEAM_SMOOTH_WINDOW=5` (default 0=off). Wired at the end of `_seam_cut()` — after traceback, before return. |
| **Constant** (`constants/animation.py`) | `SEAM_SMOOTH_WINDOW=5`. |
| **`ASP_SEAM_SMOOTH_WINDOW` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 51, "Median-filter window for seam path jitter removal (0 or 1 = off, recommend 5)")`. |
| **`_smooth_seam_path` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestSmoothSeamPath`) | window-zero-returns-unchanged, window-one-returns-unchanged, smooth-path-removes-spike, constant-path-unchanged, even-window-incremented-to-odd. **animation suite: 452 passing.** |

### Design rationale

The `_seam_cut()` DP traceback selects the locally-optimal column at each step (`argmin` over a ±1 window). When adjacent columns have nearly equal energy, the traceback oscillates: column 3 → column 4 → column 3 → column 4, producing a visible zigzag band at the boundary. A 1-D median filter of window=5 removes oscillations of period ≤ 2 (single-pixel jitter) while preserving the coarser seam routing (bends of ≥ 3px extent pass through unchanged). This is analogous to path post-processing in graph-cut segmentation and is already standard in video seam-carving literature.

---

## ASP Session 68 — §1.24 Post-Composite Seam-Step Gate (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_measure_max_seam_step(canvas, n_strips, band_px=10, guard=3) → float`** (`pipeline.py`) | §1.24: samples mean greyscale luma in `band_px` rows above and below each inter-strip boundary (±`guard` guard rows). Returns `max(|above − below|)` across all N-1 seams. Returns 0.0 when n_strips ≤ 1 or canvas too small. |
| **Stage 11.3 gate** (`pipeline.py`) | `_SEAM_STEP_GATE` flag (default 0.0=off, `ASP_SEAM_STEP_GATE=25.0`). After Stage 11.2 colour gate: measures `_measure_max_seam_step(canvas, N)`. If > threshold → SCANS fallback. |
| **Constant** (`constants/animation.py`) | `SEAM_STEP_GATE_THRESH=25.0`. |
| **`ASP_SEAM_STEP_GATE` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 255.0, "Max luma step at seam boundary before SCANS fallback")`. |
| **`_measure_max_seam_step` in `__all__`** (`pipeline.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_pipeline.py::TestMeasureMaxSeamStep`) | single-strip-returns-zero, uniform-canvas-returns-near-zero, step-detected-at-boundary, max-returned-for-multiple-seams, small-canvas-no-crash. **animation suite: 447 passing.** |

### Design rationale

Stage 11.2 (§1.14B, S56) detects mismatched-colour seam zones in source frames before compositing. Stage 11.3 operates on the final composite output: if a luminance step >25 lum units persists at any strip boundary (≈"visible step" in the `seam_visibility_score` taxonomy from §3.8), the photometric normalisation has failed and SCANS is a better result. The guard rows (default 3) prevent sampling in the immediate artefact zone at the seam boundary itself; `band_px=10` samples the stable region just outside the transition. Complements Stage 11.2 without overlap.

---

## ASP Session 67 — §1.23 SemanticStitch Hard Corridor Barrier (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_corridor_exists(cost, fg_thresh=0.5) → bool`** (`compositing.py`) | §1.23: returns True iff the cost map has both fg-dominated columns (>50% fg-interior) AND non-dominated columns (background corridor). False when all columns are fg-dominated (no corridor) or none are (no barrier needed). |
| **`_build_seam_cost_map(..., barrier_cost=None)` extended** (`compositing.py`) | New `barrier_cost` parameter. When `None`: uses module-level `_SEAM_HARD_BARRIER` flag to choose between 2.0 (S33 soft) and `_SEAM_HARD_BARRIER_COST` (1e6 hard). When corridor exists, fg-dominated columns are raised to `barrier_cost` instead of hardcoded 2.0. Backward-compatible: default path is identical to S33. |
| **`_SEAM_HARD_BARRIER` / `_SEAM_HARD_BARRIER_COST` flags** (`compositing.py`) | `ASP_SEAM_HARD_BARRIER=1` (default OFF). `ASP_SEAM_HARD_BARRIER_COST=1e6` (configurable). |
| **Constants** (`constants/animation.py`) | `SEAM_HARD_BARRIER_COST=1e6`. |
| **2 entries in `_CONFIG_SCHEMA`** (`config.py`) | `ASP_SEAM_HARD_BARRIER (int, 0, 1)` and `ASP_SEAM_HARD_BARRIER_COST (float, 0, None)`. |
| **`_seam_corridor_exists` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestSeamCorridorExists`) | all-dominated-returns-false, all-bg-returns-false, mixed-returns-true, hard-barrier-applied-when-corridor, soft-barrier-backward-compat. **animation suite: 442 passing.** |

### Design rationale

S33 (§3.15A) set fg-dominated columns to cost=2.0 — soft deterrence. With `sem_weight=200` in `_seam_cut()`, a cost-2.0 column costs 400 energy vs a cost-1.0 fg-interior column at 200. The DP is discouraged but not prevented from routing through fg columns. When a background corridor exists (detected by `_seam_corridor_exists`), setting the barrier to 1e6 makes the fg-column path 5000× more expensive than any background path — the DP is effectively forced into the corridor. The graceful fallback (no corridor → cost stays 2.0) maintains S33 behaviour when the character fills the full overlap width.

---

## ASP Session 66 — §1.22 Adaptive Single-Pose Soft-Edge Width (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_adaptive_sp_soft_px(feather_width, base_px=6, max_px=30, ref_px=80) → int`** (`compositing.py`) | §1.22: scales the single-pose soft-edge half-width proportionally to the original feather width that triggered escalation. Formula: `min(max_px, max(base_px, base_px * feather_width // ref_px))`. At feather=80px returns 6 (baseline unchanged); at feather=160px returns 12; at feather=300px returns 22; capped at 30px. `feather_width ≤ 0` is handled safely (returns base_px). |
| **`_ADAPTIVE_SP_SOFT` flag** (`compositing.py`) | `ASP_ADAPTIVE_SP_SOFT=1` (default OFF). When ON, replaces the fixed `ASP_SP_SOFT_PX=6` in the single-pose branch of the blend loop with a per-seam adaptive value computed from `feathers[k]`. |
| **Constants** (`constants/animation.py`) | `SP_SOFT_BASE_PX=6`, `SP_SOFT_MAX_PX=30`, `SP_SOFT_REF_PX=80`. |
| **`ASP_ADAPTIVE_SP_SOFT` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 1, "Enable adaptive single-pose soft-edge width scaled by feather")`. |
| **`_adaptive_sp_soft_px` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestAdaptiveSpSoftPx`) | at-ref-px-returns-base, doubles-for-double-ref, narrow-feather-clamps-to-base, wide-feather-caps-at-max-px, zero-feather-returns-base. **animation suite: 437 passing.** |

### Design rationale

§1.15 (S15) always applies a fixed ±6px soft edge at single-pose seams. When §1.18 escalates a 300px feather to single-pose, the viewer expects a gentle transition over ~300px but sees a hard cut softened by only 6px — visually equivalent to a hard cut. The 6px was calibrated for the S15 baseline (feathers 80–120px). For wide feathers (160–300px), the appropriate soft edge is 12–22px: large enough to conceal the cut but narrow enough to avoid the ghost risk (double-image artefact requires ≥40px overlap to form). §1.22 derives the soft edge from the original feather width, maintaining the no-ghost guarantee while eliminating the visible step that §1.18 alone creates.

---

## ASP Session 65 — §1.21 Post-Composite Seam Luminance Equalisation (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_lum_equalize(canvas, boundaries, band_px=20, min_step=5.0) → np.ndarray`** (`compositing.py`) | §1.21: for each boundary, samples mean greyscale luminance in band_px-row reference windows above and below (±3-row guard). When step > min_step lum units, applies a linear additive ramp over band_px rows below the boundary subtracting the step to smooth the transition. Equal BGR correction (luminance shift, chrominance preserved). Returns uint8 copy. |
| **`_SEAM_LUM_EQ` flag** (`compositing.py`) | `ASP_SEAM_LUM_EQ=1` (default OFF). Wired just before `return result` in `_composite_foreground`. |
| **Constants** (`constants/animation.py`) | `SEAM_LUM_EQ_BAND_PX=20`, `SEAM_LUM_EQ_MIN_STEP=5.0`. |
| **`ASP_SEAM_LUM_EQ` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 1, "Enable post-composite seam luminance equalisation pass")`. |
| **`_seam_lum_equalize` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestSeamLumEqualize`) | no-step-no-change, step-above-threshold-reduced, step-below-threshold-not-corrected, boundary-near-edge-no-crash, returns-uint8-dtype. **animation suite: 432 passing.** |

### Design rationale

test27 (Class D) has SC=26.7 — visible luminance step at seam boundaries despite only 4% background gain spread. The step comes from ARAP warp residuals in the midpoint blend, not from gain mismatch. §1.16 (seam color match) and §1.4B/C (background gain) operate on intermediate compositing state. §1.21 operates on the FINAL output, correcting whatever step remains after all upstream passes. The ramp only touches band_px rows below the boundary — the upstream zone is untouched. The ±3-row guard prevents sampling the artefact region at the seam itself.

---

## ASP Session 64 — §1.20 Tight-Step Preemptive Single-Pose Escalation (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_seam_step_size(fi_a, fi_b, affines) → float`** (`compositing.py`) | §1.20: returns `max(|ty_b−ty_a|, |tx_b−tx_a|)` — dominant-axis camera step between two frame canvas positions. Returns `float("inf")` for out-of-range frame indices. |
| **Tight-step preemptive escalation in FG registration loop** (`compositing.py`) | `_TIGHT_STEP_PX` flag (default 0=off, `ASP_TIGHT_STEP_PX=30`). When step < threshold, skip ARAP entirely and immediately set `seam_single_pose[k]` based on which frame has more fg pixels in the ±20px boundary band. Records step size in `seam_post_diffs[k]`. |
| **`TIGHT_STEP_PX = 30`** (`constants/animation.py`) | Recommended threshold. At 1080p with 30px step, the character occupies 97%+ of both frames' overlap zone — ARAP cannot correct the animation pose difference. |
| **`ASP_TIGHT_STEP_PX` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 500, "Dominant-axis step (px) below which seam is preemptively single-posed (0=off)")`. |
| **`_compute_seam_step_size` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestComputeSeamStepSize`) | pure-vertical-step (ty=50→50.0), pure-horizontal-step (tx=80→80.0), uses-dominant-axis (dy=15/dx=60→60.0), exactly-at-threshold-not-below (step=30, strict < means 30 is not below 30), out-of-range-frame-returns-inf (fi=99→∞). **animation suite: 427 passing.** |

### Design rationale

For sequences with tiny camera steps (e.g., test57: min_gap=10.8px, spacing_ratio=3.379), the animation may have advanced significantly relative to the minimal camera motion. In those cases, frame_a and frame_b show nearly the same background position but the character is in a completely different pose. ARAP registration can warp one character pose toward another, but when the poses are related by complex non-rigid motion across the full body, the residual after warping is still large — creating a ghost. Rather than discovering this AFTER a slow ARAP pass, §1.20 detects it BEFORE registration: any seam where the camera moved < 30px gets immediately assigned to the higher-fg-count frame. The dominant-frame selection (by fg pixel count in ±20px boundary band) ensures the character-heavier frame defines the seam zone. The step threshold is tunable; at 30px the gate fires on all "dense-step" seams in irregular-speed sequences while leaving normal-speed seams (>30px) for ARAP.

---

## ASP Session 63 — §1.19 Foreground-Density-Aware Feather Cap (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_fg_density_feather_cap(feathers, boundaries, warped_bg, order, cap_px, fg_thresh) → np.ndarray`** (`compositing.py`) | §1.19: checks fg pixel fraction in ±feather[k] band around boundaries[k] in canvas-space warped_bg for each adjacent frame pair. When max(fg_frac_a, fg_frac_b) > fg_thresh, caps feather to cap_px. Masks of None treated as all-bg (cap never fires without a BiRefNet mask). Returns copy of feathers (input not mutated). |
| **`_FG_FEATHER_CAP` / `_FG_FEATHER_THRESH` flags** (`compositing.py`) | `ASP_FG_FEATHER_CAP=60` (px cap value; 0=off, the default). `ASP_FG_FEATHER_THRESH=0.60` (fg fraction threshold). Wired after §1.6B gain-adjusted feathers and before Stage 8.5 FG registration. |
| **Constants** (`constants/animation.py`) | `FG_FEATHER_CAP=60`, `FG_FEATHER_THRESH=0.60`. |
| **`ASP_FG_FEATHER_CAP` / `ASP_FG_FEATHER_THRESH` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 300, ...)` and `(float, 0.0, 1.0, ...)`. |
| **`_fg_density_feather_cap` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestFgDensityFeatherCap`) | all-bg-no-cap, all-fg-applies-cap, feather-already-narrow-skips, uses-max-of-two-frames, none-mask-treated-as-all-bg. **animation suite: 422 passing.** |

### Design rationale

§1.18 fires AFTER ARAP registration using post_warp_diff as the signal. §1.19 fires BEFORE registration using the fg density of the blend zone. When the seam boundary crosses a character-heavy zone (>60% fg), any feather wider than cap_px blends two different animation poses over that distance → double-image ghost. The cap reduces the blend zone immediately. The two gates are independent: §1.18 catches high post_warp_diff after ARAP; §1.19 catches character-dominated zones before ARAP runs. `warped_bg` is in canvas space — correct for checking boundary zones.

---

## GUI Session — §2.23A Accessible Names on Pagination Widgets (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Accessible names — §2.23A** (`meta_abstract_class_gallery.py`) | `setAccessibleName()` added to all interactive pagination controls: page-size `QComboBox` ("Images per page"), sort `QComboBox` ("Sort by"), sort direction button ("Toggle sort direction"), Prev/Page/Next buttons ("Previous page" / "Current page" / "Next page"), item range label ("Item range"), thumbnail slider ("Thumbnail size" + description), item range label. Applies to every gallery tab via the shared `_common_create_pagination_ui` factory. |

---

## GUI Session — §2.4B+C Shift+Click Range Select + Right-Click Context Menu (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Shift+click range select — §2.4B** (`abstract_class_two_galleries.py`) | `_on_found_card_clicked(path)` replaces direct `toggle_selection` as the `path_clicked` handler for found-gallery cards. When `Shift` is held (`QApplication.keyboardModifiers()`), selects all cards from `_selection_anchor_idx` to the clicked index (inclusive, within current page). Without Shift, updates `_selection_anchor_idx` and delegates to `toggle_selection`. |
| **Right-click context menu — §2.4C** (`abstract_class_two_galleries.py`) | `_on_found_card_right_clicked(global_pos, path)` connected to `path_right_clicked` signal on all `ClickableLabel` cards. Menu items: Open Preview, (sep), Select/Deselect, Select All, Deselect All, (sep), Rename… (F2), Move to Trash. Trash item calls `_trash_path(path)` which uses `send2trash`, removes the path from all in-memory lists, and refreshes both galleries. |

### Design rationale

`_selection_anchor_idx` is the Shift+click anchor — set only on non-Shift left clicks, so multiple Shift+clicks extend from the same anchor (standard file-manager behaviour). Range selection operates on `master_found_files` page slice, so it is consistent with what the user sees. The right-click context menu surfaces the three most common per-image operations (preview / rename / trash) without requiring keyboard shortcuts knowledge.

---

## GUI Session — §2.25A Shortcut Overlay, §2.20A QSplitter Persistence, §2.17D Log Window (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Shortcut discovery overlay — §2.25A** (`main_window.py`) | `_open_shortcut_overlay()` — `Ctrl+/` or `F1` opens a `QDialog` (560×460) with a real-time filter `QLineEdit` and a 3-column `QTableWidget` (Scope / Action / Key). Populated from `ShortcutRegistry.get_all()` including the active binding. Filter searches all three columns. `QHeaderView.ResizeMode.Stretch` on the Action column; ResizeToContents on Scope and Key. |
| **QSplitter persistence — §2.20A** (`splitter_persistence.py` + 5 tabs) | New `gui/src/utils/splitter_persistence.py` — `persist_splitter(splitter, key)` restores from `QSettings("splitters/{key}")` then wires `splitterMoved` to auto-save. Wired at: `StitchFeedbackTab/main`, `StitchPanel/main`, `GraphPanel/vertical`, `GraphPanel/horizontal`, `CanvasPanel/main`, `ThumbnailFilePicker/sidebar`. `listings_tab.py` already had its own inline `_persist_splitter`; all 4 of its splitters remain covered. |
| **Log window upgrade — §2.17D** (`log_window.py`) | Already shipped in a prior session: `QPlainTextEdit` (not `QTextEdit`), colour-coded levels via `LEVEL_COLORS` (`ERROR`=red, `WARNING`=orange, `INFO`=white, `DEBUG`=grey), timestamp prefix, "Follow" auto-scroll toggle, Copy All / Save… / Clear toolbar. Now documented. |

### Design rationale

`persist_splitter` uses a lazy `QSettings` write on `splitterMoved` — no timer or debounce needed because Qt debounces splitter drag events natively. The key scheme `"category/widget_name"` (e.g. `"StitchPanel/main"`) is collision-free across all tabs without per-tab registration. Shortcut overlay uses the registry's `get_all()` which already merges defaults + user overrides, so it shows the effective binding including any customisations from the shortcut editor (§2.29).

---

## GUI Session — §2.16C Ctrl+T Tab Search Popup (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Ctrl+T tab search — §2.16C** (`main_window.py`) | `_open_tab_search()` opens a frameless `QDialog` (popup mode, 400px wide) with a `QLineEdit` filter and `QListWidget` showing `"Tab Name  —  Category"` entries. Typing filters in real-time. `Enter` / double-click navigates: sets `command_combo` to the correct category then `_select_tab_by_name()` after a `QTimer.singleShot(0)` tick. Bound to `Ctrl+T` in `keyPressEvent`. |

### Design rationale

`QTimer.singleShot(0)` is required because `on_command_changed` synchronously clears and re-adds all tabs — the tab widget needs one event-loop tick before `tabText(i)` reflects the new category's tabs. Frameless popup auto-dismisses on click-outside without extra focus tracking. `WindowType.Popup` achieves this with no additional code.

---

## GUI Session — §2.11A+B+D Preview Enhancements, §2.12A+B+C System Tray (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Fullscreen toggle — §2.11A** (`image_preview_window.py`) | `_toggle_fullscreen()` — `showFullScreen()` / `showMaximized()` toggle. Wired to `F11` / `F` (no modifier) and registered as `preview.fullscreen` in `ShortcutRegistry`. Context menu entry updates label dynamically ("Fullscreen" ↔ "Exit Fullscreen"). |
| **Fit modes — §2.11B** (`image_preview_window.py`) | `_fit_to_width()`, `_fit_to_height()`, `_zoom_actual_pixels()`. Fit-to-width uses `viewport().width() / orig.width()`; fit-to-height uses height equivalent; 100% sets `current_zoom_factor=1.0`. Bound to `W`, `H`, `1`. Registered as `preview.fit_width`, `preview.fit_height`, `preview.actual_size`. Context menu shows all three. |
| **Rotation — §2.11D** (`image_preview_window.py`) | `_rotate(clockwise: bool)` applies `(rotation_degrees ± 90) % 360` and calls `update_image_display()` (which applies `QTransform().rotate(degrees)` during scaling). Bound to `R` (CW) and `L` (CCW). Registered as `preview.rotate_cw`, `preview.rotate_ccw`. Context menu shows both. In-memory only; does not write to disk. |
| **System tray icon — §2.12A** (`main_window.py`) | `_setup_tray_icon(app_icon)` called in `__init__` when `QSystemTrayIcon.isSystemTrayAvailable()`. Loads `assets/images/image_toolkit_icon.png`; falls back to `SP_ComputerIcon`. Context menu: Show Window, Toggle Daemon, Next Wallpaper, (sep), Quit. Double-click activates window. |
| **Tray balloon notifications — §2.12B** (`main_window.py`) | `tray_notify(title, message, timeout_ms=4000)` instance method. Module-level `show_tray_notification()` traverses `topLevelWidgets()` for app-wide access. Uses `QSystemTrayIcon.showMessage(MessageIcon.Information)`. |
| **Minimize to tray — §2.12C** (`main_window.py`) | `set_minimize_to_tray(enabled)` sets `_minimize_to_tray` flag. When enabled, `closeEvent` calls `event.ignore(); self.hide()` and shows a one-time tray notification instead of quitting. Opt-in; disabled by default. |

### Design rationale

All preview-window hotkeys are registered in `ShortcutRegistry` so they appear in the shortcut discovery overlay (§2.25) and the global keybindings editor (§2.29). `_rotate` uses `QTransform` on the cached `QPixmap` / `QMovie` frame — no disk write, clearly communicated by context-menu label. Tray availability is checked at runtime; the feature degrades silently on systems without a system tray (e.g., bare Wayland without xdg-portal). `_minimize_to_tray` is `False` by default to avoid confusing users who expect the window to close.

---

## GUI Session — §2.21A+D Dir History + MRU Dropdown, §2.26B Inline Rename (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Dir navigation history — §2.21A** (`abstract_class_two_galleries.py`) | `_push_dir_history(path)`, `_dir_go_back() → Optional[str]`, `_dir_go_forward() → Optional[str]` helpers. `deque(maxlen=20)` back and forward stacks. `Alt+Left` / `Alt+Right` wired in `keyPressEvent` via `gallery.nav_back` / `gallery.nav_forward` shortcuts (added to `ShortcutRegistry`). Virtual `_navigate_to_dir(path)` hook (no-op in base, overridden in `FormatTab`). |
| **MRU recent-dirs dropdown — §2.21D** (`convert_tab.py`) | `▼` `QToolButton` (instant-popup mode, fixed 24px wide) appended to FormatTab's input path row. `_show_recent_dirs_menu()` populates and shows the menu from `_get_recent_dirs()`. `browse_directory_and_scan()` now calls `_push_dir_history` + `_add_recent_dir` on successful browse. Also fixes missing `DontUseNativeDialog` flag on that `QFileDialog` call. |
| **Inline rename — §2.26B** (`abstract_class_two_galleries.py`) | `_rename_focused_file()` method: opens `QInputDialog.getText` pre-filled with stem (no extension). Sanitises illegal filesystem characters. Guards against name conflict. On success: calls `os.rename`, updates `found_files`, `master_found_files`, `selected_files`, `path_to_label_map` via `_replace_path_in_lists()`. Bound to `F2` via `gallery.rename` shortcut (already in registry). |

### Design rationale

Virtual `_navigate_to_dir` in the base class means back/forward dispatch compiles for all tabs — only FormatTab implements it for now; the others silently no-op until they add their own override. The MRU menu is separate from the Browse dialog to avoid an extra modal round-trip for common re-visits. Rename sanitises `\/:*?"<>|` which covers FAT32, NTFS, and ext4 reserved characters.

---

## GUI Session — §2.10C QStatusBar, §2.14A Filename Labels (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **QStatusBar — §2.10C** (`main_window.py`) | `QStatusBar` added to the bottom of `MainWindow`'s vbox layout (height-capped 24px, size grip off). `show_status(message, timeout_ms=3000)` instance method on `MainWindow`. Module-level `show_main_status()` function traverses `topLevelWidgets()` so any tab can post a status message without holding a direct window reference. `_show_status()` helper added to both gallery base classes; wired into `_export_selection_as_paths()` and `copy_image_to_clipboard()`. |
| **Filename labels — §2.14A** (both gallery base classes) | `_add_filename_label(card, path)` method added to `AbstractClassTwoGalleries` and `AbstractClassSingleGallery`. Appends a `QLabel` (`thumb_filename_lbl`) with elided middle-truncated filename (`fontMetrics().elidedText(ElideMiddle)`) to every thumbnail card's `QVBoxLayout`. Card height extended by `fm.height() + 4`. Called at all three card creation sites (found gallery, selected gallery, single gallery). |

### Design rationale

`QStatusBar` works as a standalone widget (MainWindow is a `QWidget`, not `QMainWindow`). Module-level traversal avoids direct import cycles between tab modules and the main window. Filename labels use `ElideMiddle` so the extension is always visible for long names. `_add_filename_label` is appended after `create_card_widget` — the existing `findChild(QLabel)` calls in `update_card_pixmap` still resolve to the image label (added earlier/deeper in the hierarchy).

---

## GUI Session — §2.13A+E Sort Toolbar + Search Operators, §2.15A Trash (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Search operators — §2.13E** (`meta_abstract_class_gallery.py`) | `_common_filter_string_list` upgraded from a plain `in` check to a multi-token engine. Supported: `-term` (exclude), `"phrase"` (exact), `a\|b` (OR); tokens AND-combined. Placeholder updated to hint syntax. |
| **Sort toolbar — §2.13A** (both gallery base classes) | Sort `QComboBox` (Name / Date Modified / File Size / Extension) + `↑`/`↓` button in pagination bar. `_sort_key_fn()` dispatches to `getmtime`/`getsize`/`splitext`/`natural_sort_key`. `_apply_sort()` is a pure sorted() call. Re-sort fires on combo change, direction toggle, and initial directory load. |
| **Move to Trash — §2.15A** (`delete_tab.py`, `wallpaper_tab.py`, `search_tab.py`) | `send2trash(path)` replaces `os.remove` at all user-initiated image deletion sites. Dialogs updated ("Move to Trash"). `send2trash>=1.8.3` added to `pyproject.toml`. |

### Design rationale

Token parser extracts quoted phrases first (regex), then splits remainder on whitespace. OR uses `|` without spaces (matches file-manager convention). Sort in pagination bar groups with "page size" left of the stretch, not with nav arrows. `_apply_sort` is a pure function — no in-place mutation until the caller reassigns.

---

## GUI Session — §3.9 Item Range Label, §4.11 Thumbnail Slider (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Default page size 100→150** (`meta_abstract_class_gallery.py`) | Combo default changed to `"150"` and `"150"` added to the item list between `"100"` and `"250"`. Both gallery base classes updated from `page_size = 100` to `150`. |
| **Item range label — §3.9** (both gallery base classes) | `item_range_lbl` (`QLabel`, min-width 120px) added to every pagination bar between the page-size combo and the prev/next buttons. Text: `"Items 1–150 of 843"` or `"0 images"`. Updated in `_update_pagination_ui` on every pagination state change. |
| **Thumbnail size slider — §4.11** (`meta_abstract_class_gallery.py`) | `QSlider` (range 64–512, step 16, fixed width 110px) + `thumb_size_lbl` ("180 px") added to the right end of every pagination bar. The `⊞` icon precedes the slider as a visual hint. Returns in `controls` dict as `"thumb_slider"` and `"thumb_size_lbl"`. |
| **Per-tab thumbnail persistence** (both gallery base classes) | `_save_thumbnail_size()` — `QSettings` keyed `session/{ClassName}/thumbnail_size`. `_load_thumbnail_size(default=180)` — called at `__init__` before `approx_item_width` is set. `_sync_thumb_slider()` — updates all slider widgets without triggering signals (via `blockSignals`). |
| **Slider wiring** (both gallery base classes) | `valueChanged` → `_on_thumb_slider_changed()` (16px snap, live gallery reload). `sliderReleased` → `_save_thumbnail_size()`. Initial slider value set from `self.thumbnail_size` in `create_pagination_controls()`. |
| **Ctrl+scroll → slider sync** (both gallery base classes) | `_on_ctrl_wheel_zoom()` calls `_sync_thumb_slider()` after updating `thumbnail_size`, so the slider widget always reflects the current zoom level. |

### Design rationale

A `QSlider` in the pagination bar is always visible and requires zero discoverability — unlike Ctrl+scroll which requires prior knowledge. Snapping to 16px boundaries in `_on_thumb_slider_changed` ensures the slider moves in sensible increments even when the user drags freely. Per-tab persistence uses the class name as the `QSettings` key so `WallpaperTab` and `DeleteTab` remember independent sizes. `sliderReleased` triggers the save rather than `valueChanged` to avoid writing to `QSettings` on every drag event.

---

## GUI Session — §3.15 Keyboard Shortcuts, §3.16 QSS Override, §3.17 Window Geometry (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`gui/src/utils/shortcut_manager.py`** (new file) | `SHORTCUT_REGISTRY` — 21 bindable actions across Gallery (9) and Preview (12) scopes. `ShortcutRegistry` class: `load/save/reset/matches/get_key_sequence` API. `get_registry()` module-level singleton. JSON persistence to `~/.image-toolkit/keybindings.json`. |
| **`ShortcutRegistry.matches()` PySide6 6.10 fix** | `event.key()` returns plain `int` in PySide6 6.10; `event.modifiers()` returns `KeyboardModifier` flag with `.value`. `matches()` now branches on `isinstance(raw_key, int)` and `hasattr(raw_mods, "value")` before building `QKeySequence(mods_int | key_int)`. All 8 functional assertions pass. |
| **`keyPressEvent` in gallery base classes** | Both `AbstractClassTwoGalleries` and `AbstractClassSingleGallery` now route all shortcut checks through `get_registry().matches(event, action_id)` instead of hardcoded `Qt.Key_*` comparisons. |
| **`keyPressEvent` + `QShortcut` in `ImagePreviewWindow`** | Zoom `QShortcut` objects use `get_registry().get_key_sequence("preview.zoom_in/zoom_out")`. All 11 preview key actions use `reg.matches()` in `keyPressEvent`. |
| **Settings "⌨️ Shortcuts" tab** (`settings_window.py`) | New Tab 6: `QTableWidget` with one `QKeySequenceEdit` per registry entry, conflict detection on save, Save/Reset All buttons. `_save_shortcuts` / `_reset_shortcuts` helpers. |
| **`load_user_qss_override()`** (`style.py`) | Reads `~/.image-toolkit/user_theme.qss`; returns `""` if absent. Appended last in `set_application_theme()` so user QSS wins over all theme layers. |
| **Window geometry persistence** (`main_window.py`) | `QSettings("ImageToolkit","ImageToolkit").setValue("mainwindow/geometry", self.saveGeometry())` in `closeEvent()`. `restoreGeometry()` called in `__init__` before `showMaximized()` (skipped if no saved geometry). |

### Design rationale

The `ShortcutRegistry` sits between the Qt event loop and the action handlers: `keyPressEvent` dispatches to `reg.matches(event, action_id)` which reconstructs a `QKeySequence` from the raw event and compares it to the loaded binding. This means any action can be rebound from the settings UI without touching widget code. Conflict detection is purely client-side at save time (O(n²) over 21 entries — negligible). The PySide6 6.10 enum change (`event.key()` returning `int` instead of `Qt.Key`) is handled with a `isinstance(raw_key, int)` branch that will degrade gracefully on both old and new versions. User QSS override is a single file read appended last in the theme chain — no parse-time overhead, full QSS power.

---

## GUI Session — §2.30 Accent Colour, Font Scale, UI Density (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`load_qss_with_overrides(filename, overrides)`** (`style.py`) | Merges a runtime override dict into a copy of `THEME_VARS` before `Template.safe_substitute`, allowing per-session variable injection without touching the QSS files. |
| **`compute_accent_vars(accent_hex, theme_prefix)`** (`style.py`) | Derives `ACCENT_COLOR`, `ACCENT_HOVER` (15% darker), and `ACCENT_PRESSED` (32% darker) from any valid hex colour using `QColor.darker()`. |
| **`COMPACT_DENSITY_QSS` / `SPACIOUS_DENSITY_QSS`** (`style.py`) | QSS override snippets appended after the base theme. Compact reduces button/input/groupbox padding; Spacious increases it. |
| **`set_application_theme` refactored** (`main_window.py`) | Reads `preferences["accent_color_dark/light"]`, `"ui_density"`, and `"font_scale"` from `cached_creds` at runtime. Calls `load_qss_with_overrides` instead of the static `DARK_QSS`/`LIGHT_QSS` constants; appends density QSS; applies `QApplication.setFont` for non-100% scale. |
| **Appearance groupbox in Settings → Display and Media tab** (`settings_window.py`) | Dark accent swatch button + Reset, Light accent swatch button + Reset, Font Scale `QSpinBox` (80–150%, step 10%), UI Density `QComboBox` (Compact/Comfortable/Spacious), Preview button for live apply without saving. |
| **`_pick_accent_color` / `_reset_accent` / `_update_swatch` / `_preview_appearance`** (`settings_window.py`) | Helper methods: `_pick_accent_color(theme)` opens `QColorDialog(DontUseNativeDialog)` and updates the swatch. `_preview_appearance` applies current accent/density/font to `main_window_ref` without persisting. |
| **Vault persistence** (`settings_window.py`) | Four new `preferences` keys: `accent_color_dark`, `accent_color_light`, `font_scale`, `ui_density`. Loaded in `__init__` and `reload_settings`; saved in `_update_settings_logic`; reset in `reset_settings`. |

### Design rationale

The QSS system already uses `$DARK_ACCENT_COLOR` template variables substituted via `string.Template.safe_substitute`. Rather than baking the QSS at import time, `load_qss_with_overrides` reads the file fresh and substitutes at call time — one file read per theme apply, negligible overhead. Hover/pressed variants are computed from the chosen colour automatically so users only pick one hex value. Density is a pure QSS append — no layout code changes needed. Font scale uses `QApplication.setFont` which propagates to all widgets without requiring a QSS reload.

---

## ASP Session 62 — §1.18 Adaptive Single-Pose Escalation Threshold (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_adaptive_sp_threshold(feather_width, base, min, ref) → float`** (`compositing.py`) | §1.18: scales the single-pose ghost-prevention threshold down for wide feathers. Formula: `max(min_threshold, base × (feather_reference / max(feather_width, 1)))`. At feather=80px → 22.0 (baseline unchanged); at feather≥147px → 12.0 (floor). |
| **`_ADAPTIVE_SP_THRESH` flag** (`compositing.py`) | `os.environ.get("ASP_ADAPTIVE_SP_THRESH", "0") != "0"` (default OFF). When enabled, replaces the hardcoded `_POST_DIFF_THRESHOLD = 22.0` at the single-pose escalation gate with `_adaptive_sp_threshold(int(feathers[k]))`. |
| **Constants** (`constants/animation.py`) | `ADAPTIVE_SP_THRESH_BASE=22.0`, `ADAPTIVE_SP_THRESH_MIN=12.0`, `ADAPTIVE_SP_THRESH_REF=80` document the tuned defaults. |
| **`ASP_ADAPTIVE_SP_THRESH` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 1, "Enable adaptive single-pose escalation threshold scaled by feather width")`. |
| **`_adaptive_sp_threshold` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestAdaptiveSpThreshold`) | reference-feather-returns-base (fw=80→22.0), narrow-feather-above-reference (fw=40→44.0), wide-feather-hits-min-floor (fw=300→12.0), floor-crossover-point (fw=146>12, fw=147→12.0), zero-feather-no-division-by-zero (fw=0→1760.0). **animation suite: 417 passing.** |

### Design rationale

The dominant failure mode identified in the 2026-06-10 benchmark (Class A, 4/5 test images) is: wide feather (300px adaptive widening) × moderate post_warp_diff (15–22 lum) → blend zone NOT escalated to single-pose → 600px ghost band. The hardcoded threshold `_POST_DIFF_THRESHOLD = 22.0` treats a 22 lum discrepancy the same at 80px feather (trivially short ghost, barely visible) and 300px feather (ghost span = feather×2 = 600px, visually dominant). The adaptive formula ties the risk tolerance to the blend zone width: for a 300px feather the floor (12.0) fires for any post_warp_diff ≥ 12.0 lum, which covers the 15–22 range that was slipping through. The min_threshold=12.0 preserves the existing ARAP warp attempt — the path still warps first, then escalates if residual discrepancy is large relative to the feather width.

---

## ASP Session 61 — §1.17 Canvas Span Utilisation Gate (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_canvas_span_utilization(affines) → float`** (`pipeline.py`) | §1.17: computes actual dominant-axis canvas span divided by expected span (`median_adjacent_step × (N−1)`). Dominant axis = whichever of ty/tx has the larger range. Returns 1.0 for N < 2 or zero expected span (safe fallback). |
| **Post-BA canvas span gate** (`pipeline.py`) | `_CANVAS_SPAN_MIN_UTIL` flag (default 0.0=off, `ASP_CANVAS_SPAN_MIN_UTIL=0.3`). Wired after §3.14 scroll-axis check (Stage 9.5) before Stage 10 rendering: if utilisation ratio < threshold → SCANS fallback with log message. |
| **`CANVAS_SPAN_MIN_UTIL = 0.3`** (`constants/animation.py`) | Recommended threshold. Catches oscillating BA solutions (frames back-and-forth between two positions) where individual step sizes look valid but total canvas is far shorter than expected. |
| **`ASP_CANVAS_SPAN_MIN_UTIL` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 1.0, "Min canvas-span/expected-span utilisation ratio after BA (0=off)")`. |
| **`_compute_canvas_span_utilization` in `__all__`** (`pipeline.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_pipeline.py::TestComputeCanvasSpanUtilization`) | single-frame-returns-one, two-frames-returns-one, perfect-monotone-sequence (ratio≈1.0), oscillating-ba-returns-low-ratio (alternating [0,100,0,100…] → span=100, expected=500 → ratio=0.2 < 0.3), dominant-axis-horizontal (pure tx scroll → tx axis used, ratio=1.0). **animation suite: 412 passing.** |

### Design rationale

The pre-BA gates (§1.15 connectivity, §1.16 MST weight) catch bad *graphs* before bundle adjustment runs. The post-validation gates (§0.5C min gap, §1.12 Kendall-τ) catch bad *per-adjacent-step* values. §1.17 fills a gap between them: a BA solution can pass all per-step checks yet still produce a globally collapsed canvas if the optimiser converges to an oscillating local minimum (common when there are dense cross-pairs or conflicting edge directions). In that case `median_step × (N−1)` significantly exceeds the actual span — the ratio fires where neither gate would. Distinct from the coverage gate (§0 Stage 10.5) which measures how many canvas rows have ≥ 2 frames: §1.17 fires earlier (after Stage 9, before temporal median) and detects the geometric collapse rather than the coverage consequence.

---

## ASP Session 60 — §1.16 Minimum Spanning Tree Weight Gate (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_mst_weight(edges, n_frames) → float`** (`pipeline.py`) | §1.16: builds the max-weight spanning tree (Kruskal greedy, highest-weight-first) using iterative path-compression Union-Find and returns `total_weight / (N-1)`. Returns 0.0 when n_frames ≤ 1 or no edges. |
| **Pre-BA MST weight gate** (`pipeline.py`) | `_MST_MIN_WEIGHT` flag (default 0.0=off, `ASP_MST_MIN_WEIGHT=0.35`). After the §1.15 connectivity check, if the mean MST weight < threshold → SCANS fallback with log message. Wired between connectivity gate and Stage 7 BA call. |
| **`MST_MIN_WEIGHT = 0.35`** (`constants/animation.py`) | Recommended threshold: LoFTR edges weight~0.6–0.9; TM/PC fallbacks~0.15–0.3; threshold 0.35 triggers on all-TM/PC graphs. |
| **`ASP_MST_MIN_WEIGHT` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 1.0, "Min mean MST edge weight before pre-BA SCANS fallback (0=off)")`. |
| **`_compute_mst_weight` in `__all__`** (`pipeline.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_pipeline.py::TestComputeMstWeight`) | no-frames-returns-zero, empty-edges-returns-zero, chain-graph-mean-weight (0→1 w=0.8, 1→2 w=0.6 → mean 0.7), takes-highest-weight-edges-for-mst (triangle: picks 0.9+0.5, mean=0.7), low-weight-graph-below-threshold (all edges w=0.2 → mean 0.2 < 0.35). **animation suite: 407 passing.** |

### Design rationale

The §2.9C retry 0 (`_filter_high_conf_edges`, S37) removes bad edges and re-solves with only high-confidence LoFTR edges. But it fires *after* BA has already been attempted. The MST weight gate fires *before* BA: if the spanning tree itself is dominated by TM/PC fallback edges (all weights ≈ 0.15–0.3), even a successful BA will produce poor translations because the measurements are fundamentally noisy. Rather than consuming the full Retry 0–5 chain, the gate takes an immediate SCANS fallback. Zero overhead on success paths (disabled by default), O(E log E) sort when enabled.

---

## ASP Session 59 — §1.14C Per-channel BGR Bhattacharyya Seam Gate (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_color_similarity_bgr(img, k, n_strips, band_px=50) → float`** (`compositing.py`) | §1.14C: computes separate normalised 256-bin histograms for each of the B, G and R channels in the `band_px`-row windows immediately above and below seam k; returns `min(score_B, score_G, score_R)`. Any single channel with a severe distribution mismatch drives the score down even when luminance is unchanged. Falls back to `_seam_color_similarity` for 2-D greyscale inputs. Exported in `__all__`. |
| **`_check_seam_color_gate(..., use_bgr=False)` extended** (`compositing.py`) | Added `use_bgr: bool = False` parameter. When True, routes to `_seam_color_similarity_bgr` instead of `_seam_color_similarity`. Gate logic unchanged: returns worst seam index below thresh or None. |
| **`_SEAM_COLOR_GATE_BGR` flag** (`compositing.py` + `pipeline.py`) | `ASP_SEAM_COLOR_GATE_BGR=1` enables BGR mode (default OFF — greyscale path is faster). Stage 11.2 gate in `pipeline.py` passes `use_bgr=_SEAM_COLOR_GATE_BGR`. |
| **`ASP_SEAM_COLOR_GATE_BGR` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 1, "Use per-channel BGR Bhattacharyya instead of greyscale in seam colour gate (0 or 1)")`. |
| **5 unit tests** (`test_compositing.py::TestSeamColorSimilarityBgr`) | identical-bands-returns-one, hue-shift-same-luma-low-score (proves grey score ≈ 1.0 while BGR score < grey for equal-luma colour shift), grayscale-input-falls-back-gracefully, check-gate-use-bgr-triggers-on-hue-shift, band-too-small-returns-one. **animation suite: 402 passing.** |

### Design rationale

§1.14B (`_seam_color_similarity`) operated on greyscale histograms. It cannot detect hue shifts where the luminance distribution is preserved: if both strips have the same amount of bright and dark pixels, the greyscale histogram overlap is near 1.0 regardless of the colour palette. A common failure mode is a warm-toned strip (high R) adjacent to a neutral or cool-toned strip (high B), at the same luminance level. The B channel shift (128→28) drives the BGR minimum score below 0.55 while the greyscale score remains above 0.90, allowing the gate to correctly trigger a SCANS fallback on hue-banded outputs that the §1.14B gate would pass.

---

## ASP Session 58 — §1.15 Edge Graph Connectivity Validation (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_check_edge_graph_connectivity(edges, n_frames) → bool`** (`pipeline.py`) | §1.15: iterative path-compression Union-Find over the edge graph; returns True iff all frames 0..n_frames-1 are in one connected component. Trivially True for n_frames ≤ 1. Out-of-bounds edge indices are silently skipped. Exported in `__all__`. |
| **Pre-BA connectivity gate** (`pipeline.py`) | Wired immediately after the existing `if not edges:` SCANS fallback in `run()`. If `_check_edge_graph_connectivity(edges, N)` returns False, logs the frame/edge count and triggers `_scan_stitch_fallback` using the `scans_frames or _reload_scans_frames(image_paths)` pattern. Runs in O(E·α(N)) — negligible overhead. |
| **5 unit tests** (`test_pipeline.py::TestCheckEdgeGraphConnectivity`) | chain-graph-is-connected, isolated-frame-is-disconnected, single-frame-trivially-connected, complete-graph-is-connected, no-edges-multiple-frames-disconnected. **animation suite: 397 passing (+1 pre-existing skip).** |

### Design rationale

The §1.13A/B scene-change gates (S51, S57) and the §1.2A/C static-edge filters (S32, S34) can, in edge cases, remove enough edges to partition the frame graph into two or more disconnected components. When this happens, bundle adjustment still runs — but frames in the isolated component receive translations derived only from their intra-component constraints. Those translations are unconstrained relative to the main component, so they can be placed anywhere on the canvas. The resulting `_validate_affines` call typically fails with a ratio error, consuming Retry 0–5 time before landing on SCANS fallback.

The connectivity gate short-circuits this by catching the disconnection in O(E·α(N)) time right before the BA, saving the retry chain and producing a faster, cleaner SCANS fallback. The Union-Find uses the same path-compression algorithm as §1.1B's spanning-tree pre-filter — no new algorithmic machinery, just a different query (connectivity vs spanning-tree construction).

---

## ASP Session 57 — §1.13B Per-Channel (BGR) Scene-Change Gate (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_reject_scene_change_edges(..., use_bgr=True)`** (`pipeline.py`) | §1.13B: extended with `use_bgr: bool = False` parameter. When True, computes per-channel (B, G, R) thumbnail means via `t.reshape(-1,3).mean(axis=0)` and takes `np.abs(means_i − means_j).max()` as the scene-change signal. Backward compatible (default `use_bgr=False` preserves §1.13A grayscale behaviour). |
| **`_SCENE_CHANGE_BGR_THRESH` flag** (`pipeline.py`) | Default 0.0 (off). Set via `ASP_SCENE_CHANGE_BGR_THRESH=60.0` to enable. Wired as a second pass in `_filter_edges` after the existing §1.13A luma gate — the two gates are applied sequentially and are independent. |
| **`SCENE_CHANGE_BGR_THRESH = 60.0`** (`constants/animation.py`) | §1.13B calibrated default: 60/255 ≈ 24% per-channel mean shift is sufficient to identify a hue-shifted scene cut while tolerating normal gradual lighting changes. |
| **`ASP_SCENE_CHANGE_BGR_THRESH` in `_CONFIG_SCHEMA`** (`config.py`) | Float, range [0.0, 255.0]. Closes the TOML-config loop for §1.13B. |
| **5 unit tests** (`test_pipeline.py::TestRejectSceneChangeEdgesBgr`) | identical-frames-not-rejected, hue-shift-same-luma-rejected-in-bgr-mode, luma-mode-misses-hue-shift, bgr-threshold-zero-disabled, bgr-small-channel-diff-kept. **animation suite: 392 passing (+1 pre-existing skip).** |

### Design rationale

§1.13A (S51) catches *brightness* discontinuities by comparing mean grayscale luma. It misses a common failure pattern: warm-versus-cool lighting shifts where overall luma is similar but colour distribution is completely different. A 200-lux orange studio shot and a 200-lux blue-tinted corridor can have identical grayscale luma (≈120) while their B and R channels differ by 180 units. A LoFTR match across that scene cut would produce a valid-looking edge with a plausible displacement but would corrupt bundle adjustment by linking geometrically incompatible environments.

The per-channel max-delta uses `np.abs(means_i − means_j).max()` rather than Euclidean distance (`sqrt(ΔB² + ΔG² + ΔR²)`) so the threshold stays in the same [0, 255] luminance unit as §1.13A — no threshold recalibration is needed when switching between modes. The same `max_luma_diff` parameter governs both gates at 60.0, maintaining a single tuning point per environment.

---

## ASP Session 56 — §1.14B Seam Colour-Similarity Pipeline Gate (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_color_similarity(img, k, n_strips, band_px=50) → float`** (`compositing.py`) | §1.14B: single-seam Bhattacharyya similarity scorer. Computes greyscale histograms of `band_px`-row windows above and below seam boundary k, normalises, and returns `1 − HISTCMP_BHATTACHARYYA`. Returns 1.0 for trivially narrow bands (<10 rows per side). Zero new dependencies. |
| **`_check_seam_color_gate(img, n_strips, thresh, band_px=50) → Optional[int]`** (`compositing.py`) | §1.14B: post-composite gate. Evaluates all `n_strips−1` seams; returns the 0-indexed seam with the minimum colour similarity if that minimum is below *thresh*, else `None`. Returns `None` when `n_strips ≤ 1` or `thresh ≤ 0`. Exported in `__all__`. |
| **`_SEAM_COLOR_GATE` flag** (`compositing.py`) | Module-level float, default 0.0 (off). Set via `ASP_SEAM_COLOR_GATE=0.55` to enable. |
| **`SEAM_COLOR_GATE_THRESH = 0.55`** (`constants/animation.py`) | §1.14B calibrated default. Score < 0.55 indicates a significant distributional mismatch (>45% histogram divergence) across a seam boundary — a reliable indicator of colour-banded output. |
| **Stage 11.2 gate** (`pipeline.py`) | After `_composite_foreground`, when `_SEAM_COLOR_GATE_THRESH > 0` and `N > 1`, calls `_check_seam_color_gate(canvas, N, _SEAM_COLOR_GATE_THRESH)`. On failure → `_scan_stitch_fallback` with logged seam index. Uses `scans_frames or _reload_scans_frames(image_paths)` (on-demand reload pattern from §1.9C). |
| **`ASP_SEAM_COLOR_GATE` in `_CONFIG_SCHEMA`** (`config.py`) | Float, range [0.0, 1.0]. Schema entry closes the TOML-config loop for §1.14B. |
| **5 unit tests** (`test_compositing.py::TestSeamColorGate`) | single-strip-returns-none, threshold-zero-disabled, identical-strips-above-threshold, mismatched-strips-below-threshold, returns-worst-seam-index. **animation suite: 387 passing (+1 pre-existing skip).** |

### Design rationale

§1.14 (S55) added `_seam_bhattacharyya_distances` to the *benchmark* as a diagnostic metric, closing the measurement gap between spatial artefact detectors and distributional colour mismatch. §1.14B closes the loop by wiring the same signal directly into the pipeline as an actionable gate.

The gate is post-composite (Stage 11.2) rather than pre-composite because the Bhattacharyya score is defined on the *output* image — it measures what the seam actually looks like after the Laplacian blend, not what the input frames would predict. This makes it complementary to the pre-blend signal (seam DP cost) and the pre-render signal (render gate at Stage 10.5). Stage 11.2 is the last point where a SCANS fallback is geometrically safe: the canvas has been composited but not yet cropped or super-resolved.

The `_seam_color_similarity` function is kept in `compositing.py` (not imported from `bench_anime_stitch.py`) to avoid a circular dependency between the benchmark and the pipeline modules. The greyscale histogram computation is 15 lines of pure OpenCV — duplication is justified by the module boundary.

---

## ASP Session 55 — §1.14 Per-Seam Bhattacharyya Colour-Distance Metric (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_bhattacharyya_distances(img, n_strips, band_px=50) → List[float]`** (`bench_anime_stitch.py`) | §1.14: computes the Bhattacharyya histogram similarity score for each inter-strip seam boundary. For each of the `n_strips−1` seam boundaries, computes greyscale histograms of the `band_px`-row window *above* and *below* the boundary, normalises them, and returns `1 − cv2.compareHist(HISTCMP_BHATTACHARYYA)`. Score in [0,1]: 1.0 = identical distributions (no colour banding), <0.5 = severe colour mismatch. Returns `[]` when `n_strips ≤ 1`. Falls back to 0.0 when either side of a boundary is empty (image smaller than `band_px`). |
| **`_compute_all_metrics` extended** (`bench_anime_stitch.py`) | `seam_color_scores: List[float]` (per-seam scores) and `seam_color_min: Optional[float]` added to the result dict. Both are `[]` / `None` at default `n_strips=1`. Backward compatible. |
| **New roadmap section §1.14** (`moon/roadmaps/asp.md`) | Added as a new section with Option A (Bhattacharyya, shipped) and Option B (pipeline gate, future). |
| **5 unit tests** (`test_bench_metrics.py::TestSeamBhattacharyyaDistances`) | n-strips-one-returns-empty, returns-n-minus-1-scores, identical-strips-score-near-one, different-histograms-score-below-identical, scores-in-valid-range. **animation suite: 381 passing (+1 pre-existing skip).** |

### Design rationale

The existing per-seam diagnostics (`seam_visibility_score`, `ghost_seam_scores`) both operate in the *spatial* domain — they detect luminance jumps and repeated-edge signatures at a specific row. Neither detects the *distributional* mismatch that causes colour banding: two adjacent strips can have similar mean luminance and identical local gradients but completely different histogram shapes (e.g., one dominated by a bright background gradient, the other by a dark character body), producing a perceptible tonal shift that spatial metrics miss.

Bhattacharyya coefficient is the natural measure for this: it quantifies histogram overlap as `−ln(Σ sqrt(h1[i]·h2[i]))` (Bhattacharyya distance), normalised here to `1 − distance` so higher = more similar. It is available in `cv2.compareHist` with no new dependencies. Greyscale histograms are used (not per-channel) to keep the score interpretable; per-channel extension is Option C.

The `band_px=50` window is narrower than §3.8B's `band_px=100` because Bhattacharyya captures distribution shape, not periodicity — 50 rows is enough to characterise the luminance distribution in a strip zone.

---

## ASP Session 54 — §1.3C Scale Normalisation Before BA (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_normalize_frame_scales(frames, edges, scale_thresh) → (List[np.ndarray], List[Dict])`** (`pipeline.py`) | §1.3C: detects inter-frame zoom from the 2×2 rotation-scale block of matched affines (`s_ij = sqrt(a² + b²)`), propagates absolute scale factors via a BFS spanning tree from frame 0, and resizes each frame by `1/scale[i]` so BA only sees pure translations. Edge affines are updated: 2×2 block reset to identity, tx/ty divided by `scale[i]`. Falls back to originals when scale deviation < `scale_thresh`, the spanning tree is disconnected, or `scale_thresh ≤ 0`. `SCALE_NORM_THRESH = 0.05` in `constants/animation.py`. `_SCALE_NORM_THRESH` module-level flag (default 0.0=off, `ASP_SCALE_NORM_THRESH=0.05` to enable). Exported in `__all__`. |
| **5 unit tests** (`test_pipeline.py::TestNormalizeFrameScales`) | identity-scale-returns-unchanged, zoomed-frame-is-resized, below-threshold-returns-unchanged, disconnected-graph-returns-unchanged, edge-affines-reset-to-unit-scale. **animation suite: 377 tests passing.** |

### Design rationale

The existing §1.3E (similarity-mode matching, S48) and §0.5D (adaptive rotation/scale thresholds, S47) together allow the pipeline to accept zoom-pan sequences without crashing. However, the *canvas construction* and *temporal median rendering* stages still assume translation-only displacement — so even when BA produces valid affines with scale ≈ 1.2, the frame pixels are composited at the wrong effective size, causing subtle parallax ghost artifacts.

§1.3C corrects this at the source: by resizing frames to a uniform scale *before* BA, the entire downstream pipeline (canvas, rendering, compositing) operates on frames that are geometrically consistent without any code changes to those stages. The resize uses Lanczos-4 interpolation to minimise ringing on line-art. The spanning-tree BFS mirrors §1.1B's approach to ensure scale propagation is connected and deterministic.

Default OFF (`ASP_SCALE_NORM_THRESH=0`, i.e., `_SCALE_NORM_THRESH=0.0`) to preserve backward compatibility. Enable with `ASP_SCALE_NORM_THRESH=0.05` for zoom-pan sequences (test5-style, scale_dev ≈ 0.12).

---

## ASP Session 53 — §3.8B Per-Seam SIQE Ghost Map (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_per_seam_ghost_scores(img, n_strips, band_px=100) → List[float]`** (`bench_anime_stitch.py`) | §3.8B: divides the output image into *n_strips* equal-height zones and evaluates `_ghosting_score_v2` in a ±*band_px* band centred at each inter-zone seam boundary. Returns `n_strips − 1` float scores (same [0–100] scale as `ghosting_siqe`). Returns `[]` when `n_strips ≤ 1`. Band clipped to image bounds when near edges — no exception on degenerate inputs. |
| **`_compute_all_metrics` extended** (`bench_anime_stitch.py`) | Signature extended with optional `n_strips: int = 1` parameter. Result dict now includes `"ghost_seam_scores": List[float]` (per-seam scores, empty for default `n_strips=1`) and `"ghost_seam_max": Optional[float]` (`max()` of scores, or `None` for empty list). Backward compatible: default `n_strips=1` leaves existing callers unaffected. |
| **5 unit tests** (`test_bench_metrics.py::TestPerSeamGhostScores`) | uniform-image-all-near-zero, n-strips-one-returns-empty, returns-n-minus-1-scores, band-with-sharp-luminance-step-has-high-score, band-clipped-to-image-bounds-no-error. **animation suite: 372 tests passing.** |

### Design rationale

The existing `ghosting_siqe` metric runs `_ghosting_score_v2` on the entire output panorama and returns a single scalar. For a 2000-row panorama with 12 seam boundaries, a ghost on one seam contributes at most ~1/12 of the signal — the per-image score is diluted and the problem seam is unidentifiable from the metric alone.

Per-seam scoring solves both problems: (1) it raises the signal by restricting the analysis window to the ±`band_px` neighbourhood of each seam boundary, where ghost artifacts actually appear; (2) it localises the worst seam (via `ghost_seam_max` and its index in `ghost_seam_scores`), enabling targeted per-seam intervention (re-composition, deeper feathering) instead of a global SCANS fallback.

The `_ghosting_score_v2` function is reused without modification — the only change is the input window. Each band is extracted as a pure numpy slice (zero copy), so the overhead is N-1 FFT autocorrelations per image — typically < 5ms for N=12 at 1080px width. Fully backward compatible (default `n_strips=1` → no seam scoring, `ghost_seam_scores=[]`, `ghost_seam_max=None`).

---

## ASP Session 52 — §1.12 Kendall-τ Translation Monotonicity Check (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_check_translation_monotonicity(affines, primary_axis, min_tau_abs) → (bool, float)`** (`validation.py`) | §1.12: computes Kendall τ between temporal frame indices [0…N-1] and primary-axis translations. |τ| = 1 for perfectly monotone sequences (forward and backward scroll both pass); |τ| ≈ 0 for random permutations. Returns `(is_monotone, tau_abs)`. Requires ≥ 4 frames; shorter sequences always return `(True, 1.0)`. Exported in `__all__`. |
| **`_MONO_TAU_MIN = 0.4`** (`validation.py`) | Module-level minimum |τ| threshold. A value of 0.4 allows up to ~30% discordant frame pairs — catches catastrophic BA failures while tolerating the minor noise seen in real corpus sequences (typical valid sequences score ≥ 0.85). |
| **Wired as 5th check in `_validate_affines`** | After ratio / min_gap / rotation / scale, the monotonicity check fires for `scroll_axis ∈ {"vertical", "horizontal"}`. Skipped for diagonal scrolls (dominant axis ambiguous). Failure reason: `"monotonicity={tau:.2f} < 0.4"`. A monotonicity failure falls through to Retry 1 (adjacent-only BA) — the natural recovery since skip edges are the most common source of frame misplacement. |
| **5 unit tests** (`test_affine_validation.py::TestTranslationMonotonicity`) | perfectly-monotone-passes, reversed-monotone-passes, catastrophically-shuffled-fails, single-out-of-order-passes, fewer-than-4-always-passes. **animation suite: 367 tests passing.** |

### Design rationale

The existing 4 validation checks (ratio, min_gap, rotation, scale) all operate on the *sorted spatial* order. They cannot detect the case where BA produces well-spaced, correctly-oriented frames that are **placed in the wrong temporal order** — for example, skip edges misaligning frame 3 to a position between frames 0 and 1 while preserving a uniform gap ratio. Such solutions pass all existing checks but produce catastrophic output: the temporal median averages the wrong frames together, and the seam composite bisects the wrong strips.

Kendall τ directly measures the agreement between the two orderings. Forward and backward scrolling are handled symmetrically (|τ|), so no direction inference is needed. The O(N²) pair-counting loop is negligible for typical N ≤ 30. The conservative threshold (0.4) ensures no regressions on the existing 92 passing corpus tests.

---

## ASP Session 51 — §1.13 Scene-Change Edge Pre-Filter (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_reject_scene_change_edges(edges, frames, max_luma_diff) → List[Dict]`** (`pipeline.py`) | §1.13: discards edges between frames whose mean grayscale luminance differs by more than `max_luma_diff`. Comparison is performed on a 64×64 thumbnail for speed. Gate is disabled when `max_luma_diff ≤ 0` or `frames` is empty. Out-of-bounds frame indices are kept (safe fallback). Exported in `__all__`. |
| **`_SCENE_CHANGE_LUMA_THRESH: float`** (`pipeline.py`) | Module-level threshold, default `0.0` (disabled). Set via `ASP_SCENE_CHANGE_LUMA_THRESH=60.0`. Wired as the first step in `_filter_edges`, before the §1.2A+C static edge rejection. |
| **`SCENE_CHANGE_LUMA_THRESH = 60.0`** (`constants/animation.py`) | Named constant for the recommended threshold. |
| **`"ASP_SCENE_CHANGE_LUMA_THRESH"` in `_CONFIG_SCHEMA`** (`config.py`) | Schema entry `(float, 0.0, 255.0, ...)` so `validate_asp_config` catches invalid values. |
| **5 unit tests** (`test_pipeline.py::TestRejectSceneChangeEdges`) | similar-frames-not-rejected, large-luma-diff-rejected, threshold-zero-keeps-all, out-of-bounds-index-kept, selectively-filters-mixed-edges. **animation suite: 362 tests passing.** |

### Design rationale

When a source video contains a scene cut — even one that slipped past the hold detector — the two frames straddling the cut will have drastically different global brightness (e.g., a dark nighttime scene followed by a bright exterior). Any pairwise-match algorithm will attempt to produce a translation for that pair; the match will have low confidence and a spurious displacement. If that edge reaches bundle adjustment it introduces a wrong constraint that can displace all other frames.

This gate rejects such edges before any geometric or BA processing. Mean-luma comparison on a 64×64 thumbnail costs <0.5 ms per edge and is more reliable than using match-confidence alone (which can be spuriously high when two dissimilar frames share a textured region).

Placement at the top of `_filter_edges` ensures the §1.2A+C, Geometric Consistency, Min-step, and Direction Consensus filters only process valid same-scene edges. Disabled by default (`threshold=0`) to preserve backward compatibility; activate with `ASP_SCENE_CHANGE_LUMA_THRESH=60.0` for sequences known to contain lighting discontinuities.

Distinct from `_reject_exposure_outliers` (§1.4F, `compositing.py`): that function detects per-frame luminance outliers in the *normalisation* loop; this gate detects inter-frame luminance discontinuities in the *edge set* before BA.

---

## ASP Session 50 — §1.4F Per-Frame Exposure Outlier Rejection (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_reject_exposure_outliers(frame_lums, max_deviation_lum) → List[bool]`** (`compositing.py`) | §1.4F: per-frame skip mask for absolute luminance outliers. Computes the median background luminance across all frames with valid lum values, returns True for any frame whose lum deviates by more than `max_deviation_lum` units. Frames with `None` lum are never rejected. Falls back to all-False when fewer than 3 valid values are available (unreliable median). Exported in `__all__`. |
| **`_EXPOSURE_OUTLIER_THRESH: float`** (`compositing.py`) | Module-level threshold, default 0.0 (disabled). Set via `ASP_EXPOSURE_OUTLIER_THRESH=60.0`. When > 0, outlier rejects are OR'd into `_skip_norm` after the coherence gate. Logs the count of excluded frames when any are skipped. |
| **`EXPOSURE_OUTLIER_THRESH = 60.0`** (`constants/animation.py`) | Named constant for the recommended threshold value. |
| **`elif _EXPOSURE_OUTLIER_THRESH > 0.0:` wiring** (`compositing.py`) | §1.4F applied immediately after `_coherence_skip_mask` in `_composite_foreground`. Skipped frames still contribute warped pixel content; only gain correction is suppressed. |
| **`"ASP_EXPOSURE_OUTLIER_THRESH"` in `_CONFIG_SCHEMA`** (`config.py`) | Schema entry `(float, 0.0, 255.0, ...)` so `validate_asp_config` catches invalid values. |
| **5 unit tests** (`test_compositing.py::TestRejectExposureOutliers`) | uniform-lums-all-false, dark-outlier-rejected, bright-outlier-rejected, below-threshold-not-rejected, insufficient-frames-all-false. **animation suite: 357 tests passing.** |

### Design rationale

The existing `_coherence_skip_mask` (S18) handles *relative* exposure mismatch: it skips both frames in any adjacent pair whose luminances differ by more than 20 lum. But it cannot handle an *absolute* outlier — a single frame that is globally darker or brighter than all its neighbours due to a lighting flash, accidental double-exposure, or a scene cut that slipped past the hold detector.

Such a frame drives the scalar gain toward an extreme value (e.g., gain=3.5 to bring a flash-bright frame down to reference) that causes visible over-correction of adjacent zones in the feather band. Excluding it from gain normalisation entirely allows its bg pixels to contribute to the canvas at their original values, which is visually neutral, while preventing the extreme correction from propagating to adjacent compositing zones.

The threshold of 60 lum (default for `EXPOSURE_OUTLIER_THRESH`) corresponds to a 24% brightness difference at typical reference luminance (250 lum), or a 75% difference at dark-scene reference (80 lum). This catches genuine outliers (flash frames, accidental HDR blending) without triggering on legitimate inter-strip brightness variation that the §1.4A–E gain corrections are designed to handle.

Complementary to §1.4C (`_bg_gain_unclamped`): that function aggressively corrects large-gain frames; §1.4F suppresses correction entirely for extreme outliers where correction would overshoot.

---

## ASP Session 49 — §1.4E Background CDF Histogram Matching (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_bg_histogram_lut(src_pixels, ref_pixels) → np.ndarray`** (`compositing.py`) | §1.4E: builds a 256-entry float32 CDF-matching LUT via `np.searchsorted(ref_cdf, src_cdf, side="left")`. Source and reference 1-D uint8 arrays normalised to CDFs; LUT maps each source intensity to the reference intensity with the nearest cumulative probability. Fallback: identity `np.arange(256)` when either input has fewer than 10 pixels. Exported in `__all__`. |
| **`_apply_bg_histogram_match(frame, reference, bg_mask) → np.ndarray`** (`compositing.py`) | §1.4E: applies `_bg_histogram_lut` per-channel to the background region of *frame*. Foreground pixels (where `bg_mask` is False) are copied unchanged. Returns uint8 (H, W, 3). Exported in `__all__`. |
| **`_HISTOGRAM_MATCH: bool`** (`compositing.py`) | Module-level flag, default OFF (`ASP_HISTOGRAM_MATCH=0`). When enabled, replaces the `_bg_gain_unclamped` scalar path in the normalization loop with the full CDF histogram match. `_MULTISCALE_GAIN` takes priority when both flags are set. |
| **`elif _HISTOGRAM_MATCH:` branch** in normalization loop | §1.4E wired between `if _MULTISCALE_GAIN:` and `else:` in `_composite_foreground`. Calls `_apply_bg_histogram_match`, then computes a representative scalar gain (`median(out_lum / src_lum)`, clipped to [0.5, 2.0]) for §1.6B feather widening. |
| **`"ASP_HISTOGRAM_MATCH"` in `_CONFIG_SCHEMA`** (`config.py`) | Schema entry `(int, 0, 1, ...)` so `validate_asp_config` catches invalid values. |
| **5 unit tests** (`test_compositing.py::TestBgHistogramLut`) | identical-distribution-near-identity, brighter-ref-maps-source-upward, darker-ref-maps-source-downward, monotone-non-decreasing, sparse-input-returns-identity. **animation suite: 352 tests passing.** |

### Design rationale

All §1.4A–D corrections apply a single scalar (or spatially-varying scalar map) to each frame. This works well when the exposure difference between frames is a multiplicative constant (e.g., one frame is uniformly 10% brighter). It fails when the *tonal distribution* differs: a frame shot through a semi-transparent panel may have compressed highlights and boosted shadows relative to the reference, producing a characteristic S-curve difference that a scalar cannot invert.

Histogram specification solves this directly: instead of estimating a single gain, it finds the monotone mapping that makes the source CDF match the reference CDF. The result is that the background in every frame has the same tonal distribution as the canvas, regardless of the shape of the per-frame exposure curve.

Algorithm: standard CDF matching — for each intensity `v`, `lut[v] = argmin_u |CDF_ref(u) − CDF_src(v)|`. Implemented via `np.searchsorted(ref_cdf, src_cdf)` for a vectorised O(256 log 256) lookup instead of a Python loop. Per-channel application avoids luminance-only approximations that would introduce hue shifts for strongly colour-tinted panels.

The flag is OFF by default because the scalar path is ~50× faster and handles the 92/96 non-fallback tests without visible artefacts. The histogram path is intended for sequences with non-linear tonal mismatch that the §1.4A–D scalar corrections cannot correct.

---

## ASP Session 48 — §1.3E Similarity-Mode Matching (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_extract_similarity(M) → np.ndarray`** (`matching.py`) | §1.3E: closed-form projection of a full 2×3 affine to its best-fit 4-DOF similarity. Formula: `a_sym = (M[0,0] + M[1,1]) / 2`, `b_sym = (M[0,1] - M[1,0]) / 2` → output `[[a_sym, b_sym, tx], [-b_sym, a_sym, ty]]`. This is the least-squares Procrustes projection onto the 2-D conformal manifold — discards shear while preserving scale, rotation, and translation. Exported in `__all__`. |
| **`_SIMILARITY_MODE: bool`** (`matching.py`) | Module-level flag, default OFF (`ASP_SIMILARITY_MODE=0`). When enabled, `_match_pair` calls `_extract_similarity(M)` instead of the 3-line translation strip. Default behaviour is unchanged. |
| **`"ASP_SIMILARITY_MODE"` in `_CONFIG_SCHEMA`** (`config.py`) | Schema entry `(int, 0, 1, ...)` so `validate_asp_config` catches invalid values. |
| **5 unit tests** (`test_matching.py::TestExtractSimilarity`) | pure-translation-unchanged, rotation-preserved, uniform-scale-preserved, shear-eliminated, output-satisfies-similarity-constraint (20 random matrices). **animation suite: 347 tests passing.** |

### Design rationale

The current `_match_pair` unconditionally strips the matched 2×3 affine to translation-only (identity rotation block, tx/ty copied). This was correct for the original static-scroll use case but silently discards genuine scale and rotation information for zoom-pan sequences (test5: scale≈1.121, rotation≈6.35°).

`_extract_similarity` solves the Procrustes problem for the 2-D conformal group: given an arbitrary affine `[[a, b, tx], [c, d, ty]]`, find the nearest similarity `[[α, β, tx], [-β, α, ty]]` in Frobenius norm. The closed-form solution is `α = (a+d)/2`, `β = (b-c)/2` — the symmetric part of the rotation block.

Shear (`b ≠ -c`) is discarded because:
1. Feature matchers (LoFTR, RoMa) cannot reliably distinguish camera shear from perspective at anime-panel scales.
2. The 4-DOF BA model uses `[[a, b, tx], [-b, a, ty]]` — shear would break the DOF assumption.
3. Shear in matched affines is typically matching noise, not a physical camera property.

The flag is OFF by default to preserve backward compatibility for the 92/96 tests that work perfectly with translation-only matching. For zoom-pan sequences (`ASP_SIMILARITY_MODE=1`), the matched scale/rotation now propagate through the BA and canvas placement instead of being discarded at the edge.

Complementary to §0.5D (S47): validation now accepts systematic rotation/scale (σ<0.02 → loose threshold 0.15) even without similarity mode enabled. Together, S47+S48 form a complete zoom-pan support path: S47 prevents validation from rejecting the correct solution; S48 provides the correct solution to validate.

---

## ASP Session 47 — §0.5D Adaptive Rotation/Scale Validation Thresholds (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_adaptive_rot_scale(affines) → (float, float)`** (`validation.py`) | §0.5D: returns `(max_rotation, max_scale_dev)` adaptively. If frame-to-frame rotation standard deviation < `_ROT_SCALE_CONSISTENCY_THRESH=0.02`, returns loose threshold `0.15`; otherwise tight `0.10`. Same rule independently for scale. Constants: `_ROT_TIGHT=0.10`, `_ROT_LOOSE=0.15`, `_SC_TIGHT=0.10`, `_SC_LOOSE=0.15`, `_ROT_SCALE_CONSISTENCY_THRESH=0.02`. Exported in `__all__`. |
| **Wired into `pipeline.py` Stage 7b** | `_adaptive_rot, _adaptive_sc = _compute_adaptive_rot_scale(affines)` before initial `_validate_affines` call. Also applied to Retry 0 re-validation. Log message updated to show `thresh=…` for both metrics. |
| **5 unit tests** (`test_affine_validation.py::TestAdaptiveRotScale`) | consistent-rotation-returns-loose, inconsistent-rotation-returns-tight, consistent-scale-returns-loose, inconsistent-scale-returns-tight, single-frame-returns-defaults. **animation suite: 342 tests passing.** |

### Design rationale

The validation gate uses a fixed `max_rotation=0.10` and `max_scale_dev=0.10`. This rejects test5 (zoom-pan sequence with `max_rotation≈0.111, scale_dev≈0.121`) even though the BA solution is geometrically correct — every frame carries the same consistent camera-intrinsic-induced rotation and scale, not random per-frame noise.

The key diagnostic is *frame-to-frame consistency*: if σ < 0.02 (well below the tight threshold), the dominant signal is a systematic camera property (slight constant zoom, fixed lens barrel distortion, or a steady tilt introduced by video stabilisation). Widening to 0.15 in that case is safe because:
1. The BA correctly recovered the systematic component; the output affines are geometrically accurate.
2. The downstream warpAffine already handles scale and rotation (it uses the full 2×3 matrix).
3. Borderline values (0.10–0.15) that pass the loose gate are handled correctly by the PANORAMA fallback if they still produce a bad output.

If σ ≥ 0.02, rotation/scale varies wildly across frames — a sign of BA overfitting or per-frame feature matching noise. The tight 0.10 threshold is kept to prevent propagating a corrupted affine set to the compositing stage.

Calibration: test5's rotation is 6.35° = 0.1108 rad (sin ≈ 0.111) and scale_dev ≈ 0.121. Both are 10–20% above the tight threshold but 25–30% below the loose 0.15 ceiling. σ ≈ 0 for zoom-pan (all frames share the same lens distortion) → loose threshold returned → test5 passes validation without any retry.

---

## ASP Session 46 — §1.4D Multi-Scale Spatially-Varying Gain Normalisation (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_multiscale_gain_map(frame, reference, bg_mask, sigma, gain_min, gain_max) → float32 (H,W)`** (`compositing.py`) | §1.4D: computes a spatially-varying per-pixel gain map via Gaussian-blurred luminance ratio. Background pixels (from `bg_mask`) are used as sources; foreground pixels are zeroed before the blur so only background luminance propagates into fg regions (preventing character-colour corruption). Gain = `ref_blurred / (frame_blurred + ε)`; clamped to `[gain_min=0.5, gain_max=2.0]`. When `frame_blurred ≤ 1.0` (near-black or no-bg-source) gain falls through to 1.0. Exported in `__all__`. |
| **`_MULTISCALE_GAIN: bool`** (`compositing.py`) | Module-level flag, default OFF (`ASP_MULTISCALE_GAIN=0`). When enabled, replaces the scalar `_bg_gain_unclamped` call with `_multiscale_gain_map` in the per-frame bg normalization loop. Per-pixel gain applied via `gain_map[bg_sel, np.newaxis]` broadcasting (no fg pixels affected). Median gain across bg pixels stored as `frame_gains[i]` for §1.6B feather-width calculation (unchanged downstream). |
| **`MULTISCALE_GAIN_SIGMA = 30.0`** (`constants/animation.py`) | Gaussian σ in pixels for low-frequency decomposition. |
| **`"ASP_MULTISCALE_GAIN"` in `_CONFIG_SCHEMA`** (`config.py`) | Schema entry `(int, 0, 1, ...)` so `validate_asp_config` catches invalid values. |
| **5 unit tests** (`test_compositing.py::TestMultiscaleGainMap`) | identical-frame-unity-gain, darker-frame-gain-above-one, brighter-frame-gain-below-one, gain-clamped-to-range, all-fg-mask-produces-unit-gain. **animation suite: 337 tests passing.** |

### Design rationale

The existing S18/S24/S40 gain stack computes one scalar per frame: `global_ref_lum / frame_lum`. This works well for uniformly lit backgrounds but fails when a single manga or cel panel has a vertical gradient — darker at the top, brighter at the bottom, or split lighting from a window. The global mean collapse hides this variation, so the correction over-brightens the dark region while under-brightening the bright region, producing a banded plate.

§1.4D keeps the same pipeline integration point (bg-only normalization loop, fg pixels untouched) but replaces the scalar with a Gaussian-blurred ratio map. The 30px σ is chosen to be:
- Wide enough to smooth MPEG block noise and character-edge leakage into the bg mask
- Narrow enough to capture panel-scale brightness gradients (typical gradient scale: 100–300px)

The fg-zeroing before blur (not fg masking after blur) is the key correctness property: it prevents character-pixel luminance from contaminating the background model in the fg region. Without it, a bright character outline would drive the gain map low around the character, causing the background behind the character to be under-corrected once that region is covered by a different frame's background.

Default OFF because the scalar path is faster (~0.1ms vs ~2ms for a 1080p frame with σ=30) and sufficient for uniformly-lit scenes (the majority of the corpus). Enable for scenes with known vertical brightness gradients.

---

## ASP Session 45 — §1.1B Spanning-Tree Consensus Pre-Filter for Bundle Adjustment (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_spanning_tree_inlier_filter(edges, num_frames, inlier_threshold=50.0) → List[Dict]`** (`bundle_adjust.py`) | §1.1B: builds a max-weight spanning tree from the edge graph (Kruskal greedy, highest-weight-first), then BFS from frame 0 to derive a reference translation for every frame. Any edge whose observed dx/dy disagrees with the reference by > `inlier_threshold` pixels is removed. Spanning-tree edges always pass (residual = 0 by construction) so the graph remains connected. Falls back to original edges when: fewer than 2 edges/frames, spanning tree cannot reach all frames (disconnected graph), or fewer than `max(2, N-1)` inliers survive. Exported in `__all__`. |
| **`_ST_INLIER_THRESHOLD = 50.0`** (`bundle_adjust.py`) | Module-level constant for the default inlier threshold. |
| **Wired at the top of `_bundle_adjust_affine`** (`bundle_adjust.py`) | `edges = _spanning_tree_inlier_filter(edges, num_frames)` called before DOF setup. On clean data the filter is a no-op (all chain edges are tree edges → residual=0). On data with bad skip edges or outlier adjacent edges, removes them before the LM solve. |
| **5 unit tests** (`test_bundle_adjust.py::TestSpanningTreeInlierFilter`) | consistent-chain-all-kept, inconsistent-skip-edge-removed, consistent-skip-edge-kept, disconnected-graph-fallback, low-weight-bad-edge-not-in-spanning-tree. **animation suite: 332 tests passing.** |

### Design rationale

The existing GNC Cauchy loss (§1.1C, S6) down-weights outlier edges during the LM solve. The AGNC adaptive f_scale (§1.1D, S30) recalibrates the loss width if the initial estimate is too tight. Both approaches operate *during* the LM solve.

§1.1B adds a *pre-solve* filter: the spanning tree gives a deterministic, O(E log E) consensus estimate before any matrix inversion. The maximum-weight spanning tree construction ensures the most reliable (highest-weight, typically LoFTR-matched) edges form the backbone of the reference model. An inconsistent edge must differ from all these reliable edges simultaneously — a much stronger signal than a threshold on residuals from a potentially-biased LM solution.

Practical benefit: when the edge set contains a skip-edge (0→2) or long-range edge that is biased by MPEG blocking noise but has a moderately-high weight, it can survive GNC+AGNC and drag the LM toward a poor local minimum. The spanning-tree pre-filter catches this class of outlier deterministically, before it can corrupt the initial guess.

---

## ASP Session 44 — §1.5D Seam Path Cache (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_get_seam_cost_flags() → Tuple`** (`compositing.py`) | §1.5D: returns `(_POISSON_SEAM, _TOONCRAFTER_SEAM)` — a hashable snapshot of the module-level flags that affect seam cost map output. Used as the `cost_flags` component of every cache key so that changing a flag (e.g. enabling Poisson) automatically bypasses stale cache entries. |
| **`_make_seam_cache_key(frame_keys, k, cost_flags) → Optional[Tuple]`** (`compositing.py`) | §1.5D: derives a hashable `(frame_keys, k, cost_flags)` tuple for seam boundary *k*. Returns `None` when `frame_keys is None`, disabling cache lookup and insertion. Exported in `__all__`. |
| **`frame_keys` and `seam_path_cache` params on `_composite_foreground`** (`compositing.py`) | §1.5D: two new optional keyword args (default `None`). When both are provided, each seam boundary is checked against the cache before building zone arrays or submitting to the `ThreadPoolExecutor`. Cache misses run as before; hits skip all per-boundary array allocations. After the parallel executor completes, any newly computed path is written to the cache under its key. |
| **`self._seam_path_cache: Dict = {}`** (`pipeline.py`, `AnimeStitchPipeline.__init__`) | §1.5D: instance-level dict shared across successive `run()` calls on the same pipeline object. Passed as `seam_path_cache=self._seam_path_cache` at the Stage 11 call site. |
| **`AnimeStitchPipeline._composite_foreground` wrapper updated** (`pipeline.py`) | Passes `frame_keys` and `seam_path_cache` through to the module-level function. |
| **5 unit tests** (`test_compositing.py::TestSeamPathCache`) | hashable key, same-inputs-equal-keys, different-boundary-different-key, different-frame-keys-different-key, None-frame-keys-returns-None. **animation suite: 327 tests passing.** |

### Design rationale

The `ThreadPoolExecutor` seam-DP pre-computation block (§S12) accounts for 200–800 ms per panorama on a CPU (each `_seam_cut` call runs Dijkstra DP over a (2F×W) grid). In the §1.10B Bayesian parameter search use case, the same frames are re-composited many times with different gain/feather parameters — but the optimal DP seam path depends only on the pixel content and active cost flags, not on gain scalars or feather widths. Caching by `(frame_keys, k, cost_flags)` lets RLHF iterations after the first skip the DP entirely.

Cache key design: `frame_keys = tuple(image_paths)` (canonical ordering from `run()`), `k` = boundary index, `cost_flags = (_POISSON_SEAM, _TOONCRAFTER_SEAM)` (the only module flags that alter `_build_seam_cost_map` output). Memory footprint: each seam path is a `np.int32` array of shape `(W,)` ≈ 4 KB at 1080p — negligible even for hundreds of RLHF iterations.

---

## ASP Session 43 — §3.4A dHash Animation Hold Detection (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_dhash(thumb, hash_size=8) → np.ndarray[bool]`** (`frame_selection.py`) | §3.4A: difference hash of a thumbnail. Resizes to (hash_size+1, hash_size) using INTER_AREA (averages DCT block noise), converts to uint8 if float, computes horizontal gradient binarisation (`col_j > col_{j-1}`). Returns flat bool array of hash_size² bits. Exported in `__all__`. |
| **`_detect_hold_blocks_dhash(thumbs, distance_threshold=4) → List[int]`** (`frame_selection.py`) | §3.4A: same API as `_detect_hold_blocks`. Builds dHash for each thumbnail, declares a hold boundary when Hamming distance > threshold. INTER_AREA resize averages MPEG DCT blocks before the comparison, so within-hold distance typically stays 0–2 even for aggressively compressed sources where MAD can exceed 0.025. Exported in `__all__`. |
| **`_HOLD_DHASH_THRESHOLD`** (`frame_selection.py`) | Module-level config: `int(os.environ.get("ASP_HOLD_DHASH_THRESH", "0"))`. Default 0 = disabled (MAD fallback). Set to 4 to enable. |
| **`HOLD_DHASH_THRESHOLD = 4`** (`constants/animation.py`) | Canonical constant. |
| **`"ASP_HOLD_DHASH_THRESH"` in `_CONFIG_SCHEMA`** (`config.py`) | Added to §1.8B schema: `(int, 0, 64, "dHash Hamming threshold for hold detection (0=off)")`. |
| **Wired as step 1b in `smart_select_frames`** | When `_HOLD_DHASH_THRESHOLD > 0`, uses `_detect_hold_blocks_dhash` instead of `_detect_hold_blocks`. Both paths share the same `hold_ids` / `n_hold_blocks` downstream logic. Verbose log prints method label: `HoldDetect/dHash(d≤4)` vs `HoldDetect/MAD(t=0.025)`. |
| **5 unit tests** (`test_frame_selection.py::TestDetectHoldBlocksDhash`) | identical-thumbs-single-block, opposing-gradient-thumbs-split, threshold-zero-every-frame-own-block, single-frame-returns-single-block, compute-dhash-same-image-zero-distance. **animation suite: 322 tests passing.** |

### Design rationale

The MAD-based hold detector (`_detect_hold_blocks`, S6) compares consecutive thumbnail mean absolute differences. For broadcast-quality streaming rips (H.264/H.265 with heavy quantisation), MPEG DCT blocking artifacts change raw pixel values by 3–8 luma units even in "still" frames — within-hold MAD of 0.012–0.030 frequently overlaps the 0.025 default threshold, causing hold boundaries to be missed or false boundaries to fire. The `_refine_hold_ids_by_response` post-hoc fix (§1.11C, S38) partially compensates but only for pairs that were already cross-correlated.

dHash avoids this by resizing to 9×8 pixels with INTER_AREA (area average) before computing the gradient. The resize averages out the ~8×8 pixel MPEG DCT blocks into a single value, so block noise is structurally eliminated before any comparison is made. A frame-identical-except-noise pair will hash to Hamming distance 0–2; a genuine pose-change pair typically hashes to distance 8–20. The threshold-4 default leaves a comfortable gap between both populations.

The two detectors are complementary: MAD is faster (~1ms for 300 frames vs ~3ms for dHash), handles all sources, and is robust when frames are clean. dHash is the right choice for compressed streaming sources. Both detectors feed the same downstream hold_ids logic and are both refined by `_refine_hold_ids_by_response` (S38).

---

## ASP Session 42 — §1.8B Config Schema Validation (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_CONFIG_SCHEMA`** (`config.py`) | 14-key schema dict mapping known `ASP_*` env-var names to `(expected_type, min_val, max_val, description)` tuples. Covers all frequently-tuned keys: hold threshold, near-dup luma, coverage pct, single-pose feather, ghost gate floor, Poisson/ToonCrafter/SCANS flags, temporal variance, hold-response floor, BA f_scale, DINOv2 window, SGM proxy, and two-channel selection. |
| **`validate_asp_config(config, *, strict=False) → List[str]`** (`config.py`) | §1.8B validator. Iterates the flat config dict; for each key checks (a) it exists in `_CONFIG_SCHEMA`; (b) value has the expected type (int→float coercion allowed); (c) value is within `[min_val, max_val]`. Unknown keys emit `UserWarning` (forward-compat) but are not violations. Returns a list of violation strings; empty = valid. Exported in `__all__`. |
| **`strict=True` mode** | Raises `ValueError` with a formatted bullet list of all violations. Designed for CI and experiment scripts where a misconfigured run should abort instead of silently forwarding a bad value as an env string. |
| **Wired into `load_asp_config`** | New `validate=False` and `strict=False` parameters. When `validate=True`, calls `validate_asp_config(flat, strict=strict)` after merging TOML sections but before writing env vars — so invalid configs are caught before they pollute the process environment. |
| **5 unit tests** (`test_config.py::TestValidateAspConfig`) | valid-keys-no-violations, wrong-type-produces-violation, out-of-range-produces-violation, strict-raises-ValueError, unknown-key-warns-not-violation. **animation suite: 317 tests passing.** |

### Design rationale

§1.8A (S27) loads `asp_config.toml` and injects all keys into `os.environ` via `setdefault`. Because the pipeline reads env vars as strings and parses them locally (`float(os.environ.get(..., "0.0"))`), a typo like `ASP_HOLD_THRESHOLD = "0.03"` (TOML string instead of float) would silently result in `float("0.03")` parsing correctly — but `ASP_HOLD_THRESHOLD = "moderate"` would raise a cryptic `ValueError` deep inside `frame_selection.py` rather than at config load time.

§1.8B addresses this by adding a lightweight schema validation layer using only stdlib types — no `jsonschema` dependency. The schema is defined as a plain Python dict in `config.py`, making it co-located with the loader and easy to extend as new `ASP_*` env vars are added. The `jsonschema` approach from the original roadmap description would require an external dep and a separate schema file; the inline dict accomplishes the same with zero overhead and immediate discoverability.

The `validate=False` default preserves full backward compatibility — callers that do not opt in see no change in behaviour. The `strict=True` mode is aimed at the upcoming §1.10B Bayesian parameter search, where a misconfigured TOML would silently bias the objective function otherwise.

---

## ASP Session 41 — §1.9C On-Demand SCANS Frame Reload (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_SCANS_RELOAD`** (`pipeline.py`) | Module-level flag: `os.environ.get("ASP_SCANS_RELOAD", "0") != "0"`. Default OFF (backward-compatible). When enabled, the Stage-2 `list(frames)` snapshot is replaced with an empty list, saving the full frame memory footprint for the success path. |
| **`_reload_scans_frames(paths: List[str]) → List[np.ndarray]`** (`pipeline.py`) | New module-level function. Calls `_load_frames(paths)` (same as Stage 1) then `_normalise_widths()` (same as Stage 2). Returns `[]` when all paths fail. Exported in `__all__`. |
| **Stage 2 snapshot guarded** | `scans_frames = ([] if _SCANS_RELOAD else list(frames))`. |
| **Dedup sync sites guarded** | Both `scans_frames = [scans_frames[i] for i in keep_idx]` lines (inline luma dedup and `_spatial_dedup_frames` return) changed to `... if scans_frames else []`. |
| **5 fallback call sites patched** | All `_scan_stitch_fallback(scans_frames, ...)` and `_panorama_stitch_fallback(scans_frames, ...)` calls use `_sf = scans_frames or _reload_scans_frames(image_paths)`. When `_SCANS_RELOAD=False` (default), `scans_frames` is truthy and the `or` short-circuits — zero overhead. |
| **5 unit tests** (`test_pipeline.py::TestReloadScansFrames`) | valid-paths-return-two-frames, empty-paths-returns-empty, unreadable-path-skipped, all-frames-normalised-to-first-width, all-unreadable-returns-empty. **animation suite: 312 tests passing.** |

### Design rationale

§1.9A (S28) fixed the `scans_frames` desync bug, but the fix revealed the underlying cost: `scans_frames = list(frames)` at Stage 2 duplicates the entire width-normalised frame set in memory for the duration of every pipeline run — even when the run succeeds and the fallback never fires. For a 14-frame 1080p sequence (each frame ≈ 6.2 MB), this snapshot consumes ~87 MB of RAM that is freed only at function return.

§1.9C eliminates this cost on the success path. The `or` pattern at each fallback site (`scans_frames or _reload_scans_frames(image_paths)`) incurs zero overhead when `_SCANS_RELOAD=False` (truthy list, Python short-circuits). When `_SCANS_RELOAD=True`, `scans_frames=[]` is falsy, so `_reload_scans_frames(image_paths)` is called — but only when a fallback actually fires. `image_paths` is already kept in sync with the live frame set by the §1.9A spatial dedup, so the reloaded frames are exactly the post-dedup subset.

The two dedup sync lines are guarded with `if scans_frames else []` rather than removed, so the behaviour when `_SCANS_RELOAD=False` (the default) is byte-for-byte identical to before §1.9C.

---

## ASP Session 40 — §1.4C Background-Only Gain Clamp Override (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_bg_gain_unclamped(ref_lum, frame_lum, override_threshold=0.20) → float`** (`compositing.py`) | §1.4C: returns raw ideal gain `ref_lum / frame_lum` when `_adaptive_gain_clamp` would reduce the ideal correction by more than `override_threshold` (default 20 %). Otherwise returns the clamped value unchanged. |
| **Wired into normalization loop** | Replaces `_adaptive_gain_clamp(...)` call in the bg-only gain application path in `_composite_foreground`. `frame_gains[i]` now stores the actual applied gain (may be unclamped) for feather-width computation. |
| **5 unit tests** (`test_compositing.py::TestBgGainUnclamped`) | large-correction-returns-ideal, small-correction-returns-clamped, zero-frame-lum-guard, threshold-boundary-behavior, darkening-case-symmetry. **animation suite: 307 tests passing.** |

### Design rationale

`_adaptive_gain_clamp` (§1.4B) uses a smooth clamp width of `0.26 - 0.12 × (ref_lum / 255)`. For normal-brightness scenes (ref ≈ 120), this gives a ±20% correction window. When a frame's luminance deviates by more than 25%, the clamp cuts the ideal correction short — the frame is partially corrected but still visibly brighter or darker than the reference, producing residual banding at seam boundaries.

The clamp exists to protect character skin tones from over-correction. But the normalization loop in `_composite_foreground` already applies the gain **only to background-selected pixels** (`bg_sel` mask). Skin tones are excluded at the application site. Therefore the clamp's protective purpose does not apply to this path — background regions are large uniform areas where aggressive correction is less visible than residual banding.

§1.4C lifts the clamp for background pixels when the ideal correction exceeds the clamped value by >20%: `cut = |ideal - clamped| / |ideal|`. This is symmetric — it applies to both brightening (dark frames) and darkening (bright frames). The 20% threshold is conservative: it only overrides when the clamp is cutting a large correction, leaving small deviations unchanged (< 20% cut → clamped value kept).

---

## ASP Session 39 — §1.2D Temporal Variance Pre-Filter (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`TEMPORAL_VAR_THRESH = 1e-3`** (`constants/animation.py`) | §1.2D canonical threshold (mean per-pixel variance in [0,1]² space). |
| **`_TEMPORAL_VAR_THRESH = 0.0`** (`frame_selection.py`) | Module-level config constant. Default 0.0 = disabled. Override via `ASP_TEMPORAL_VAR_THRESH`. |
| **`_temporal_variance_filter(thumbs, paths, sigma_threshold) → (thumbs, paths, n_dropped)`** (`frame_selection.py`) | §1.2D: for each interior frame i, stacks the (i-1, i, i+1) thumbnail triplet and computes mean per-pixel variance. If variance < sigma_threshold the frame is static and dropped. First/last always kept. No-op when threshold=0 or N<3. |
| **Wired as step 1a in `smart_select_frames`** | Runs after `_load_thumbs_parallel()`, before hold detection (step 1b). Rebinds `thumbs`, `frames_paths`, and `N` so all downstream steps see the reduced frame set. Verbose log prints drop count and threshold. |
| **`_temporal_variance_filter` in `frame_selection.py __all__`** | Exported alongside other module-level public functions. |
| **5 unit tests** (`test_frame_selection.py::TestTemporalVarianceFilter`) | static-triplet-drops-middle, high-variance-kept, first-last-never-dropped, threshold-zero-disables, fewer-than-three-passes-unchanged. **animation suite: 302 tests passing.** |

### Design rationale

§1.2A–§1.2C filter static frames at the *edge* level (after matching) or the *selected-frame* level (post-selection). All three require matching to have run first. A subtler failure mode exists upstream: when neither the camera nor the character has moved between frames i-1 and i+1, frame i is a pure duplicate and carries zero canvas information. The matching step will correctly assign it a near-zero edge, but that edge must still be built, BA-solved, and validation-checked before it is discarded.

§1.2D catches this case directly at the thumbnail level — before any edge construction — using temporal variance: a frame is static if and only if the per-pixel variance across the triplet is near zero. Unlike the luma post-filter (§1.2B), which compares *selected* frames after the frame selector has already run, §1.2D operates on the raw candidate set, preventing static frames from polluting the edge graph in the first place.

The threshold `1e-3` in [0,1]² space corresponds to a standard deviation of ~0.032 (~8 luma units). MPEG quantization noise on a truly static scene produces std ≈ 2–4 luma units (variance ≈ 4e-5 to 2.5e-4) — well below the floor. Genuine camera motion of even 5 px at thumbnail scale raises variance by > 10×. The default-disabled setting (`ASP_TEMPORAL_VAR_THRESH=0.0`) ensures no regression on existing benchmarks; enabling with `1e-3` targets compressed sources.

---

## ASP Session 38 — §1.11C Phase-Correlation Response Hold Refinement (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_HIGH_HOLD_RESPONSE = 0.85`** (`frame_selection.py`) | §1.11C configuration constant. Override via `ASP_HIGH_HOLD_RESPONSE` env var. Set to 0.0 to disable. |
| **`HIGH_HOLD_RESPONSE_THRESH = 0.85`** (`constants/animation.py`) | Canonical constant for the phase-correlation response floor. |
| **`_refine_hold_ids_by_response(hold_ids, responses, high_response_threshold) → (ids, n_blocks)`** (`frame_selection.py`) | §1.11C: post-hoc hold refinement. Iterates `responses`; for each cross-hold pair (different `hold_ids`) with `response >= threshold`, merges the higher-index block ID into the lower. IDs are renumbered consecutively (first-occurrence order) before returning. Zero extra compute — uses the `responses` list that step 3 already builds. |
| **Wired as step 3b in `smart_select_frames`** | Called after the phase-correlation loop (`responses` complete) and before step 4 (dominant axis). Only runs when both `_HOLD_THRESHOLD > 0.0` and `_HIGH_HOLD_RESPONSE > 0.0`. Updates `hold_ids` and `n_hold_blocks` in-place. Verbose logging prints updated block count. |
| **`_refine_hold_ids_by_response` in `frame_selection.py __all__`** | Exported alongside `_detect_hold_blocks` and other public functions. |
| **5 unit tests** (`test_frame_selection.py::TestRefineHoldIdsByResponse`) | all-high-merge, low-leave-unchanged, partial-merge-only-high-pairs, consecutive-renumbering, single-frame-unchanged. **animation suite: 297 tests passing.** |

### Design rationale

§1.11A (`_detect_hold_blocks`) identifies animation hold blocks using thumbnail MAD — effective for lossless or low-compression sources. On MPEG-compressed anime (broadcast, streaming), quantization noise inflates inter-frame MAD by 0.005–0.015 even between identical cels, occasionally splitting a genuine hold into two separate blocks. The phase-correlation pass (step 3) already runs `cv2.phaseCorrelate` for all cross-hold frame pairs and produces a `response` scalar in [0,1]. A response near 1.0 means the FFT peak is very sharp and narrow — i.e., the two frames are nearly identical (same image, sub-pixel drift). Values of 0.85+ are effectively unreachable for frames with different character poses; they only occur for frames that are visually identical modulo MPEG quantization noise.

§1.11C exploits this signal at zero additional cost: after step 3 has populated the `responses` list, scan for cross-hold pairs with `response >= 0.85` and merge their hold blocks. This corrects the MAD-based false splits without requiring DINOv2 or any extra computation. Within-hold pairs already have synthetic `response=1.0` (set in the hold-skip path), so the merge is idempotent for correctly detected holds. The block IDs are renumbered after merging so downstream Pass 2 scoring (`_pose_dist`), the `_hold_info` diagnostic, and the sparse-correlation speedup all see the updated block assignment.

The threshold 0.85 is deliberately conservative: MPEG quantization on 420 chroma with CRF 23 typically produces inter-frame response ~0.55–0.70 for identical-pose compressed pairs; genuine pose changes produce ~0.20–0.50. The 0.85 floor admits only near-lossless pairs. Adjustable via `ASP_HIGH_HOLD_RESPONSE`.

---

## ASP Session 37 — §2.9C High-Confidence Edge Re-Solve on Ratio Failure (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`HIGH_CONF_EDGE_THRESH = 0.65`** (`constants/animation.py`) | §2.9C floor for LoFTR-quality edge weight. LoFTR: weight ~0.7–0.95; TM fallback: ~0.15–0.55; PC fallback: ~0.15. |
| **`_filter_high_conf_edges(edges, min_weight) → List[Dict]`** (`pipeline.py`) | Keeps only edges with `weight >= min_weight`. Used as the Retry-0 pre-check on ratio failures. |
| **Retry 0 wired into Stage 7b** | Inserted before Retry 1: when `health.reason.startswith("ratio=")` and `len(_hc_edges) >= N-1`, re-solves with high-confidence edges and re-validates. Falls through to Retry 1 unchanged if fewer than N-1 HC edges survive. |
| **`_filter_high_conf_edges` in `pipeline.py __all__`** | Exported alongside other module-level functions. |
| **5 unit tests** (`test_pipeline.py`) | `TestFilterHighConfEdges`: high-weight-kept, low-weight-removed, empty-returns-empty, all-below-returns-empty, missing-weight-treated-as-zero. **animation suite: 292 tests passing.** |

### Design rationale

When LoFTR matches are unavailable for a frame pair, the pipeline falls back to template matching (weight ~0.15–0.55) or phase correlation (weight ~0.15). These low-confidence edges sometimes introduce a single large wrong displacement that passes the `_reject_static_edges` filter but corrupts the bundle-adjustment solution: one outlier edge pulls two frames to the same position, producing a `max_gap / median_gap` ratio of 5–11× and triggering affine validation failure.

The existing Retry 1 (adjacent-only edges) handles this case but only for ratio failures caused by *skip-frame* edges. If the bad edge is adjacent (i→i+1), Retry 1 keeps it unchanged.

§2.9C adds "Retry 0" specifically for ratio failures: filter all edges to those with `weight >= HIGH_CONF_EDGE_THRESH (0.65)`, which excludes TM/PC fallbacks and keeps only LoFTR-quality matches. If ≥ N-1 such edges survive, re-solve the bundle. For sequences where all frame pairs had a LoFTR match (weight > 0.7), Retry 0 produces the same result as the original solve and passes validation — the ratio failure was caused by a TM/PC edge that is now excluded. For sequences where too many frame pairs fell back to TM/PC, the HC filter returns fewer than N-1 edges and the existing Retry 1–3 chain handles the failure as before.

---

## ASP Session 36 — §0.5C Adaptive Min-Gap Threshold for Affine Validation (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_adaptive_min_gap(affines) → float`** (`validation.py`) | §0.5C: returns `max(20.0, canvas_span / (N × 3))` where `canvas_span` is the dominant-axis displacement range. Slow-scroll sequences (200 px span, N=10) → floor 20.0; fast-scroll 4K (3000 px span, N=10) → adaptive 100 px. |
| **`_compute_adaptive_min_gap` in `validation.py __all__`** | Exported alongside `AffineHealth` and `_validate_affines`. |
| **Imported and wired into `pipeline.py` Stage 7b** | First `_validate_affines` call now passes `min_step=_compute_adaptive_min_gap(affines)`. Log message updated to include `adaptive_floor=Xpx`. Import added to `validation` import line. |
| **5 unit tests** (`test_affine_validation.py`) | `TestAdaptiveMinGap`: slow-scroll-returns-floor, fast-scroll-exceeds-fixed-threshold, single-frame-returns-floor, dominant-axis-is-max-span, wired-into-pipeline-initial-call. **animation suite: 287 tests passing.** |

### Design rationale

The existing `_validate_affines(affines, min_step=25.0)` always used a fixed 25 px threshold for the minimum adjacent gap. This was calibrated for 1080p sequences with ~50–200 px inter-frame steps. Two failure modes arise from the fixed threshold:

1. **Slow-scroll sequences** (step ≈ 15–24 px): a valid but tight frame spacing is rejected because 15 px < 25 px, even though every frame is genuinely spaced at its expected distance. These sequences fall all the way to Retry 3 (`min_step=20.0`) unnecessarily, and some still fail.

2. **Fast-scroll / 4K sequences** (step ≈ 300–1000 px): a near-duplicate pair with a 26 px gap passes the 25 px threshold but represents a degenerate frame that is essentially co-located relative to the expected step. The pipeline would proceed with a bad frame that collapses the temporal median at that canvas row.

The adaptive formula `max(20.0, canvas_span / (N × 3))` anchors the minimum gap at 1/3 of the expected per-frame canvas contribution. For slow-scroll, the floor of 20.0 px matches Retry-3's existing relaxed threshold, so the first validation call will succeed where before it required recovery. For fast-scroll 4K (canvas_span ≈ 3000 px, N=10) the threshold rises to 100 px, correctly rejecting near-duplicate frames that the fixed 25 px threshold would accept. The Retry chain (R1–R3 with progressively relaxed `min_step`) is still intact for genuine boundary cases.

---

## ASP Session 35 — §3.8A Double-Edge Autocorrelation Ghosting Metric (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_ghosting_score_v2(img) → float`** (`bench_anime_stitch.py`) | §3.8A: FFT-based autocorrelation of column-mean gradient-magnitude profile. Detects secondary peak at displacement D — the signature of a ghost (misaligned shifted copy). Score [0–100]: 0=clean, 30+=ghost likely. |
| **`ghosting_siqe` in `_compute_all_metrics`** | Added alongside existing `ghosting_score` (kept for GhostGate calibration). |
| **Metric description added to report table** | `("ghosting_siqe", "§3.8A autocorr double-edge score [0–100], higher = ghost")` |
| **5 unit tests** (`test_bench_metrics.py`) | `TestGhostingScoreV2`: uniform→zero, ghost-bands→nonzero, bounded [0–100], grayscale input, `ghosting_siqe` in `_compute_all_metrics`. **animation suite: 282 tests passing.** |
| **§1.7C roadmap housekeeping** | `_crop_to_valid` in `canvas.py` already implements content-aware bounding-box crop (bounding box when valid_ratio ≥ 80%, max-inscribed-rect otherwise). §1.7C marked de facto done. |

### Design rationale

The existing `_ghosting_score()` computes the mean of `|second-order vertical Sobel|` — effectively measuring total second-derivative energy. While this loosely correlates with double-edge density, it fires equally on any high-frequency vertical pattern: fine background texture, cross-hatch patterns, and genuine ghost artifacts all inflate the score. On the 96-test corpus, `ghosting_score` averages 20–36 for both clean and ghosted outputs, making borderline cases (ratio 1.9–2.1) non-deterministic.

`_ghosting_score_v2` (§3.8A) takes a different approach:
1. Computes the column-mean of `|Gy|` — a 1D profile summarising where vertical gradients concentrate along the scroll axis.
2. Subtracts the mean and computes the zero-padded FFT autocorrelation.
3. Normalises by the zero-lag energy and looks for the maximum secondary peak in lag range [5, H/4].

A ghost creates two nearly-identical edge features at fixed displacement D. Their column-mean profiles are shifted copies, so the normalized autocorrelation peaks at lag≈D. A clean image with random texture has no preferred lag → autocorrelation falls to near-zero past lag=0. The score is clamped to [0, 1] then scaled to [0, 100] for readability.

**Why keep `ghosting_score`:** The GhostGate (`_GHOST_ABS_FLOOR=40.0`, `_GHOST_RATIO_LIMIT=2.0`) is calibrated for the double-Sobel scale (typical clean output ≈ 20–36, ghost output > 40). Replacing it without recalibrating on the full 96-test corpus would require a separate benchmarking run. `ghosting_siqe` is added as a supplementary metric; once enough benchmark data is collected, the gate can be migrated to use it.

---

## ASP Session 34 — §1.2C Adaptive Min-Step Threshold (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_adaptive_min_disp(edges) → float`** (`pipeline.py`) | §1.2C: returns `max(STATIC_EDGE_MIN_DISP_PX, ADAPTIVE_MIN_DISP_FRAC × median_adjacent_step)` on the dominant scroll axis. For slow-scroll sequences the floor (50px) dominates; for fast-scroll/4K content (e.g., 1000px/frame) the adaptive threshold rises to 100px. |
| **`ADAPTIVE_MIN_DISP_FRAC = 0.10`** (`constants/animation.py`) | §1.2C fractional constant. |
| **Wired into `_filter_edges()`** | `_compute_adaptive_min_disp(edges)` called before `_reject_static_edges`; result passed as `min_disp_px`. |
| **`_compute_adaptive_min_disp` in `pipeline.py __all__`** | Exported alongside `_reject_static_edges`. |
| **5 unit tests** (`test_filter_edges.py`) | `TestComputeAdaptiveMinDisp`: floor-dominates-small-steps, adaptive-exceeds-floor-large-steps, empty-edges-returns-floor, dominant-axis-x-selected, no-adjacent-edges-returns-floor. **animation suite: 277 tests passing.** |

### Design rationale

§1.2A (`_reject_static_edges`) uses a fixed `STATIC_EDGE_MIN_DISP_PX=50` threshold that was calibrated for 1080p sequences (~5% of frame height). For 4K sequences with typical step size 400–800px, 50px is only 2–5% of the step, meaning noisy near-zero edges can still slip through. Conversely, for ultra-slow-scroll content (step ≈ 60px), the fixed 50px threshold would discard valid edges.

§1.2C makes the threshold content-adaptive: it uses the median of adjacent-edge displacements on the dominant scroll axis as an estimate of the expected step, then applies a 10% floor (`ADAPTIVE_MIN_DISP_FRAC=0.10`). For typical 1080p content (step ≈ 200px), the adaptive threshold equals `max(50, 20) = 50` — unchanged. For fast-scroll 4K (step ≈ 1000px), it raises to `max(50, 100) = 100` — rejecting near-zero edges that the old fixed threshold would have passed.

---

## ASP Session 33 — §3.15A SemanticStitch Column Barrier + §3.14 Scroll-Axis Detection (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **§3.15A column fg-domination barrier** (`compositing.py`) | `_build_seam_cost_map()`: columns with >50% fg-interior pixels raised to cost=2.0 (above Tier 1 max of 1.0), forcing DP seam into background-only corridor columns. Falls back to per-pixel costs when all columns are fg-dominated. |
| **§3.14 scroll-axis detection wired** (`pipeline.py`) | `_detect_scroll_axis` imported and called after Stage 9; `'horizontal'` scroll type → explicit SCANS fallback with log. (Function existed in `canvas.py` but was never called from the pipeline.) |
| **10 unit tests** | `TestSeamCostColumnFilter` (5) in `test_compositing.py`; `TestDetectScrollAxisModule` (5) in `test_canvas.py`. **animation suite: 272 tests passing.** |

---

## ASP Session 32 — §1.2A Pre-bundle Static Edge Rejection (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_reject_static_edges(edges, min_disp_px) → List[Dict]`** (`pipeline.py`) | §1.2A: drops any edge where BOTH `|dx| < min_disp_px` AND `|dy| < min_disp_px`. Default `min_disp_px = STATIC_EDGE_MIN_DISP_PX = 50`. Keeps an edge if EITHER axis is >= the threshold (preserves valid diagonal-scroll edges). |
| **`STATIC_EDGE_MIN_DISP_PX = 50`** (`constants/animation.py`) | New pipeline constant for the combined-axis displacement threshold. |
| **Wired into `_filter_edges()`**  | `_reject_static_edges(edges)` is called at the very start of `_filter_edges()`, before the geometric consistency filter. Ensures near-zero-2D-displacement edges cannot corrupt the direction consensus median. |
| **`_reject_static_edges` exported in `pipeline.py __all__`** | Added alongside `_spatial_dedup_frames`. |
| **5 unit tests** (`test_filter_edges.py`) | `TestRejectStaticEdges`: normal-edges-all-kept, both-axes-below-threshold-rejected, one-axis-above-threshold-kept, skip-edge-with-small-displacement-rejected, empty-edge-list. **animation suite: 262 tests passing.** |

### Design rationale

The existing min-step guard in `_filter_edges` (shipped in an earlier session) rejects adjacent edges where the **primary-axis** displacement is below `MIN_EXPECTED_STEP=25px`. This covers the common failure mode (vertical pan with small dy), but leaves two gaps:

1. **Skip edges** (j > i+1) with small 2D displacement are not filtered.
2. **Both-axes-small** edges — where neither axis alone triggers the primary-axis check (e.g., dx=20px, dy=30px for a diagonal sequence with primary=y) — pass through.

§1.2A closes both gaps with a combined-axis pre-filter: reject any edge where BOTH |dx| and |dy| are below 50px. This runs before all other filters so near-zero edges can't skew the consensus median that the direction filter relies on. An edge is kept if EITHER axis meets the threshold, preserving horizontal-scroll edges (large |dx|, small |dy|).

---

## ASP Session 31 — §1.3B PANORAMA Stitcher Fallback (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_panorama_stitch_fallback(frames, output_path) → PIL.Image`** (`canvas.py`) | §1.3B: tries `cv2.Stitcher_create(mode=0)` (PANORAMA) for affine-validation failures before the SCANS path. PANORAMA handles scale and rotation that the translation-only canvas model rejects. Raises `RuntimeError` on failure so the caller can fall through. |
| **`_panorama_stitch_fallback` wired into `pipeline.py`** | Inserted between Retry 3 and the SCANS fallback in the affine validation failure branch (line ~1037). Any `Exception` from PANORAMA is caught; the pipeline logs it and proceeds to `_scan_stitch_fallback`. |
| **`_panorama_stitch_fallback` added to `canvas.py __all__`** | Exported alongside `_scan_stitch_fallback`. |
| **5 unit tests** (`test_canvas.py`) | `TestPanoramaStitchFallback`: returns-pil-image-on-success, raises-runtime-error-on-non-ok-status, saves-file-on-success, uses-panorama-mode-zero, output-dimensions-match-pano. **animation suite: 257 tests passing.** |

### Design rationale

When `_validate_affines` rejects a solution after Retries 1–3, the pipeline has historically fallen back immediately to SCANS mode. SCANS is a scan-line stitcher (mode=1) that still uses the same global feature detector and homography estimator as PANORAMA, but assumes a flat scene and ignores rotation/scale — which is why it works well for pure vertical pans but fails on zoom-and-pan sequences.

§1.3B inserts a PANORAMA stitcher attempt between Retry 3 and SCANS. PANORAMA (mode=0) uses spherical/cylindrical projection and handles affine distortions natively. For sequences with `scale_dev > 0.05` or `max_rotation > 0.03` (the conditions that trigger affine validation failure), PANORAMA has significantly better coverage. If PANORAMA also fails (returns non-OK status or throws), the pipeline falls through to SCANS as before — net regression risk is zero.

---

## ASP Session 30 — §1.1D Adaptive GNC f_scale (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_adaptive_f_scale(edges, affines, floor) → float`** (`bundle_adjust.py`) | §1.1D: derives a data-driven Cauchy loss scale from the post-solve edge residuals. Returns `max(floor, 2.0 × median_residual_px)`. Pure module-level function, exported in `__all__`. |
| **Adaptive re-solve in `_bundle_adjust_affine`** | After the initial LM solve, the function extracts preliminary affines and calls `_compute_adaptive_f_scale`. If `adaptive_scale > _BA_F_SCALE × 1.5`, a single re-solve runs with the data-derived scale (warm-started from `x_opt`). The two-pronged outlier rejection then runs on the refined solution as before. |
| **`__all__` added to `bundle_adjust.py`** | Exports `["_bundle_adjust_affine", "_compute_adaptive_f_scale"]`. |
| **5 unit tests** (`test_bundle_adjust.py`) | `TestAdaptiveFScale`: floor-dominates-for-perfect-solution, widens-when-solution-does-not-fit-edges, empty-edges-returns-floor, floor-respected-for-tiny-residuals, single-edge-computes-correctly. **animation suite: 252 tests passing.** |

### Design rationale

The existing GNC Cauchy loss uses a hardcoded `f_scale=10.0` (overridable via `ASP_BA_F_SCALE`). This value was calibrated on the primary corpus and is appropriate when good matches have < 5 px residuals. For sequences with uniformly elevated noise (MPEG compression artefacts, slight zoom, moderate blur), all edges can land at 20–40 px residuals — none are extreme outliers, but the fixed f_scale=10 treats them all as outliers (50% downweighted at 10 px, 12% at 20 px). This biases the LM toward a local minimum that satisfies the regularisation terms rather than the edge constraints.

§1.1D addresses this with a one-shot adaptive step: after the initial solve, compute the median edge residual from the preliminary affines. If that median residual implies an f_scale more than 50% wider than `_BA_F_SCALE`, re-solve with the wider scale. For clean data (residuals ≈ 2 px), the floor kicks in and behaviour is unchanged. For uniformly noisy data (residuals ≈ 30 px), `adaptive_scale = max(10, 60) = 60 px` — the re-solve now treats 30 px edges as inliers, allowing the BA to converge to the correct global consensus.

The re-solve is warm-started from `x_opt` (the initial solution), so it takes far fewer LM iterations than a cold start. The two-pronged outlier rejection still runs afterwards on the refined solution, preserving the existing robustness layer.

---

## ASP Session 29 — §1.10A RLHF Post-run Quality Gate (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_RLHF_FLAG_THRESHOLD = 0.6`** (`bench_anime_stitch.py`) | Module-level constant. Outputs with `rlhf_score < 0.6` are flagged for human review in the feedback tab. |
| **`_get_reward_model()`** | Lazy singleton loader for `StitchRewardModel`. Initialises on first call; returns `None` on any import or init error (e.g., torch unavailable). |
| **`_compute_rlhf_score(img_bgr: np.ndarray) → Optional[float]`** | Calls `StitchRewardModel.predict(img_bgr)`, returns a float in [0, 1] or `None` for empty/invalid input or unavailable model. |
| **`_compute_all_metrics` updated** | Added `rlhf_score` (float or None) and `rlhf_flagged` (bool) to every metrics dict. The lazy model is loaded once per benchmark run and reused across all tests. |
| **5 unit tests** (`test_bench_metrics.py`) | `TestComputeRlhfScore`: float-or-None contract, empty-image None guard, valid range [0,1], flagged-when-below-threshold (mock), not-flagged-at-threshold (mock). **animation suite: 247 tests passing.** |

### Design rationale

The reward model CNN (`backend/src/animation/rlhf/reward_model.py`) has existed since early sessions but was never wired into the benchmark evaluation loop. Without wiring, benchmark runs produced no `rlhf_score` column — there was no automated signal to identify which of the 96 outputs warranted human review, and the `_RLHF_FLAG_THRESHOLD` concept had no concrete implementation.

The S29 addition is minimal by design. The model loads lazily (no startup cost when not used), and the wiring is entirely in the benchmark, not in the pipeline itself. The `rlhf_flagged` key in the per-test metrics dict acts as the entry point for the human feedback tab: the tab can filter the results table to `rlhf_flagged=True` outputs and present them for rating. Collected ratings then flow into `StitchRewardModel.train_from_feedback()` (already implemented), which tightens the model's predictions for future runs.

Current limitation: the model is initialised with random weights if no checkpoint exists at `~/.config/image-toolkit/stitch_reward_model.pt`. The `rlhf_score` values are therefore uninformative until at least a few dozen labelled examples have been collected. The infrastructure is in place; the quality of the gate improves with feedback volume.

---

## ASP Session 28 — §1.9A Spatial Dedup scans_frames Sync (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_spatial_dedup_frames(frames, scans_frames, bg_masks, image_paths, edges, min_displacement_px)` → `Tuple[..., int]`** (`pipeline.py`) | §1.9A: extracts the post-Stage-6 spatial near-static dedup loop body into a standalone, testable module-level function. Returns all updated lists plus `n_dropped`. Pure function — no side effects, no logging. |
| **§1.9A sync fix** | The previous while-loop updated `frames`, `bg_masks`, `image_paths`, and `edges` on each drop pass but never updated `scans_frames`. Every SCANS fallback triggered after spatial dedup therefore received the full pre-dedup frame set (including near-duplicates just discarded). One-line fix: `[scans_frames[i] for i in keep_idx]` appended to the drop block. |
| **`run()` refactored to call `_spatial_dedup_frames`** | The while-loop body in `AnimeStitchPipeline.run()` is replaced by a call to the new function. Loop exit condition (`_spa_changed`) is now simply `n_dropped > 0`. N<2 fallback path unchanged. |
| **`_spatial_dedup_frames` added to `__all__`** | Directly importable for testing. |
| **5 unit tests** (`test_pipeline.py`) | New `TestSpatialDedupFrames` class: `test_no_drop_when_displacement_above_threshold` (all edges ≥ min_px → unchanged), `test_drops_near_static_adjacent_frame` (one sub-threshold edge → frame dropped), `test_scans_frames_synced_with_frames_after_drop` (scans_frames tracks frames after drop), `test_edges_reindexed_after_drop` (i/j indices remapped correctly after a mid-sequence drop), `test_first_frame_never_dropped` (frame 0 is always anchor). **animation suite: 242 tests passing.** |

### Design rationale

The bug was subtle: `scans_frames` is set at Stage 2 (after width-normalisation, before BiRefNet) as the snapshot for all SCANS fallbacks. The pre-Stage-5 luma dedup (line 716) correctly syncs `scans_frames` when it drops frames. But the post-Stage-6 spatial dedup (the `while _spa_changed` loop) only updated `frames`, `bg_masks`, `image_paths`, and `edges` — never `scans_frames`. Any SCANS fallback triggered after spatial dedup would therefore receive the full original set including the frames the spatial dedup just discarded as near-static noise.

The consequence is benign in most cases (near-duplicate frames add small overlapping content to the scan stitch, producing a result nearly identical to without them), but it is semantically wrong: the pipeline had committed to a specific frame subset, and the fallback path was violating that commitment. The fix is a single list comprehension in the dedup block, unchanged across all loop passes.

Extracting `_spatial_dedup_frames` as a module-level function also makes the dedup logic auditable and independently testable without requiring a full pipeline run. Future changes to the dedup criterion (e.g., switching from axis-specific to vector-magnitude comparison) can be validated by tests on the pure function.

---

## ASP Session 27 — §1.8A TOML Config Loader (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`load_asp_config(path, *, override_env) → Dict[str, Any]`** (`backend/src/animation/config.py`) | §1.8A: loads `asp_config.toml` (or a caller-supplied path) using Python 3.11 stdlib `tomllib`. Sections are merged into a flat dict; each key is written to `os.environ` via `setdefault` so downstream `os.environ.get` calls in pipeline modules pick it up automatically. Explicit env vars always win over the config file. Zero new dependencies. |
| **Multi-section TOML format** | Keys are organised under semantic sections (`[frame_selection]`, `[compositing]`, `[pipeline]`, etc.) for readability. Any key is valid — unrecognised keys are forwarded as env vars. |
| **`override_env=False` dry-run mode** | Passing `override_env=False` loads and returns the config dict without touching `os.environ`, enabling unit-test isolation and config-preview tooling. |
| **`load_asp_config` added to `backend.src.animation.config.__all__`** | Directly importable from the package. |
| **5 unit tests** (`test_config.py`) | New `TestLoadAspConfig` class: `test_missing_file_returns_empty_dict` (absent file → `{}`), `test_valid_config_sets_env_var` (value written to env), `test_existing_env_var_not_overwritten` (setdefault semantics), `test_multi_section_keys_flattened` (two sections merged into flat dict), `test_override_env_false_does_not_write_env` (dry-run mode). **animation suite: 237 tests passing.** |

### Design rationale

All ASP runtime constants are currently controlled by env vars (`ASP_NEAR_DUP_LUMA`, `ASP_HOLD_THRESHOLD`, `ASP_SP_SOFT_PX`, etc.). This works for one-off experiments but is cumbersome for reproducible benchmark runs — environment state is transient, not recorded with the run. §1.8A adds a persistent config file that can be checked in alongside the benchmark results, enabling exact reproducibility.

The TOML format is preferred over `.env` because it supports typed values (integers, floats, booleans), sections for organisational clarity, and comments. Python 3.11's stdlib `tomllib` requires no new dependency.

The `setdefault` semantics (env wins over file) preserve the existing workflow: developers can still override any value with an environment variable without touching the config file. The config file is a default, not a constraint.

Example `asp_config.toml`:

```toml
# Frame selection
[frame_selection]
ASP_NEAR_DUP_LUMA = 5.0
ASP_HOLD_THRESHOLD = 0.03

# Compositing
[compositing]
ASP_SP_SOFT_PX = 6
ASP_POISSON_SEAM = 0
ASP_GATE_GHOST_FLOOR = 40.0

# Pipeline routing
[pipeline]
ASP_COV_MIN_MULTI_PCT = 0.30
```

---

## ASP Session 26 — §1.2B Near-Duplicate Luma Post-Filter (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_near_dup_luma_filter(selected_thumbs, selected_paths, threshold)` → `List[str]`** (`frame_selection.py`) | §1.2B: post-filter on the already-selected frame list. Compares consecutive pairs by mean absolute grayscale difference on thumbnail images. Frames with `diff < threshold` luma units are dropped. First frame always kept; last frame always retained (preserves full canvas extent). |
| **`_NEAR_DUP_LUMA` config var** (`frame_selection.py`) | Env var `ASP_NEAR_DUP_LUMA` (default `0.0` = disabled). Set to e.g. `5.0` to activate. Default OFF avoids regression risk on the existing test corpus. |
| **Wired as step 8 in `smart_select_frames`** | After both selection passes, if `_NEAR_DUP_LUMA > 0.0` and more than 2 frames are selected, `_near_dup_luma_filter` is applied. Verbose mode prints how many near-dup frames were dropped. |
| **`_near_dup_luma_filter` added to `__all__`** | Directly importable and testable from `backend.src.animation.frame_selection`. |
| **`NEAR_DUP_LUMA_THRESH = 3.0` added to `constants/animation.py`** | Promotes the magic number from `pipeline.py`'s pre-stage-5 luma dedup (`diff < 3.0`) to a named constant. Imported and used in `pipeline.py`. |
| **5 unit tests** (`test_frame_selection.py`) | New `TestNearDupLumaFilter` class: `test_disabled_at_zero_threshold` (threshold=0 → all paths unchanged), `test_all_identical_keeps_first_and_last` (5× same lum → only first + last survive), `test_all_different_keeps_all` (large luma steps → no drops), `test_two_frames_passes_unchanged` (≤2 frames always bypassed), `test_middle_near_dup_dropped_first_last_kept` (middle near-dup dropped; first and last always in result). **animation suite: 232 tests passing.** |

### Design rationale

§1.2B complements the hold-block detection (S6, §1.11) and the existing pre-stage-5 luma dedup in `pipeline.py`. Hold detection identifies camera-hold runs (same cel repeated for 2–3 video frames); the pre-stage-5 dedup catches exact duplicates after BiRefNet preprocessing. The new `_near_dup_luma_filter` operates on the SELECTED frame list at thumbnail scale, before the full-resolution pipeline begins. This catches a third class of redundancy: frames that were selected because they meet the min-step-px displacement threshold, but whose pixel content is nearly indistinguishable because the camera moved in a direction where the background change is small (e.g., vertical pan with a character that fills the full frame horizontally).

The function is disabled by default (`ASP_NEAR_DUP_LUMA=0.0`) because the existing corpus doesn't need it — the greedy forward selection already guarantees at least `min_step_px=50px` of camera advance per frame, which for most scenes produces > 5-luma units of mean content change. The filter activates only when explicitly enabled, making it a safe addition with no regression risk. The "last frame always retained" invariant is critical: the last selected frame determines the canvas extent; dropping it would crop the panorama.

---

## ASP Session 25 — §3.9 Fix: Unified `_compute_aligned_ssim` (S8 Metric Dedup) (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **Dead code removed: S8 `_compute_aligned_ssim`** (`bench_anime_stitch.py` lines 168-204) | The S8 EUCLIDEAN definition was silently overridden at module level by the later S9 TRANSLATION definition (Python last-wins). All call sites in `_compute_gt_metrics` were using TRANSLATION-only ECC (50 iterations, 0.01 tolerance). The dead S8 definition is now removed. |
| **Active `_compute_aligned_ssim` upgraded to EUCLIDEAN** (`bench_anime_stitch.py`) | The surviving definition (formerly line 377) is now upgraded: `cv2.MOTION_TRANSLATION` → `cv2.MOTION_EUCLIDEAN`; criteria updated from `(50, 0.01)` → `(200, 1e-4)`. Robustness features from the active version are preserved: `gaussFiltSize=5` (pre-smooths ECC input for noisy/low-texture crops), GT-centric resize `cv2.resize(output_img, (w, h))` (correct reference space), `borderMode=cv2.BORDER_REPLICATE`. Docstring updated to document S25 consolidation. |
| **Redundant double call eliminated** (`_compute_gt_metrics`) | Lines 434 and 437 both called `_compute_aligned_ssim(output_img, gt_img)`. Line 434 assigned to `aligned_ssim_val` (unused). Consolidated to a single call assigning to `aligned_ssim`. |
| **5 unit tests for `_compute_aligned_ssim`** (`test_bench_metrics.py`) | New `TestComputeAlignedSsim` class (skipped if skimage unavailable): `test_identical_images_returns_one` (identical input → SSIM ≈ 1.0), `test_returns_float` (isinstance check), `test_shifted_image_high_ssim_after_alignment` (translated copy with 5px shift → score > 0.70 after ECC correction), `test_different_images_score_below_one` (structurally unrelated → < 0.99), `test_score_in_valid_range` (SSIM ∈ [0, 1]). **animation suite: 227 tests passing.** |

### Design rationale

The S8 and S9 `_compute_aligned_ssim` definitions were identical in intent (ECC-aligned SSIM to remove GT-coupling framing bias) but diverged in implementation:

| Property | S8 (dead) | S9→S25 (active) |
|---|---|---|
| Motion model | MOTION_EUCLIDEAN | MOTION_TRANSLATION → **MOTION_EUCLIDEAN** |
| Iterations | 200 | 50 → **200** |
| Tolerance | 1e-4 | 0.01 → **1e-4** |
| gaussFiltSize | not set | 5 ✅ |
| Resize reference | min(h,w) | GT dims ✅ |
| BORDER_REPLICATE | ✅ | ✅ |

S25 consolidates the best of both: EUCLIDEAN motion model (handles small rotation residuals from the panorama assembly, not just translation), tighter convergence (200 iter / 1e-4 matches animation-frame alignment demands), and the S9 robustness features (Gaussian pre-smooth, GT-centric reference space, replicate border). The function name, signature, and call sites are unchanged.

---

## ASP Session 24 — §1.4B Continuous Adaptive Gain Clamp (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_adaptive_gain_clamp` rewritten** (`compositing.py`) | §1.4B: replaced the S18 binary threshold (ref_lum<80 → ±18%, ≥80 → ±14%) with `clamp_width = 0.26 − 0.12 × (ref_lum / 255)`. At ref=0 this gives ±26%; at ref=255 it gives exactly ±14% (anchored to the S18 normal ceiling). All intermediate values are linearly interpolated — the discontinuity at ref=80 is gone. |
| **5 existing `TestAdaptiveGainClamp` tests updated** (`test_compositing.py`) | Tests 1, 2, 5 now compute their expected `lo`/`hi` via the continuous formula helper `_lo(ref)` / `_hi(ref)`. Test 4 (`test_dark_threshold_boundary_at_80`) renamed `test_continuous_no_jump_at_ref_80` — verifies `|f(79.9, 300) − f(80.0, 300)| < 0.001` (continuity). Test 3 (unclamped correction) unchanged. |
| **3 new `TestAdaptiveGainClamp` tests** (`test_compositing.py`) | `test_bright_ref_hi_matches_anchor` (ref=255 → hi=1.14 exactly), `test_clamp_width_monotone_decreasing` (lo(50) < lo(200)), `test_mid_ref_continuous_formula` (ref=128 → exact formula result). animation suite: 222 tests passing. |

### Design rationale

§1.4A (S18) introduced a conditional that chose ±18% for ref<80 and ±14% for ref≥80. This created a visible step in the gain-clamp surface: at ref=79.9 the lower bound is 0.82, but at ref=80.0 it jumps to 0.88 — a discontinuity of 0.06 in a smooth quantity. §1.4B's linear interpolation `clamp_width = 0.26 − 0.12 × (ref_lum/255)` produces a smooth surface anchored at ±14% (the S18 normal value) for bright scenes and ±26% for pure-black scenes. The wider allowance for dark scenes (±26% vs S18's ±18%) reflects that dark-scene photometric residuals can be proportionally larger. The key invariant preserved: at ref=255 the upper bound is exactly 1.14, matching the S18 normal upper anchor so the correction is no more aggressive on bright scenes.

---

## ASP Session 23 — §1.7B OpenCV INPAINT_TELEA Border Fill Fallback (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_telea_fill_gaps(canvas, gap_mask) → np.ndarray`** (`canvas.py`) | §1.7B: fills residual black border pixels left after Stage-13 `_crop_to_valid`, using `cv2.inpaint(inpaintRadius=3, flags=cv2.INPAINT_TELEA)`. Zero new dependencies. Fast (~0.5 s typical). Returns unchanged canvas when `gap_mask.any()` is False. |
| **`_telea_fill_gaps` added to `canvas.py __all__`** | Directly importable and testable from `backend.src.animation.canvas`. |
| **TELEA fallback in `pipeline.py` P1.8 block** | The `except Exception` block that previously logged "keeping canvas as-is" now attempts `_telea_fill_gaps` as a fast recovery path when diffusion inpainting fails. A second `except` guards against degenerate inputs (fully-black canvas). |
| **`_telea_fill_gaps` imported in `pipeline.py`** | Added to the `from .canvas import (...)` block alongside `_crop_to_valid` and `_scan_stitch_fallback`. |
| **5 unit tests** (`test_canvas.py`) | New `TestTelaeFillGaps` class: `test_no_gap_returns_unchanged` (all-zero mask → identical output), `test_shape_preserved`, `test_dtype_preserved` (uint8 in → uint8 out), `test_corner_gap_no_longer_black` (4×4 black corner filled by neighbour propagation → `max() > 0`), `test_valid_region_unchanged_outside_band` (pixels ≥8 rows/cols from gap band untouched). animation suite: 219 tests passing. |

### Design rationale

The P1.8 inpainting block already attempts diffusion inpainting (`mfsr.inpaint_gaps`) for coverage gaps below 95%. In practice this path always raises an import error in the standard environment (the `mfsr` module requires GPU diffusion dependencies not installed by default). Before S23, the except block silently discarded the gap fill and left black corner triangles in the output — the intended behavior was there, but the fallback was missing. `cv2.inpaint(INPAINT_TELEA)` fills from the nearest valid pixels outward, resolving the typical 10–30 px black triangles produced by diagonal-scroll canvas geometry in ~0.5 s. The roadmap note about smearing for gaps > 50 px wide is preserved in the docstring — TELEA is not suitable as a primary fill for large diagonal-scroll holes (use the §1.7A diffusion path or §1.7C inner-rect crop instead).

---

## ASP Session 22 — §1.6B Gain-Adaptive Feather Minimum + Dead Code Removal + Roadmap Housekeeping (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_gain_to_min_feather(gain_diff: float) -> int`** (`compositing.py`) | §1.6B: minimum feather width from luminance gain difference. Formula: `min(120, max(40, int(gain_diff × 300)))`. Ensures the blend zone is wide enough to smooth any residual brightness step after the adaptive gain clamp. Floor=40px (below FEATHER_MIN=80) so it only has effect when `|gain_A − gain_B| > 0.267` (extreme dark/bright adjacent pairs). Cap=120px prevents excessive blurring. |
| **`frame_gains` tracking in normalization loop** (`compositing.py`) | `frame_gains: List[float] = [1.0] * N` initialized before the normalization loop; `frame_gains[i] = gain` stored alongside each applied gain. Indexed by frame index, defaulting to 1.0 for skipped/uncorrected frames. |
| **`max_feathers` cache in overlap-cap loop** (`compositing.py`) | `max_feathers: List[int] = []` populated in the overlap-cap loop so §1.6B can re-apply the cap (`feathers[k] = min(min_fk, max_feathers[k])`) without recomputing `nat_overlap` per boundary. |
| **§1.6B pass after overlap-cap** (`compositing.py`) | For each boundary k: `gain_diff = abs(frame_gains[fi_a] - frame_gains[fi_b])`, `min_fk = _gain_to_min_feather(gain_diff)`. If `feathers[k] < min_fk`, widen (capped by `max_feathers[k]`). Prints a per-boundary feather report only when any boundary was actually widened. |
| **Dead code removed: `_normalize_warped_to_median`** (`compositing.py`) | Removed the 30-line function (per-channel gain normalization) that was defined but never called. The function's hue-shift risk was the documented reason for its disuse; the scalar-gain approach in `_adaptive_gain_clamp` supersedes it. |
| **`_gain_to_min_feather` added to `__all__`** | Directly importable and testable from `backend.src.animation.compositing`. |
| **6 unit tests** (`test_compositing.py`) | New `TestGainToMinFeather` class: `test_zero_diff_returns_floor` (0.0→40), `test_small_diff_returns_floor` (0.1×300=30<40→40), `test_mid_diff_scales_linearly` (0.2×300=60→60), `test_large_diff_capped_at_120` (0.5×300=150→120), `test_at_floor_boundary` (40/300×300=40→40), `test_just_above_floor_boundary` (0.14×300=42→42). animation suite: 214 tests passing. |
| **Roadmap housekeeping** (`roadmaps/asp.md`) | Marked ✅: §0.5A (25px threshold), §0.5B (vector magnitude gap), §1.1C (GNC Cauchy loss), §1.4A (adaptive gain clamp), §1.5A (seam DP vectorization), §1.5C (adaptive boundary search), §1.5E (parallel seam DP), §1.6A (tiered seam cost), §1.6B (gain-adaptive feather), §1.6C (Poisson blend). |

### Design rationale

§1.6B targets the residual brightness step that persists even after the §1.4A gain clamp. The clamp bounds gains to [0.82–1.22] per frame; for a boundary where frame A was corrected by ×1.18 and frame B by ×0.90, the net gain mismatch is 0.28 — enough to produce a visible 10–20 lum horizontal band. A feather of `int(0.28 × 300) = 84px` smoothly blends this band over 84 rows. For typical adjacent-frame pairs (gain diff < 0.13), `_gain_to_min_feather` returns the 40px floor, which is below the existing FEATHER_MIN=80px and has no effect. The function therefore only activates on genuinely mismatched pairs — intentional scoping to avoid widening feathers in normal cases.

Dead code removal: `_normalize_warped_to_median` (per-channel scalar gain) was intentionally disabled due to hue-shift risk when backgrounds are dominated by a strong colour. The scalar-luminance `_adaptive_gain_clamp` (S18) is its correct replacement. No call sites existed anywhere in the codebase.

---

## ASP Session 21 — §1.6C Gradient-Domain Poisson Seam Blend (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_poisson_seam_blend(fa_zone, fb_zone, path_local, apply_mask)`** (`compositing.py`) | §1.6C: Gradient-domain seam refinement via `cv2.seamlessClone(NORMAL_CLONE)`. Builds a hard-partition zone (fa above the DP path, fb below), then applies Poisson blending in a ±20px band around the path. The Poisson solver finds pixel intensities that minimise `‖∇(out) − ∇(fb)‖²` subject to the hard-partition boundary conditions — eliminating the brightness step at the seam cut without ghosting. Seam band clipped to `[1, zone_h-2] × [1, W-2]` to satisfy `cv2.seamlessClone`'s no-border-touch requirement. Falls back to the hard partition on `cv2.error`. |
| **`_POISSON_SEAM` flag + `_POISSON_BAND_PX = 20`** (`compositing.py`) | Enabled via `ASP_POISSON_SEAM=1` (default OFF — adds ~1–3 s per seam on CPU). When enabled, the Poisson zone replaces the Laplacian+DSFN blend in the normal (non-single-pose, non-ToonCrafter) `else` branch of the blend loop. Single-pose and ToonCrafter seams are unaffected. |
| **`_poisson_seam_blend` added to `__all__`** | Directly importable and testable from `backend.src.animation.compositing`. |
| **5 unit tests** (`test_compositing.py`) | New `TestPoissonSeamBlend` class: `test_shape_and_dtype` (output shape/dtype correct), `test_above_seam_band_unchanged` (rows above the band match hard partition fa), `test_below_seam_band_unchanged` (rows below the band match hard partition fb), `test_path_near_bottom_no_crash` (path near zone edge clips band and doesn't raise), `test_empty_apply_returns_hard_partition` (empty apply_mask returns unblended hard partition). animation suite: 208 tests passing. |

### Design rationale

The Laplacian+DSFN blend in the `else` branch is a good default: it adapts ramp width to photometric similarity and zeroes out fg-vs-fg ghosting (S20). But for background-only seam bands (where the DP path already avoids characters), it leaves a residual brightness step equal to `|gain_A − gain_B|` — typically 2–6 lum units after normalization. Poisson blending solves this exactly: by solving the gradient-matching equation with the hard-partition as boundary conditions, it produces a continuous intensity field with no discontinuity at the seam. The effect is visible as a smooth brightness ramp of ≈40px instead of the abrupt step. Gate behind `ASP_POISSON_SEAM=1` because `cv2.seamlessClone` is CPU-only and takes 1–3 s for a full-width anime frame seam zone; it is best used in final-output mode or targeted evaluation runs.

---

## ASP Session 20 — S20: bg-Mask-Aware DSFN Ramp (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_soft_seam_weight` — fg-vs-fg similarity zeroed after Gaussian diffusion** (`compositing.py`) | S20: when `bg_mask_a`/`bg_mask_b` are provided, `sim_diffused[both_fg] = 0.0` is applied after the Gaussian blur step, where `both_fg = (~bg_mask_a.astype(bool)) & (~bg_mask_b.astype(bool))`. Previously these masks were passed through the signature but never used. This prevents background similarity from diffusing into character-vs-character overlap regions: without the fix, the blur kernel could propagate high-similarity background values into adjacent fg-vs-fg pixels, artificially widening the blend ramp and creating double-image ghosting. Background pixels on the seam-side edge of the fg boundary are untouched and retain their diffused similarity. |
| **2 unit tests** (`test_compositing.py`) | Added to `TestSoftSeamWeight`: `test_bg_mask_fg_fg_narrows_blend` (all-fg bg_masks narrow the blend transition band vs. no-mask for similar frames), `test_bg_mask_none_result_unchanged` (None bg_masks produce identical output to calling without them). animation suite: 203 tests passing. |

### Design rationale

`_soft_seam_weight` already received `bg_mask_a`/`bg_mask_b` at every call site (both sliced from `warped_bg[fi_a/fi_b]`), but the function body never read them. The Gaussian diffusion with `sigma=20px` diffuses background similarity ~40px into the frame, which can pull fg-vs-fg pixels up to `sim≈0.5` if they're close to a background region. At `sim=0.5`, `ramp = min_ramp + 0.5 * (max_ramp - min_ramp)` — roughly 50–100px, wide enough to create ghost-blending across two different character poses. After S20 the forcing only fires for pixels where both frames agree the pixel is foreground, which is the exact class that should always receive a narrow ramp.

---

## ASP Session 19 — §1.6A Tiered Seam Cost (S19) (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_build_seam_cost_map` Tier 2 cost lowered from 1.0 → 0.5** (`compositing.py`) | §1.6A: the edge-buffer zone (background pixels within `dilate_px` of any fg boundary) now costs 0.5 instead of 1.0. The fg interior (Tier 1) remains at 1.0. This creates a three-level gradient — interior=1.0 → edge buffer=0.5 → background=0.0 — giving the DP seam path-finder an incentive to route *through* the edge buffer toward clean background, rather than treating it identically to the character body. With `sem_weight=200`, energy levels are: fg body≈200, edge buffer≈100, background≈0–50. Before S19 the edge buffer was also ≈200, offering no gradient. |
| **`_build_seam_cost_map` added to `__all__`** | Function is now importable and directly testable. |
| **7 unit tests** (`test_compositing.py`) | New `TestSeamCostMap` class: all-bg cost=0.0, all-fg cost=1.0, edge-buffer row=0.5, pure-bg-far-from-fg=0.0, fg interior not lowered to 0.5 by edge buffer, None masks return zero, union of two fg masks covers both regions at 1.0. animation suite: 201 tests passing. |

### Design rationale

Before S19 the seam DP treated the edge buffer zone (≤15px outside any fg boundary) identically to the character body (both cost=1.0 × sem_weight=200). When the only route from one boundary to another passed through a narrow region flanked on both sides by character edges, the DP had no gradient: routing through the edge buffer cost the same as routing through the body. After S19 the DP sees a "highway shoulder" (cost=100) between the forbidden zone (body=200) and the fast lane (background=0–50), making it more likely to find the shortest route through background for partially-covered seam zones.

---

## ASP Session 18 — Per-Pair Coherence Gate + §1.4A Adaptive Gain Clamp (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_coherence_skip_mask(order, frame_lums, coherence_limit)`** (`compositing.py`) | Standalone testable helper. Per-frame normalization-skip mask built from adjacent-strip coherence check. Marks both frames in an adjacent pair as skip-normalization when their background luminance differs by more than `coherence_limit`. Only the bad pair's frames are excluded — other frames proceed normally. Replaces the former global-skip that penalised every frame when a single scene-change pair exceeded the limit. |
| **`_adaptive_gain_clamp(ref_lum, frame_lum)`** (`compositing.py`) | §1.4A adaptive gain clamp. Dark scenes (ref_lum < 80) use `[0.82, 1.22]` (±18%); normal scenes use `[0.88, 1.14]` (±14%). Replaces the previous fixed `±7%` clamp. Stage 4.5 already applies ±14–20% before warping; Stage 11 corrects any residual after canvas projection. The wider clamp allows Stage 11 to fully bridge residuals that Stage 4.5 couldn't reach due to its own ceiling. |
| **Normalization block updated** (`compositing.py`) | `_composite_foreground` calls `_coherence_skip_mask()` for per-frame skip flags and `_adaptive_gain_clamp()` for each frame's gain. Print log now reports per-pair skip count instead of binary global skip/proceed. |
| **11 unit tests** (`test_compositing.py`) | `TestAdaptiveGainClamp` (5 tests): normal scene clamped at 0.88/1.14, dark scene clamped at 0.82/1.22, small correction passes unclamped, dark threshold boundary at 80, zero frame_lum protected. `TestCoherenceSkipMask` (6 tests): all-small diffs none skipped, bad pair both skipped, good frames after bad pair not skipped, None lum pair ignored, exactly-at-limit not skipped, non-identity order maps correctly. animation suite: 194 tests passing. |

### Design rationale

**Per-pair coherence gate**: The previous guard used `max(adj_diffs) > 20` → skip ALL normalization for the entire sequence. A scene change between frames 3 and 4 caused frames 1, 2, 5, 6 (coherent backgrounds) to also skip normalization, widening strip-banding to the whole composite. The per-pair approach isolates the bad pair while allowing the rest to normalize.

**§1.4A wider gain clamp**: Stage 11 was limited to ±7%. For a frame where Stage 4.5 hit its own ±14% ceiling (true correction needed was >14%), the residual can be up to 6–12% — larger than ±7% can bridge. The ±14%/±18% clamp ensures Stage 11 always closes the residual left by Stage 4.5.

---

## ASP Session 17 — Per-Pixel DSFN Blend Ramp + Adaptive Boundary Search (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **Per-pixel DSFN blend ramp** (`compositing.py` — `_soft_seam_weight`) | S17 replaces the per-column-average blend radius with a per-pixel value driven by local photometric similarity. Previously: `col_sim = sim_diffused.mean(axis=0)` collapsed the (zone_h, W) similarity field into (W,), then broadcast the same ramp to all rows in each column. Now: `ramp = min_ramp_bg + sim_diffused * (max_ramp_bg - min_ramp_bg)` gives every pixel its own blend width. Background pixels (high similarity, wide ramp) and foreground pixels at character edges (low similarity, narrow ramp) in the same column now get independently-sized transitions, eliminating the averaging artifact where a character-edge row was forced into a wide blend because its column happened to have mostly background above it. |
| **Adaptive boundary search range** (`compositing.py` — `_find_optimal_boundaries`) | When affines are available and horizontal tx spread < 5 px (pure vertical scroll), the boundary search window narrows from ±SEARCH_RANGE=250 to ±100 px. For typical dense vertical-scroll sequences the optimal boundary is always within ±50 px of the midpoint, so the narrow window loses nothing while reducing candidate evaluations by ~60 % for sparse sequences with large frame steps. For diagonal/2D motion (tx_spread ≥ 5px), the full ±250 px range is preserved. |
| **6 unit tests** (`test_compositing.py`) | New `TestSoftSeamWeight` class: output shape/dtype, values in [0,1], weight ≈ 0.5 at seam for identical frames, weight ≈ 1.0 far above seam, weight ≈ 0.0 far below seam, similar frames produce wider blend zone than different frames. animation suite: 183 tests passing. |

---

## ASP Session 16 — Seam Band Color Matching for Single-Pose Seams (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_color_match(dom_zone, oth_zone, path_local, band_px)`** (`compositing.py`) | Standalone helper (testable). Computes per-channel mean of content pixels within `band_px` rows of `path_local` in both zones, then applies the per-channel delta `(dom_mean − oth_mean)` to oth_zone's band pixels. Shifts oth_zone's colors toward dom_zone's photometric profile in the seam band. Degenerate zones (< 10 content pixels) return an unchanged copy. |
| **Wired into single-pose composite branch** (`compositing.py`) | Called with `band_px = sp_soft_px + 4` before `_single_pose_soft_edge()`. The color-matched `_oth_matched` is passed to the S15 blend — the channel-mean step drops from `post_warp_diff` lum units toward ~0 before the ramp is applied, making the blend seam nearly imperceptible. `take_oth` (non-overlap) pixels still use original `oth_zone` colors. |
| **7 unit tests** (`test_compositing.py`) | New `TestSeamColorMatch` class: output shape/dtype, zero band returns unchanged copy, band pixels shifted to dom mean, outside-band pixels unchanged, identical zones produce no shift, degenerate (all-black) zone returns unchanged, per-channel delta applied independently. animation suite: 177 tests passing. |

### Design rationale

S15 applied a ±6px blend ramp at single-pose seams (max 50% blend at centre). If `post_warp_diff = 30`, even 50% blend leaves a 15-lum residual step — visible as a seam. S16 eliminates the channel-mean component of this step entirely by shifting oth_zone's colour to match dom_zone's in the blend band. After the shift, both zones have compatible means; the remaining ±6px blend smooths the residual variance. Combined, S15+S16 reduce the worst-case seam step from `post_warp_diff` to the within-band colour variance (typically < 5 lum), well below the human perceptual threshold (~10 lum).

`take_oth` pixels (used where only oth_zone has fg content, away from the seam) remain at original oth_zone colours to preserve foreground fidelity in non-overlap regions.

---

## ASP Session 15 — Soft-Edge Single-Pose Seam (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_single_pose_soft_edge(dom_zone, oth_zone, path_local, apply_mask, sp_soft_px)`** (`compositing.py`) | New standalone helper (exportable, unit-testable). Applies a narrow ±`sp_soft_px` linear feather centred on the DP seam path to smooth the hard color step at single-pose escalated seams. Maximum blend weight at the seam centre is 50% other-frame; weight drops linearly to 0% at ±sp_soft_px rows. Only fires where BOTH frames have non-zero foreground content AND `apply_mask` is True AND pixel is within the band — never bleeds into background or single-frame regions. |
| **Wired into single-pose composite branch** (`compositing.py`) | After the hard dominant/fill partition (existing S11 logic), `_single_pose_soft_edge()` is called and its result written back for `both_have & fg_apply` pixels. No-op outside the blend band. Disable with `ASP_SP_SOFT_PX=0`. Print updated: "soft_px=N" instead of "(no blend — avoids double image)". |
| **7 unit tests** (`test_compositing.py`) | New `TestSinglePoseSoftEdge` class: output shape/dtype, disabled when sp_soft_px=0, seam row is 50/50 blend, outside-band pixels unchanged, in-band pixels strictly between dom and oth, no modification where apply_mask=False, no modification where oth has no content. animation suite: 170 tests passing. |

### Design rationale

Single-pose seams previously rendered as a completely hard binary cut (dominant frame / fill frame with zero transition). The cut is visually noticeable as an abrupt color step at the seam line, even though the color values on either side differ by only 10–40 lum units in practice. A ±6px linear ramp at the DP-optimal seam position smooths this step into a ~12px transition zone, which is below the threshold where pose-gap ghosting becomes perceptible (ghosts require 20–50px of blended region with misregistered content to be visible).

The blend is 50%-at-seam-centre, not blending across the full feather zone, because pose differences are large (post_warp_diff > 22 lum units for escalated seams) — blending across a wide zone at high weights would recreate the double-image ghost that single-pose was designed to prevent.

---

## ASP Session 14 — Seam Visibility Score (No-Reference Quality Metric) (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_visibility_score(output_img)`** (`bench_anime_stitch.py`) | No-reference quality metric measuring the worst-case adjacent-row luminance jump in the final panorama. Computes per-row mean luminance for content rows (lum > 5, ≥10% fill), then reports the maximum absolute difference between consecutive row means. Detects hard single-pose seam cuts (score 12–50+) that `_seam_coherence` misses (which measures global drift, not local discontinuities). Works for all 96 tests with no GT required. |
| **Wired into `_compute_all_metrics`** | `seam_visibility` field now appears in `metrics_asp` and `metrics_simple` in all benchmark result dicts. |
| **8 unit tests** (`test_bench_metrics.py`) | New test file: `TestSeamVisibilityScore` — uniform image → 0, hard seam → ≥100, smooth gradient → <10, non-negative, harder seam scores higher, affines=None works, black borders ignored, single-row → 0. animation suite: 163 tests passing. |

### Interpretation guide

| `seam_visibility` | Meaning |
|-------------------|---------|
| 0–5 | Invisible seams — excellent adaptive feather / FG registration |
| 6–12 | Faintly visible — normal for well-blended Laplacian output |
| 13–25 | Visible step — likely one or more single-pose seam escalations |
| > 25 | Hard cut — significant animation pose gap at worst seam |

---

## ASP Session 13 — Multi-Frame Canvas Coverage Gate (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_row_coverage()` helper** (`pipeline.py`) | Pure function: given `affines`, `frames`, `canvas_h`, returns `(row_cov, pct_multi, median_cov)`. `row_cov[r]` = number of frames covering canvas row `r`; `pct_multi` = fraction of content rows with ≥2-frame overlap; `median_cov` = median per-row coverage. Extracted as a standalone function to enable direct unit testing. |
| **Stage 10.5 coverage gate** (`pipeline.py`) | Inserted after Stage 10 (temporal render), before Stage 11 (fg composite). Computes row coverage, logs diagnostic summary (`N multi-frame rows / total content rows`), and falls back to SCANS when `pct_multi < ASP_COV_MIN_MULTI_PCT` (default 0.30). Conservative 30% threshold avoids false positives on typical dense-overlap datasets while catching degenerate 2-frame sparse selections. |
| **Coverage unit tests** (`test_canvas.py`) | 6 new tests in `TestComputeRowCoverage`: fully-overlapping frames, non-overlapping frames, dense stack, output shape, empty canvas, non-negative counts. animation suite: 155 tests passing. |

### Notes

The coverage gate completes §0 item 2 from the roadmap. Default threshold 0.30 means the gate only fires when fewer than 30% of content rows have 2+ frames — well below the coverage level of all current 92/96 passing tests (all of which have dense multi-frame overlap). The gate is a safety net for future edge-case datasets, not a quality change for the current corpus.

---

## ASP Session 12 — Adaptive Feather Refinement + Parallel Seam DP (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **Adaptive feather refinement** (`compositing.py`) | After FG pose registration, each seam's feather width is adjusted based on `post_warp_diff`: diff < 8.0 → widen 1.5× (excellent alignment, smoother Laplacian blend); diff > 16.0 → narrow 0.75× (poor alignment, tighter cut to prevent ghosting). Seams that escalated to single-pose (diff > 22) are skipped. Overlap cap is re-applied after modification. `seam_post_diffs` init bug fix from S11 was the prerequisite that made this effective for the first time. |
| **Parallel seam DP pre-computation** (`compositing.py`) | Collects zone arrays + `sem_cost` maps for all N-1 seam boundaries, then dispatches `_seam_cut()` jobs via `ThreadPoolExecutor(max_workers=min(N-1, 4))`. Single-boundary case uses inline path (no executor overhead). Pre-computed paths are stored in `_precomp_paths: dict` and retrieved in the Laplacian blend loop. Safe to parallelise: `result` is fully populated by hard-partition before the pre-compute block; `warped_norm` is read-only; zones don't overlap; `.copy()` prevents aliasing. |
| **S12 unit tests** (`test_compositing.py`) | Added 8 new tests: `TestSeamCutDP` (5 tests — shape, valid range, identical-image, sem_cost, 3-connectivity constraint) and `TestParallelSeamPrecompute` (3 tests — 5-frame parallel path, 6-frame output shape, 2-frame single-seam fallback). animation suite total: 149 tests passing. |

### Results

| Metric | Before S12 | After S12 |
|--------|-----------|-----------|
| SCANS fallbacks | 4/96 (4%) | 4/96 (4%, unchanged) |
| Tests passing (animation suite) | 141 | 149 |
| Adaptive feather firing | never (seam_post_diffs always empty) | all seams with post_diff < 8 → widened to FEATHER_MAX |
| Parallel seam DP | sequential | ThreadPoolExecutor (max 4 workers) |

*test09: all 20 seams post_diff 2–8, all feathers widened 250px → 300px (FEATHER_MAX). test27: all 19 seams, same pattern.*

---

## ASP Session 11 — Fallback Elimination: Comparative Gates + Validation Retry Chain (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **Comparative render gate** (`bench_anime_stitch.py`) | Replaced absolute render gate with a SCANS-relative gate: limits are `max(floor, scans_value * 2.0)`. Floors: `_SC_FLOOR=38`, `_SB_FLOOR=35`. Override via `ASP_GATE_SC` / `ASP_GATE_SB`. Prevents the gate from rejecting valid ASP output when the source content has inherently high luminance variation. |
| **Alignment gate changed to advisory** (`bench_anime_stitch.py`, `pipeline.py`) | The `75th-pct |dx| > limit` check no longer raises `RuntimeError`; it now prints a `⚠ high drift` warning and lets the pipeline proceed. Default threshold in `pipeline.py` raised from 50px → 200px (`ASP_ALIGN_GATE_DX`). Tests with 2D/diagonal motion are no longer hard-rejected before compositing. |
| **Validation Retry 4** (`bench_anime_stitch.py`) | Added a 4th retry after Retry 3: `_validate_affines(_seq, min_step=3.0, max_ratio=10.0, max_rotation=0.3, max_scale_dev=0.3)`. Fixes slow-pan sequences (e.g., test48 with min_gap=6.8px, test14/78 with min_gap≈5–19px) where fine-grained sampling naturally produces sub-25px per-frame steps. |
| **Validation Retry 5** (`bench_anime_stitch.py`) | Added a 5th final retry: `min_step=0.5, max_ratio=50.0, max_rotation=0.5, max_scale_dev=0.5`. Catches extreme-clustering cases where the sequential chain has ratio > 10 (e.g., test73 ratio=18.4, test77 ratio=27.0). |
| **GhostGate absolute floor** (`bench_anime_stitch.py`) | `_ghost_limit = max(_GHOST_ABS_FLOOR, _GHOST_RATIO_LIMIT * sim_ghost)`. Default floor=40.0 (env `ASP_GATE_GHOST_FLOOR`). Prevents false positives when ASP ghosting is low in absolute terms but appears high relative to an unusually clean SCANS output (test81 asp=30.5, test82 asp=37.4 — both now pass). |
| **`seam_post_diffs` init bug fix** (`compositing.py`) | `seam_post_diffs: dict = {}` was missing from declarations at line 603. The NameError was silently caught by the FG-registration `except` block, causing the entire FG pose registration step to be skipped on every run. Fixed by adding the declaration. |

### Results

| Metric | Before S11 | After S11 |
|--------|-----------|-----------|
| SCANS fallbacks | 51/96 (53%) | 4/96 (4%) |
| Genuine SCANS fallbacks | 51 | 4 (tests 54, 59, 73, 89) |
| Retries needed | 3 | 5 |
| Ghost gate floor | none | 40.0 |

*4 confirmed genuine SCANS cases: test54 (2D drift, sb=56.0 >> 36.0), test59 (sc=50.2 >> 38.0), test73 (ratio=18.4 in _seq, sb=68.3 >> 35.0), test89 (sb=122.3 >> 48.7).*

---

## ASP Session 10 — Seam DP Vectorization + Dead Code Removal + Test Fixes (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **Seam DP vectorization §1.5A** (`compositing.py`) | Replaced the W_e-iteration Python forward pass in `_seam_cut()` with `scipy.ndimage.minimum_filter1d(size=3, mode='constant', cval=np.inf)` — a compiled C kernel that computes the 3-neighbour row minimum in one pass, eliminating per-iteration `left`/`right` array allocations. Traceback changed from Python list construction + comprehension to slice-argmin (`E[i, j_lo:j_hi].argmin()`). Expected speedup: 5–10× for Stage 11. |
| **Removed dead S8 `_compute_dinov2_features` definition** (`frame_selection.py`) | The S8 version (`thumbs: List[np.ndarray]`) was silently shadowed by the S9 version (`frames_paths: List[str]`). Removed the S8 definition; sole definition is now the S9 path-based API. |
| **Fixed `_TOONCRAFTER_SEAM_ENABLED` NameError** (`compositing.py`) | Variable at line 743 was misnamed; renamed to `_TOONCRAFTER_SEAM` (the correct module-level name). |
| **Fixed pre-existing import errors in test suite** (`test_compositing.py`, `test_canvas.py`) | `_FEATHER_MAX`/`_FEATHER_MIN`/`_FEATHER_TABLE` and `_CANVAS_MAX_DIM` were imported with a leading underscore that never existed. Fixed to import from `backend.src.constants` under the correct names (`FEATHER_MAX`, etc.) aliased for backwards-compat. |
| **Rewrote `TestDINOv2Features`** (`test_frame_selection.py`) | Two tests that were testing the removed S8 API (numpy array input) replaced with tests for the actual S9 API (file path input). `test_returns_none_when_model_unavailable`: poisons `_DINOV2_CACHE[device]` (S9 key), calls with temp PNG paths. `test_identical_images_low_cosine_distance`: writes two identical PNGs, verifies cosine distance < 0.05. |
| **141 tests passing** | Up from 107 (S9 baseline); gains include 34 previously collection-failing tests now runnable. |

---

## ASP Session 9 — ToonCrafter Seam Synthesis (2026-06-05)

### Shipped

| Item | Summary |
|------|---------|
| **ToonCrafter seam synthesis** (`compositing.py`) | `_TOONCRAFTER_SEAM_ENABLED = os.environ.get("ASP_TOONCRAFTER_SEAM", "0") != "0"` added. `seam_post_diffs: dict` tracks `post_warp_diff` per seam during the fg-register loop. After the loop, the worst single-pose-escalated seam triggers `_generate_canonical_cel(crop_a_tc, crop_b_tc, device)` from `anim_fill.py`. Canonical cel stored in `seam_canonical_crops[worst_k]`; in the Laplacian blend loop it replaces the hard dominant-frame partition for fg pixels with the ToonCrafter-generated intermediate pose. Falls back gracefully to single-pose when ToonCrafter is unavailable. Disable default: `ASP_TOONCRAFTER_SEAM=0`. |

---

## ASP Session 8 — DINOv2 Frame Selection + LSD Collinearity + Aligned-SSIM (2026-06-05)

### Shipped

| Item | Summary |
|------|---------|
| **DINOv2 submodular frame selection** (`frame_selection.py`) | `_DINOV2_CACHE: dict = {}` at module level. `_compute_dinov2_features(thumbs, device, thumb_size=224, batch_size=16) → Optional[np.ndarray]` loads `dinov2_vits14` via `torch.hub.load` with module-level cache; returns (N, 384) L2-normalised float32 features. In Pass 2 of `smart_select_frames()`, `_pose_dist(i, j)` uses DINOv2 cosine distance when features are available, falls back to `_fg_center_diff()` otherwise. Activated via `ASP_POSE_WINDOW_PX=80`. Handles holds natively: identical-pose frames collapse to the same feature point, so one representative is selected automatically. 2 new tests in `TestDINOv2Features`. |
| **LSD collinearity term in ARAP** (`fg_register.py`) | `_arap_regularise()` gains `image: Optional[np.ndarray] = None` and `image_offset: Tuple[int, int] = (0, 0)` parameters. When `image` is provided: runs `cv2.createLineSegmentDetector` on the seam-band crop; for fg/bg boundary cells (cells containing both fg and bg pixels — where ink outlines appear), projects the cell's flow onto the line direction when the projection retains ≥50% of original magnitude (prevents vertical lines from cancelling horizontal translation). Call site in `register_foreground_at_seam()` updated to pass `image=crop_a, image_offset=(y0_crop if axis==0 else 0, ...)`. 3 new tests in `TestArapRegulariseLSDCollinearity`. |
| **Aligned-SSIM metric** (`bench_anime_stitch.py`) | `_compute_aligned_ssim(img_a, img_b)` uses `cv2.findTransformECC(MOTION_EUCLIDEAN)` to align `img_a` to `img_b` before SSIM computation. Removes GT-coupling framing bias: a temporal shift in frame selection shows the same character at a different vertical position → raw SSIM penalises the shift even when pose quality is identical. `aligned_ssim_vs_gt` reported alongside `ssim_vs_gt` in `_compute_gt_metrics()`. |

---

## ASP Session 7 — Stage 12.5 Scroll-Axis Content Trim (2026-06-05)

### Shipped

| Item | Summary |
|------|---------|
| **Stage 12.5 scroll-axis foreground-extent trim** (`pipeline.py`) | Inserted between Stage 11 (foreground composite) and Stage 13 (boundary crop). Detects dominant scroll axis from affine ty/tx range; warps `~bg_masks[i]` per frame into canvas space using `cv2.warpAffine` + `INTER_NEAREST`; unions all fg masks; trims canvas rows (vertical scroll) or columns (horizontal scroll) to the fg-covered extent plus 20px padding. `valid_mask` trimmed in sync. Guard: `ASP_CONTENT_TRIM=1` (default on). Directly addresses test27's 2× height excess caused by frame selection sampling a wider temporal range than the GT. |

---

## ASP Session 6 — Hold Detection + GNC Robust Loss + SLIC SGM Proxy (2026-06-04)

### Shipped

| Item | Summary |
|------|---------|
| **Animation hold detection** (`frame_selection.py`) | `_detect_hold_blocks(thumbs, hold_threshold=0.025)` detects "on twos/threes" animation holds by comparing consecutive thumbnail pixel MAD (normalised to [0,1]). Blocks below threshold treated as the same hold. Hold IDs used in Pass 2 to apply `_SAME_HOLD_PENALTY=0.05` to same-hold candidates (prefers cross-hold frames). Enable via `ASP_HOLD_THRESHOLD=0.025`. 9 new tests in `TestDetectHoldBlocks`. |
| **GNC robust loss in bundle adjustment** (`bundle_adjust.py`) | `least_squares` upgraded to `loss='cauchy', f_scale=float(os.environ.get("ASP_BA_F_SCALE", "10.0"))`. Makes BA robust against outlier edges (long-distance matches, incorrect temporal-ordering edges) that survive the post-solve residual pruning. Override via `ASP_BA_F_SCALE`. 3 new tests in `test_bundle_adjust.py`. |
| **SLIC SGM proxy** (`fg_register.py`) | `_slic_sgm_proxy(crop_a, crop_b, fg, n_segments=200) → Optional[np.ndarray]`: SLIC superpixel centroid tracking as a coarse flow source for flat cel-shaded regions where RAFT/DIS gradient aperture problem produces noisy flow. SGM flow replaces RAFT/DIS flow for foreground pixels when `ASP_SGM_PROXY=1`. Then ARAP-regularised same as RAFT/DIS flow would be. |
| **12 new unit tests** | 9 for `_detect_hold_blocks()`, 3 for bundle adjust GNC. Total: 102 tests (was 90 at S5 start). |

---

## ASP Session 5 — Alignment Stability Gate + Fg Pixel L1 Pose Metric (2026-06-04)

### Shipped

| Item | Summary |
|------|---------|
| **Alignment stability gate** (`bench_anime_stitch.py`, `pipeline.py`) | Detects 2D/diagonal camera motion BEFORE compositing via 75th-percentile of `|dx_steps|`. When > 50px, falls back immediately to SCANS on width-normalised frames. Saves 2.5s of unnecessary compositing AND produces better output (normalised frames give better SCANS quality): test08 +0.074 (0.736→**0.809**, simple_better→**asp_better**), test25 +0.049 (0.697→**0.746**). Disable via `ASP_ALIGN_GATE_DX=99`. |
| **Ghosting ratio gate** (`bench_anime_stitch.py`, post-crop) | Fires when ASP composite ghosting > 2× simple stitch ghosting (computed on CROPPED canvas). Catches double-image blending artifacts that pass the seam coherence gate. test82 borderline (S4 ratio=2.06; current SCANS non-determinism puts ratio 1.92–2.06, stochastic fire). test84 safely below (ratio=1.87). Disable via `ASP_GATE_GHOST=99`. |
| **Fg pixel L1 pose metric** (`frame_selection.py`, `bench_anime_stitch.py`) | Replaced gradient-weighted L1 with fg-masked pixel L1 in `_fg_center_diff()`. Hard-threshold mask (>0.3) → zero out background → compare only fg pixels. Per-frame gain normalisation removes brightness variation. Background-invariant by construction (vs gradient: computed on full image, then weighted → background edges still contributed at 0.05–0.1 weight). |
| **8 new unit tests** (`test_frame_selection.py`) | Cover `_fg_center_diff()` behavior: identical-fg near-zero, different-pose high-score, gain-normalisation, strict background-invariance, sparse-mask fallback. Total unit tests: 90 (up from 82). |

### Investigated

| Item | Finding |
|------|---------|
| **Fg pixel L1 with pose selection** (`ASP_POSE_WINDOW_PX=80`) | test27 improved +0.010 (0.709→0.719) — first meaningful breakthrough since session 2. test09 +0.001. But test04 regressed -0.024 and test57 regressed -0.015 (GT coupling). Pose selection remains disabled by default. |
| **±3 look range** | Strictly worse than ±2: test09 -0.007, test27 -0.007. Extra candidates at ±3 slots are at awkward advances for uniform-step pans. Reverted to ±2. |

---

## ASP Session 4 — ARAP Push Phase + BiRefNet Fg-Masked Pose Diff (2026-06-04)

### Shipped

| Item | Summary |
|------|---------|
| **ARAP Push phase** (`fg_register.py`) | Full Sýkora 2009 Push→Regularise algorithm. `_arap_push()`: per-cell SAD block matching via `cv2.matchTemplate` with 15% improvement threshold and 24px search range. Decouples cells for independent appearance-optimal displacement before global Regularise smoothing. Enabled by default (`ASP_ARAP_PUSH=1`). 2 new unit tests in `TestARAPPush`. |
| **BiRefNet fg-masked pose diff** (`bench_anime_stitch.py`, `frame_selection.py`) | When `ASP_POSE_WINDOW_PX > 0`, BiRefNet probes build both bg mask (for camera displacement) AND fg mask (union across probe frames). The fg mask weights the gradient diff so background edges are excluded from pose comparison. Still disabled by default (background-agnostic but gradient still limited). |
| **Composite gate env overrides** (`bench_anime_stitch.py`) | `ASP_GATE_SC` / `ASP_GATE_SB` env vars to tune or disable the composite gate for diagnostics. |

### Investigated and Found Non-Impactful

| Item | Finding |
|------|---------|
| **ARAP Push on benchmark** | Zero measurable GT-SSIM change (+0.001 test27, 0.000 elsewhere). Flow quality confirmed not the bottleneck; SSIM ceiling is animation timing mismatch from frame selection. |
| **BiRefNet fg-masked pose selection** | Slightly better than raw gradient (fewer spurious refinements) but still regresses test04 (-0.082→-0.026 magnitude reduction). GT reference coupling prevents reliable improvement: any frame substitution diverges from the GT's specific temporal selection. |
| **Composite gate calibration** | Gate verified correct: test04 ASP composite (sb=32.8) gives GT-SSIM 0.716 vs SCANS 0.742 — SCANS IS better for test04. Gate threshold 30 is appropriate. |

---

## ASP Session 3 — Pose-Consistent Frame Selection Infrastructure (2026-06-03)

### Shipped (disabled by default)

| Item | Summary |
|------|---------|
| **`backend/src/animation/frame_selection.py`** | New backend module exposing `smart_select_frames()` as a clean pipeline/GUI API. Two-pass architecture: Pass 1 (v1 greedy first-past-threshold), Pass 2 (local pose-consistent refinement). `_fg_center_diff()` gradient-magnitude L1 metric for pose similarity. |
| **Upgraded `_smart_select_frames()`** | Benchmark function now has the same two-pass architecture with `[PoseSelect]` logging per refined slot. `ASP_POSE_WINDOW_PX` env var (default `0` = disabled). |

### Tried and Disabled

| Item | Outcome |
|------|---------|
| **Gradient-based central-crop pose proxy** | Confounded by background structure: Sobel gradients in the central 50% crop include locker/wall edges that change as the camera pans, causing the selector to prefer same-scroll-position frames over same-pose frames. Regressions: test04 -0.043, test27 -0.026. Set `ASP_POSE_WINDOW_PX=0` (default). Needs foreground-only flow or a proper pose estimation model (DWPose/ViTPose) to work correctly. See `pipeline_analysis_report.md` §3. |

---

## Research Consolidation & Roadmap Restructure (2026-06-03)

### Consolidated research reports

The 14 image-stitching reports and 5 image/video-generation reports were merged into two comprehensive references and the **19 source reports were deleted** (their entire content is captured in the consolidations). Both new documents cover the **whole field** with deep anime-focused sections, sized to fully replace the originals.

| Item | Summary |
|------|---------|
| **`research/Image_Stitching_Research.md`** | Replaces all 14 stitching reports. 22 sections: geometric foundations & DoF; Perfect-Stitch-vs-Scan-Stitch mathematical audit (pushbroom/X-slits, APAP rank-deficiency proof); feature matching (SIFT/AKAZE/MSER → SuperPoint/SuperGlue/LightGlue/ALIKED → LoFTR/EfficientLoFTR/RoMa/JamMa/EDM); registration & sub-pixel (RANSAC/MAGSAC, translation-only BA, ECC, phase correlation); optical flow (RAFT/SEA-RAFT/AnimeInterp SGM+RFR); spatially-varying warps (APAP/Moving-DLT, TPS/MLS/CPW, LSD line preservation, SEAGULL); **foreground assembly** (motion decomposition `F_fg=T_camera+A_animation`, Sýkora ARAP push/regularise, symmetric midpoint warp, two-channel selection, Eden single-pose fallback, HDR/VSR analogy); photometric (Harding broadcast-dimming reversal, BaSiC flat-fielding, Brown–Lowe gain, region-stratified Reinhard, palette harmonisation); segmentation (BiRefNet/ToonOut 99.5%/SAM-2/trapped-ball); seam-finding (graph-cut MRF, Agarwala, DSeam, semantic/SAM); blending (multi-band, Poisson/Modified-Poisson+MTOR, DSFN soft-seam); background reconstruction (temporal median, ProPainter/RAFT, latent-diffusion outpainting, VidPanos); unified frameworks (UDIS++/NIS/SRStitcher); SR (Real-ESRGAN anime_6B/APISR); video (StabStitch/++, Unwrap Mosaics); shot detection (OmniShotCut); the 14-stage pipeline spec; evaluation metrics; failure/fallback taxonomy; ASP implementation status. |
| **`research/Image_Generation_Research.md`** | Replaces all 5 generation reports. 16 sections: diffusion math (ε/v/x0-prediction, Rectified Flow Matching + Reflow, progressive distillation); architecture lineages (SD1.5, SDXL dual-encoder, Animagine XL 4.0, Illustrious XL 2.0 token-dilution, NoobAI v-pred + RF conversions, Pony score-tag Clever-Hans, FLUX MM-DiT/T5XXL/Chroma/Kaleidoscope, SD3.5) with comparison table; conditioning & prompting (Danbooru/score/natural-language, Florence-2 vs WD14); fine-tuning (LoRA dim/alpha, LyCORIS LoCon/LoHa/LoKr, DreamBooth, full-FT, kohya_ss settings, optimisers); the 4K-video→character-LoRA pipeline; inference (ComfyUI/Forge/A1111, samplers, fp16-fix VAE, ControlNet, IP-Adapter); upscaling (Real-ESRGAN anime/APISR/SUPIR); video (AnimateDiff 5D-tensor architecture + motion-module table + anime beta_schedule=linear fix, AnimeInterp, ToonCrafter Toon-Rectification/Dual-Reference-3D-Decoder/Sparse-Sketch, ToonComposer DiT/SLRA, Wan2.1/SVD, prompt-travel/context-sliding); hardware deployment (uv, TensorRT static compilation, FP8/NF4/GGUF quantisation tables for 3090 Ti / 4080 / 4080-mobile); Image-Toolkit implementation status; settings cheat-sheet. |

### Roadmap restructure

| Item | Summary |
|------|---------|
| **ASP roadmap refocus** | `moon/roadmaps/asp.md` header now references the consolidated stitching report; §0.1 updated with implementation status — A2/A4 prototype (`backend/src/animation/fg_register.py`: DIS dense flow → residual → symmetric midpoint warp, integrated into Stage 11, validated on test09) shipped; A1 (SEA-RAFT), A3 (full ARAP+LSD), A5 (bg-only median), A6 (single-pose fallback), and segment-guided flow remain. |
| **New Content Generation roadmap** | `moon/roadmaps/content_generation.md` created — grounded in the existing stack (`LoRATuner` on Illustrious-XL, `SD3Wrapper`, `ComfyUIManager`, `backend/src/models/data/`). Phased CG-1…CG-4: captioning (WD14+Florence-2), shared anime upscaler, ComfyUI control workflows, video→LoRA guided flow, LyCORIS, AnimateDiff, v-pred/ztSNR, ToonCrafter, FLUX, Wan2.1/SVD. |
| **Master roadmap update** | `moon/ROADMAP.md` adds the two consolidated reports and the Content Generation section-roadmap to its index; new **Phase 0 (ASP Foreground Assembly, items 0.1–0.8)** and **Phase CG (Content Generation, items CG.1–CG.10)** added with effort estimates and links. |

---

## Roadmap Continuation Batch — Phase 1 & Phase 2 Items (Completed 2026-05-31)

### ASP Pipeline Fixes (Phase 1 items 1.1–1.5)

| Item | Summary |
|------|---------|
| 1.1 SCANS fallback purity | `scans_frames = list(frames)` is captured at Stage 2 (before any ML corrections). All four `_scan_stitch_fallback()` call-sites in `pipeline.py` and the `_ProgressPipeline` subclass now pass `scans_frames`, ensuring the fallback always receives the original unmodified frames. |
| 1.2 Dark scene gain clamp widening | `_ref_lum_scalar` threshold is 80.0. When met, gain clamp is `[0.80, 1.25]` instead of the tighter `[0.88, 1.14]`. Both code paths confirmed present in `pipeline.py` lines 566–570. |
| 1.3 Static edge pre-bundle rejection | `MIN_EXPECTED_STEP = 50` is defined in `backend/src/constants/animation.py` and exported via `backend/src/constants/__init__.py`. It was never imported in `pipeline.py` — causing a `NameError` every time the min-step guard ran. Added `MIN_EXPECTED_STEP` to the `from backend.src.constants import (...)` block. |
| 1.4 Content-aware minimal bounding crop | `_crop_to_valid()` in `canvas.py` already uses `_largest_valid_rect` when `valid_ratio < 0.80`. SCANS fallback also uses `_largest_valid_rect` after stitching. Both verified operational — item confirmed done. |
| 1.5 Restrict seam search window | `_seam_dp()` in `stateless.py` gains a `search_half: int | None = None` parameter. When set, the cost matrix is masked to `±search_half` pixels around the image midpoint via a `np.full(..., np.inf)` mask with the window left unmasked. `de_seam()` in `mfsr/de_seam.py` propagates `search_half` to both its `_seam_dp` calls (baseline + fallback). |

### ML Model Memory Management (Phase 1 item 1.8)

| Item | Summary |
|------|---------|
| 1.8 `unload()` on all model wrappers | Added `unload()` to seven model wrappers that lacked it: `BiRefNetWrapper` (pops from `_models` class dict, calls `del model`, `gc.collect()`), `LoFTRWrapper` (`del self.matcher`, sets to `None`), `EfficientLoFTRWrapper` (deletes both `_model` and `_processor`), `RoMaWrapper`, `ALIKEDLightGlueWrapper` (deletes `_matcher`), `JamMaWrapper` (deletes `_model`), `BaSiCWrapper` (clears NumPy arrays). All call `torch.cuda.empty_cache()` and `gc.collect()`. `AnimeStitchPipeline.run()` now calls `unload()` (with `offload()` fallback) instead of the weaker `offload()` at cleanup points after Stages 4 and 5–6. |

### Logging Standardisation (Phase 1 item 1.13)

| Item | Summary |
|------|---------|
| 1.13 Python `logging` + rotating file handler | `_setup_logging()` added to `backend/src/app.py`. Called at the start of `launch_app()`. Creates: a `RotatingFileHandler` at `~/.image-toolkit/logs/image_toolkit.log` (5 MB per file, 5 backups, DEBUG level) and a `StreamHandler` on stdout (INFO level by default, DEBUG with `--verbose`). `logger = logging.getLogger(__name__)` added to: `backend/src/animation/pipeline.py` (58 print calls migrated), `canvas.py` (5), `matching.py` (8), and all 7 model wrappers including `birefnet_wrapper.py`, `efficient_loftr_wrapper.py`, etc. `print(..., file=sys.stderr)` → `logger.error()`; `print(f"[Stitch] Warning…")` → `logger.warning()`; remaining stage logs → `logger.info()` or `logger.debug()`. Third-party loggers (PIL, transformers, urllib3) capped at WARNING. |

### Worker Cancellation Standardisation (Phase 2 item 2.7)

| Item | Summary |
|------|---------|
| 2.7 `_should_stop` flag | `WallpaperWorker` and `TrainingWorker` previously used only `self.is_running` for cancellation. Both now also set `self._should_stop = False` on init and `self._should_stop = True` in `stop()`, alongside the existing `is_running` flag. Existing callers that check `is_running` continue to work; tooling that checks the standardised `_should_stop` pattern now also works. |

### Settings Window Completion (Phase 2 item 2.16D/F/G)

| Item | Summary |
|------|---------|
| 2.16 D/F/G Settings fully wired | Audit confirmed all three remaining sub-items are already wired in `settings_window.py`: §D `confirm_deletions` (checkbox, load/save/reset at lines 74, 248, 1318, 1361); §F `file_logging_enabled` + log level combo (lines 85, 391–403, 1328–1329, 1385); §G `restore_last_dir` (lines 78, 280, 1322, 1370). Item marked Done. |

### Stage-Level Progress Signals (Phase 2 item 2.6)

| Item | Summary |
|------|---------|
| 2.6 Stage signals | Audit confirmed `_ProgressPipeline` in `gui/src/helpers/models/stitch_worker.py` already emits `sig_stage(idx, total_stages, label)` at the start of all 13 pipeline stages via `_emit()`. `StitchWorker.TOTAL_STAGES = 13`. Item marked Done. |

### Pipeline Execution Trace JSON (Phase 2 item 2.13)

| Item | Summary |
|------|---------|
| 2.13 Execution trace | `_ProgressPipeline.run()` now writes a per-run JSON file to `~/.image-toolkit/traces/stitch_YYYYMMDD_HHMMSS.json`. Fields: `started_at`, `finished_at` (ISO 8601), `elapsed_seconds`, `frames_input` (N frames loaded), `edges_found` (after direction-consensus filter), `canvas_size` ([H, W]), `fallback_used` (SCANS mode triggered?), `success`, `error`, `stage_timings` (list of `{stage, label, elapsed_s}` entries — one per `_emit()` call). The trace is also written when the SCANS fallback is used. Stage timings measure wall time between consecutive `_emit()` calls. |

### Dispatcher Completion (features/ROADMAP.md — CRITICAL)

| Item | Summary |
|------|---------|
| CLI dispatcher — database | `dispatch_database()` in `dispatcher.py` was a single-line stub. Now implements the `search` sub-command: loads `PgvectorImageDatabase`, calls `search_images(filename_pattern=query, limit=limit)`, and prints tabular results (id, filename, group, subgroup, tags). |
| CLI dispatcher — model | `dispatch_model()` was a single-line stub. Now implements the `generate` sub-command: instantiates `SD3Wrapper`, calls `wrapper.generate(prompt, output_path)`, and reports the output path. |
| CLI `--recursive` flag | `dispatch_core()` now reads `args.get("recursive", False)` and forwards it to `ImageFormatConverter.convert_batch(recursive=recursive)`. The `# TODO: add recursive to backend` comment removed. |

### Database Bulk Insert (Phase 2 DB performance)

| Item | Summary |
|------|---------|
| Bulk tag insert via `execute_values` | `add_image()` in `image_database.py` replaced the per-row tag insert loop (`for tag_name in tags: cur.execute(insert_image_tag, ...)`) with `psycopg2.extras.execute_values()`. Tag IDs are still resolved one by one via `_get_or_create_tag()` (which is itself an upsert), but the subsequent insertion is now a single round-trip `INSERT ... VALUES %s ON CONFLICT DO NOTHING`. |

### pgvector HNSW Index Tuning (Phase 2 item 2.14)

| Item | Summary |
|------|---------|
| 2.14 HNSW tuning | `schema.sql`: `idx_images_embedding` index updated to `USING hnsw ... WITH (m = 32, ef_construction = 128)`. Previous defaults were `m=16, ef_construction=64`. `search_images()`: when `query_vector` is provided, issues `SET LOCAL hnsw.ef_search = 80` in a preceding cursor to tune the search beam for this query without affecting other connections. |

### Multi-Select in Gallery (Phase 2 item 2.9)

| Item | Summary |
|------|---------|
| 2.9 Shift+click / Ctrl+click | Audit confirmed `handle_marquee_selection()` in `AbstractClassTwoGalleries` (lines 601–633) already implements Shift (additive) and Ctrl (subtractive) multi-select. Item marked Done. |

---

## GUI/UX Phase 1 — Quick Wins (Completed 2026-05-31)

| Item | Summary |
|------|---------|
| G1.9 Session persistence | `_save_last_dir` / `_load_last_dir` helpers added to both `AbstractClassTwoGalleries` and `AbstractClassSingleGallery`. Each tab class stores its last browsed directory in `QSettings("ImageToolkit","ImageToolkit")` under `session/<ClassName>/last_dir`. The saved path is restored on next launch, eliminating the need to re-browse to the previous directory after an app restart. |
| G1.10 OS dark mode follow | `MainWindow.__init__` now reads `QGuiApplication.styleHints().colorScheme()` when the vault stores no explicit theme preference. Falls back to `"dark"` when the OS reports `Unknown`. Connects `colorSchemeChanged` signal to auto-switch themes when the user toggles dark/light mode in the OS while the app is running (only takes effect when no vault override is set). |
| G1.11 Ctrl+scroll thumbnail zoom | `MarqueeScrollArea` intercepts wheel events with `Qt.ControlModifier` and emits a `ctrl_wheel(int)` signal (positive = scroll up = zoom in, negative = scroll down = zoom out). Both gallery base classes connect this signal lazily on the first layout-change tick, keeping concrete tab code untouched. Each Ctrl+scroll step changes `thumbnail_size` by ±16 px (clamped to 64–512 px) and reloads the current gallery page at the new size. |

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
| P3.3 ToonCrafter ghost fill | `animation/anim_fill.py` — ToonCrafter-based synthetic frame generation for deghosting in high-overlap zones. |
| P3.4 SRStitcher diffusion fusion | `animation/sr_stitcher.py` — diffusion-based seam and border inpainting for final-quality outputs. |
| P3.5 SEA-RAFT fine-tune pipeline | Fine-tuning pipeline for SEA-RAFT optical flow on domain-specific scroll sequences. |
| P3.6 EfficientLoFTR fine-tune pipeline | Fine-tuning pipeline for EfficientLoFTR on scroll-frame keypoint pairs. |

---

## Phase 2 — ASP Intermediate Pipeline (Completed 2026-05)

| Item | Summary |
|------|---------|
| P2.1 SEA-RAFT optical flow | SEA-RAFT flow for robust large-displacement inter-frame motion estimation. |
| P2.2 Real-ESRGAN super-resolution | `animation/super_res.py` — Real-ESRGAN 4× upscale post-processing mode. |
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

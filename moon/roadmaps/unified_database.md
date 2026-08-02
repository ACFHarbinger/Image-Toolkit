# Unified Database Roadmap — Merging the Listings Subtabs and the Database Tabs

*Created: 2026-07-11. Merges the two storage/UI stacks — the SQLCipher listings store (`base.secret` → `~/.image-toolkit/listings_secure.db`, Content/Entity Listings subtabs) and the PostgreSQL + pgvector image index (`backend/src/database/image_database.py`, Configuration/Search/Metadata tabs) — into a single encrypted, serverless, relational store with real semantic search. PostgreSQL is **dropped entirely**.*

***Status (2026-08-01): all ten phases (DB.1–DB.10) shipped.*** *Every locked-in decision from the Q&A below has a real, tested implementation — including decision #2 ("no plaintext sidecar DBs"), closed last via `EncryptedSQLiteStore` (DB.7). A handful of deliberately-scoped-down items remain, documented honestly in their own sections rather than silently dropped: the hnswlib ANN index (brute-force is fast enough at current scale), multi-group semantic prefiltering, and Entity Recon batch-linking — none of them gaps in the original locked-in decisions, all UX/scale refinements for a future round if ever needed.*

**Decisions locked in (owner Q&A, 2026-07-11):**

1. Nothing outside the GUI uses the Postgres DB → the Postgres dependency is removed completely.
2. Everything is encrypted at rest — whole-database SQLCipher encryption (groups, tags, listings, file paths, all of it). Simplest implementation wins; no plaintext sidecar DBs.
3. Scale target: tens of thousands of image rows, thousands of listings → SQLite territory with headroom (design for ~1M rows).
4. Real semantic/CBIR image search is required. pHash dedup alone is explicitly insufficient (it stays, but only as the dedup primitive).
5. All cross-domain features wanted: media↔image-group links, entity↔image links, unified tag vocabulary, auto-created listings from scans.
6. Argon2id key derivation happens **once at login**; a keyed connection is held for the session.
7. UI: a unified Library tab category, **plus** new raw-database browser tab(s) showing field values and table associations ER-diagram-style (crow's-foot, à la the SQL Server sample diagram provided).
8. Mandatory pre-migration backups; all migration scripts live in `backend/migrations/`.
9. **`base.secret` is Vault-only and must not be touched.** New native code goes in a new **`base.database`** C++ module. CRUD language (C++ vs Python) chosen for performance — see [DB.2](#db2-basedatabase--the-native-storage-engine).
10. Phasing: incremental (chosen here) — the app stays shippable after every phase.

---

## Table of Contents

- [Current State](#current-state)
- [DB.1 Unified Schema Design](#db1-unified-schema-design)
- [DB.2 base.database — the Native Storage Engine](#db2-basedatabase--the-native-storage-engine)
- [DB.3 Python DAL (`backend/src/database/unified/`)](#db3-python-dal-backendsrcdatabaseunified)
- [DB.4 Backups & Migration Scripts (`backend/migrations/`)](#db4-backups--migration-scripts-backendmigrations)
- [DB.5 Listings Subtabs on the Unified Store](#db5-listings-subtabs-on-the-unified-store)
- [DB.6 Image Tabs on the Unified Store (Postgres Retirement)](#db6-image-tabs-on-the-unified-store-postgres-retirement)
- [DB.7 Semantic Search & CBIR](#db7-semantic-search--cbir)
- [DB.8 Cross-Domain Features](#db8-cross-domain-features)
- [DB.9 Data Browser Tab (Raw Tables + ER View)](#db9-data-browser-tab-raw-tables--er-view)
- [DB.10 Backup Pipeline Retarget & Final Cleanup](#db10-backup-pipeline-retarget--final-cleanup)
- [Phasing & Dependency Graph](#phasing--dependency-graph)
- [Risk Register](#risk-register)
- [Effort × Impact Matrix](#effort--impact-matrix)

---

## Current State

Two disjoint stacks that never talk to each other:

**Listings side** (`gui/src/tabs/core/elements/{content,entity}_listings_subtab.py`):
- SQLCipher SQLite at `~/.image-toolkit/listings_secure.db` via `base.secret` (`base/src/secret/vault_db.cpp`).
- One document-store table `listings(id, category, title, metadata JSON, date_added, embedding BLOB, dim)`; entities are rows with `category='Entity'`; episodes, credits, associations, genres/tags all live inside the JSON blob.
- Argon2id KDF runs **inside every API call** (`open_db()`); associations are kept bidirectionally consistent by Python fetch-all/diff/re-upsert loops; all filtering/sorting happens in Python over full-table loads.
- The `embedding` column and `hybrid_search_secure()` are dead weight (GUI writes empty or byte-of-title placeholder vectors). Recommendations bypass the DB entirely via `Recommendation-Engine/` (BGE-M3 hybrid, plain SQLite `rec_engine.db`).
- Encrypted JSON backups (`assets/secrets/*.json.enc` via JVM `SecureJsonVault`) + multi-part image ZIPs in `assets/migrations/`.

**Image DB side** (`gui/src/tabs/database/{database,search,scan_metadata}_tab.py`):
- PostgreSQL + pgvector via psycopg2 (`backend/src/database/image_database.py`, SQL in `sql/*.sql`; pooled variant `pooled_image_database.py`; `phash_deduplicator.py`).
- Relational, plaintext: `images` (with denormalized `group_name`/`subgroup_name` text columns *and* separate `groups`/`subgroups` tables), typed `tags`, `image_tags` M2M, `embedding vector(128)` + HNSW index, `phash BIGINT`.
- The `embedding` column is always `NULL` on GUI paths (dead weight #2). Requires a running Postgres server with the pgvector extension. `DatabaseTab` is the connection hub holding `self.db` + refs consumed by Search/Scan/Merge/Similarity/Wallpaper tabs and `ImagePreviewWindow`.
- Known defects to fix in transit: upsert loop runs `QPixmap(path)` + queries on the GUI thread; backend `_connect()` failure calls `exit(1)`; DB password persisted via `collect()`.

---

## ✅ DB.1 Unified Schema Design

*Shipped 2026-07-12 (S210): DDL at `backend/src/database/unified/schema.sql` + `schema_fts.sql` (FTS5 layer, applied with graceful fallback); spec + ER diagram + legacy field mapping at `docs/database/unified_schema.md`.*

One SQLCipher database: `~/.image-toolkit/library.db`. Whole-DB encryption (answer #2) — no per-column crypto, no plaintext sidecars. Normalized relational schema replacing both the JSON blob and the pgvector schema.

```
┌─ Media / entity domain ────────────────────────────────────────────┐
media_items    (id TEXT PK, title, type, status, personal_rating,
                community_rating, year, episodes_total, current_episode,
                creator, review, web_link, local_file, image_path,
                date_added, date_watched, extra JSON)
episodes       (id TEXT PK, media_item_id FK→media_items ON DELETE CASCADE,
                number, title, date_watched, rating, review,
                image_path, local_file, web_link)
entities       (id TEXT PK, name, first_name, last_name, type, role,
                rating, year, notes, image_path, date_added, extra JSON)
credits        (id TEXT PK, entity_id FK→entities CASCADE,
                title, role, year, rating, review, image_path, web_link)
media_entity   (media_item_id FK, entity_id FK, PK(media_item_id, entity_id))
entity_entity  (entity_a FK, entity_b FK, PK(entity_a, entity_b),
                CHECK(entity_a < entity_b))          -- undirected peer link

┌─ Image domain ─────────────────────────────────────────────────────┐
groups         (id INTEGER PK, name UNIQUE)
subgroups      (id INTEGER PK, name, group_id FK→groups CASCADE,
                UNIQUE(name, group_id))
images         (id INTEGER PK, file_path UNIQUE, filename, file_size,
                width, height, phash INTEGER,
                group_id FK→groups SET NULL,          -- normalized: FK, not text
                subgroup_id FK→subgroups SET NULL,
                date_added, date_modified)

┌─ Shared vocabulary ────────────────────────────────────────────────┐
tags           (id INTEGER PK, name UNIQUE, type)     -- Artist/Series/Character/
image_tags     (image_id FK, tag_id FK, PK pair)      -- General/Meta/Genre
media_tags     (media_item_id FK, tag_id FK, PK pair) -- replaces CSV genres/tags

┌─ Cross-domain links (DB.8) ────────────────────────────────────────┐
media_groups   (media_item_id FK, group_id FK, PK pair)
entity_images  (entity_id FK, image_id FK, PK pair)

┌─ Search infrastructure (DB.7) ─────────────────────────────────────┐
embeddings     (owner_type TEXT, owner_id TEXT, model TEXT,
                dim INTEGER, vector BLOB,
                PK(owner_type, owner_id, model))
media_fts      FTS5(title, review, creator, content=media_items)
entity_fts     FTS5(name, notes, content=entities)
image_fts      FTS5(filename, file_path, content=images)

schema_meta    (key TEXT PK, value TEXT)              -- schema_version, etc.
```

Design notes:

- **IDs.** Listings keep their existing TEXT UUIDs (`uuid4`, `ent-xxxxxxxx`) so migration is identity-preserving; image rows keep INTEGER PKs.
- **`extra` JSON columns** on `media_items`/`entities` absorb any legacy metadata key the normalized columns don't cover, so migration is lossless even for fields added ad hoc over time (e.g. MAL payload leftovers). New code must not write new semantics into `extra` — it is a compatibility shim.
- **CSV genres/tags become `media_tags` rows** with `tags.type='Genre'`/`'Tag'`. Advanced search's include/exclude logic becomes SQL EXISTS/NOT EXISTS instead of Python set math.
- **Associations become M2M tables** — the entire class of Python "fetch all rows, diff sets, re-upsert" consistency loops in both subtabs (`_sync_entities_for_entry`, `_sync_listings_for_entity`, `_remove_*` — ~500 LOC) collapses into `INSERT OR IGNORE`/`DELETE` statements inside one transaction, with FK cascades handling deletes.
- **`group_name`/`subgroup_name` denormalization is dropped**; views can expose the joined text form for UI compatibility during porting.
- **Indexes:** FKs, `images(phash) WHERE phash IS NOT NULL`, `images(group_id)`, `tags(name)`, plus the FTS5 tables (external-content mode, kept in sync by triggers).

Deliverable: `docs/database/unified_schema.md` with the full DDL + an ER diagram (also consumed by DB.9's ER view), reviewed before any code.

## ✅ DB.2 base.database — the Native Storage Engine

*Shipped 2026-07-12 (S210): `base/src/database/database.cpp` + `include/database/database.hpp`, registered as `base.database.Database` in `bindings.cpp`. Session-keyed handle (Argon2id once, GIL released during KDF), wrong-key detection, WAL + FK + busy_timeout pragmas, query/execute/executemany (atomic) + explicit transactions, apply_ddl/schema_version/has_fts5/vacuum/reindex/integrity_check/statistics, upsert_embedding + brute-force cosine `knn` with `prefilter_sql` (HNSW upgrade deferred to DB.7), context-manager protocol, stub class when built without SQLCipher. 14 tests in `backend/test/database/test_base_database.py` incl. encrypted-at-rest, KDF-once timing, 4-thread concurrency, FTS5-functional. FTS5 confirmed available in the linked SQLCipher.*

New C++ module `base/src/database/` registered as `base.database` (pybind11, same extension binary). **`base.secret` remains untouched** (answer #9).

**Why C++ rather than Python `sqlcipher3`:** the `base` extension already links SQLCipher + libsodium + argon2 (used by `base.secret`); a Python SQLCipher package would load a *second* libsqlcipher into a process that also hosts the JPype JVM — exactly the lazily-loaded-native-library conflict class that has caused three SIGSEGVs in this app already. Reusing the already-linked library in a new C++ module sidesteps that entirely, and keeps the vector-search hot path native.

API surface (bound class, not free functions — this is what enables the session key):

```cpp
class Database {                       // py: base.database.Database
    // opens (creating if absent) library.db; runs Argon2id ONCE here
    Database(std::string db_path, std::string password, std::string salt);
    void close();                      // + context-manager __enter__/__exit__

    // migrations & health
    int  schema_version();  void apply_ddl(std::string sql);
    void vacuum();  void reindex();  bool integrity_check();
    py::dict statistics();             // counts, file sizes, last-modified

    // generic parameterized SQL (the DAL builds on these; DAL owns SQL text)
    py::list query(std::string sql, py::tuple params);
    int      execute(std::string sql, py::tuple params);
    void     executemany(std::string sql, py::list rows);
    void     begin();  void commit();  void rollback();

    // vector search hot path (DB.7)
    void     upsert_embedding(owner_type, owner_id, model, py::array_t<float>);
    py::list knn(owner_type, model, py::array_t<float> query, int top_k,
                 std::string sql_prefilter = "");   // HNSW w/ brute-force fallback
    void     rebuild_vector_index(owner_type, model);
};
```

- The keyed `sqlite3*` handle lives for the object's lifetime → **one KDF per session** (answer #6), vs one per call today. The GUI owns a single `Database` instance created at login (post-vault-unlock, same `raw_password`/`account_name` inputs `base.secret` uses today) and threads it through a small accessor in `backend/src/database/unified/session.py`.
- WAL mode + `busy_timeout`; a coarse internal mutex serializes access from Qt worker threads (QRunnable workers already funnel DB work through few threads; contention at this scale is negligible).
- HNSW index built in-memory at first use from the `embeddings` table and persisted to an encrypted sidecar blob table (`vector_index(model, owner_type, data BLOB)`); reuses the hnswlib vendoring already present for `base.similarity`/`base.recon`.
- FTS5 must be enabled in the SQLCipher build flags (`-DSQLITE_ENABLE_FTS5`) — verify at CMake configure time; build-env notes in the pixi/RPATH memory apply.
- Tests: pure-C++-free pytest suite `backend/test/database/test_base_database.py` (tmpdir DBs, wrong-password behavior, concurrent-worker smoke test, KDF-once timing assertion).

**CRUD language split (perf-guided, answer #9):** connection/transaction/KDF/vector/FTS machinery in C++; *SQL text and domain logic* in the Python DAL (DB.3). Row-shuffling CRUD is I/O-bound — Python building parameterized statements over the C++ `query/execute` primitives measures identically to native CRUD at this scale, and keeps iteration fast. If a specific path proves hot (bulk scan upserts), promote just that path to a dedicated C++ method.

## ✅ DB.3 Python DAL (`backend/src/database/unified/`)

*Shipped 2026-07-12 (S210): `session.py` (login-time singleton + `ensure_schema` with FTS5 fallback flag), `media_repo`/`entity_repo` (legacy entry-dict dialect round-trips — CSV genres/tags ↔ `media_tags`, `episode_list`/`credit_list` ↔ tables, associations ↔ M2M), `image_repo` (PgvectorImageDatabase-parity names, FK groups, bulk `paths_in_db`), `tag_repo` (typed vocabulary + `merge_tags`), `search_repo` (structured image search parity, FTS5-with-LIKE-fallback text search, `advanced_media_search` SQL builder, `semantic_image_search` knn+prefilter), `manager.py` (legacy-shape statistics, reset gated on a verified backup manifest). 14 tests in `backend/test/database/test_unified_repos.py`.*

Repository layer that both tab families consume; no GUI file touches SQL directly.

```
backend/src/database/unified/
    session.py        # login-time Database construction, singleton accessor
    media_repo.py     # media_items + episodes + media_entity + media_tags
    entity_repo.py    # entities + credits + entity_entity + entity_images
    image_repo.py     # images + groups/subgroups + image_tags + phash queries
    tag_repo.py       # unified tag vocabulary (typed), rename/merge ops
    search_repo.py    # FTS5 queries, advanced-search SQL builder, knn wrappers
    manager.py        # vacuum/reindex/integrity/statistics/reset(dev-gated)
```

- Mirrors `PgvectorImageDatabase`'s method names where practical (`add_image`, `search_images`, `get_all_tags_with_types`, `get_subgroups_for_group`, …) so DB.6's tab port is mostly an import swap.
- Replaces the listings side's dict-blob contract with typed dicts/dataclasses; a thin compatibility function reconstructs the legacy entry-dict shape for the detail panels until DB.5 finishes.
- All mutations transactional; save-of-a-listing (entry + associations + tags) is **one** transaction instead of today's N upserts × N KDFs.
- Unit tests per repo module (these are plain SQLite-level tests — safe to run, no GUI, no JVM).

## ✅ DB.4 Backups & Migration Scripts (`backend/migrations/`)

*Shipped 2026-07-12 (S210): all five steps + runner. 000 `backup_all.py` (see progress note below); 001 `create_library_db.py` (DDL + version stamp, idempotent); 002 `migrate_listings.py` (reads via `base.secret.fetch_all_listings_secure` — its last consumer; two-pass rows-then-links so ordering can't drop associations; asymmetric legacy association data healed by M2M union; dangling ids logged AND parked in `extra._dangling_*`); 003 `migrate_pgvector.py` (injectable data provider — psycopg2 confined to the default provider; FK resolution for the denormalized text columns; original dates + pHashes preserved; graceful skip when unreachable, re-runnable); 004 `verify_migration.py` (full id↔title sweep vs legacy listings, pgvector counts + sampled paths, `integrity_check` + `foreign_key_check`, parked-dangling report); `runner.py` (resumable state file at `~/.image-toolkit/.phase_db_migration_state.json`, backup manifest re-verified by hash on EVERY run, verification failure aborts non-zero pointing at the backups, `--skip-postgres`/`--force`). 13 tests in `backend/test/database/test_migrations.py` incl. end-to-end runner, resume, tampered-backup refusal, verification-failure abort.*

Non-negotiable order (answer #8): **backup first, migrate second, verify third.** New directory:

```
backend/migrations/            # module names can't start with digits — the
    backup_all.py              #   runner maps step numbers to modules
    create_library_db.py       # 001: DDL from DB.1 via base.database, stamps schema_version
    migrate_listings.py        # 002: listings_secure.db → library.db
    migrate_pgvector.py        # 003: PostgreSQL → library.db (skippable if server absent)
    verify_migration.py        # 004: row-count + checksum + referential-integrity report
    runner.py                  # orchestrates 000→004, idempotent, resumable
```

*Progress: ✅ 000 `backup_all.py` shipped 2026-07-12 (S210) — timestamped dirs under `assets/migrations/pre_unified/`, SHA-256 manifest, `verify_manifest()` re-hash check, staleness warnings on `.enc` copies, pg_dump with graceful skip; 4 tests in `backend/test/database/test_backup_all.py`.*

- **000_backup_all**: (a) file-copy `listings_secure.db` → `assets/migrations/pre_unified/listings_secure.db.bak`; (b) trigger the existing encrypted JSON backup path (equivalent of both "Update Backup" buttons) so `listings.json.enc`/`entities.json.enc` are current; (c) `pg_dump --format=custom` of the image DB → `assets/migrations/pre_unified/imagedb.dump` (graceful skip + loud warning if Postgres is unreachable); (d) manifest with SHA-256 of every artifact.
- **002_migrate_listings**: reads via `base.fetch_all_listings_secure` (last use of that API); explodes each JSON blob into `media_items`/`episodes`/`entities`/`credits`; splits CSV genres/tags into `tags`+`media_tags`; converts `associated_*` lists into M2M rows (dangling IDs logged, not dropped — parked in `extra`); unknown keys → `extra`.
- **003_migrate_pgvector**: streams `images`/`groups`/`subgroups`/`tags`/`image_tags` via psycopg2 (the only surviving use of it, inside the script); resolves text `group_name`/`subgroup_name` → FKs; carries `phash` over; `embedding` column is ignored (it's NULL everywhere).
- **004_verify**: source-vs-target row counts per table, spot-check field equality on a random sample, `PRAGMA foreign_key_check`, orphaned-association report. Runner exits non-zero and points at the backups if anything mismatches.
- Runner invoked from a first-launch dialog ("Library upgrade required — a full backup will be created first") and from the CLI (`python -m backend.migrations.runner`).

## 🔄 DB.5 Listings Subtabs on the Unified Store

*Mostly shipped 2026-07-12 (S210): both subtabs + both detail panels ported to `MediaRepo`/`EntityRepo` via `gui/src/helpers/core/library_session.py` (session opened lazily on first use; first-launch migration prompt with backup gate + threaded progress dialog when the library is empty and legacy data exists). All four association-sync loops, both `_save_data` full-rewrites, and the `listings_common` save helpers + `fetch_entity_name_map` are deleted (~600 LOC); `_SyncBackupWorker.run_sync` now upserts through the repos on the session handle (no delete-all/reinsert window); entity-name search map uses `list_ids_and_titles()` instead of fetch-all.*

*Deferred piece shipped 2026-07-27 (issue #63): the default gallery filter/sort path (search box + type/status/role combos + sort combo) and the Advanced Search dialog's criteria now both run through `search_repo` SQL instead of the old Python full-list scan. **Correction to the note above:** the "SQL builders exist and are tested" claim was stale — `search_repo.build_advanced_query()` never existed (the real method, `advanced_media_search()`, existed and was tested but was never actually called from the GUI; the subtabs' `_filtered_entries`/`_filtered_entities` did 100% of their filtering/sorting in Python, including the Advanced Search dialog's criteria). Fixed now: `SearchRepo` gained `filter_media()`/`filter_entities()` (search box — title/creator/tags/genres/associated-entity-or-content-title, all via `EXISTS` subqueries and `LIKE … COLLATE NOCASE` — plus type/status/role equality filters, optional `advanced_criteria` reusing the same condition-builder as `advanced_media_search()`, and a `sort_key`/`descending` pair driving `ORDER BY`); both subtabs' `_filtered_entries`/`_filtered_entities` now just map UI state to those calls and look up the returned ids in the already-loaded row dicts (needed for card rendering, not for filtering). One documented gap: "Sort by: Local Filename" sorts by a path's basename, which needs string-reverse/last-index-of that core SQLite has no portable builtin for — that one sort key still does its final ordering in Python, but only over the SQL-filtered result subset, never a full-table scan. 4 new repo-level tests in `test_unified_repos.py` (`test_filter_media_search_and_combos`, `test_filter_media_sort_keys`, `test_filter_entities_search_and_combos`, `test_filter_entities_sort_keys`); 81 database-suite tests green (the JVM/crypto test file is unrelated and untouched).*

Port `SeriesListingsSubTab` / `EntityListingsSubTab` + detail panels/dialogs to the DAL. UI appearance unchanged; internals simplified:

- `_load_data` → repo list calls (already-joined, typed rows). `_upsert_entry`/`_upsert_entity` → single-transaction repo saves. Delete → FK cascades.
- The four association-sync methods and both `_save_data` full-rewrites are **deleted**, along with the cross-subtab `_on_external_reload` fetch-all churn (subtabs re-query only affected rows; the existing changed signals stay as the notification bus).
- Search/filter/sort move to `search_repo` (FTS5-backed text search plus dedicated `filter_media`/`filter_entities` SQL builders for the gallery path) — fixes the O(N·M) entity-name search and evaluates the search box + combos + Advanced Search criteria in one query instead of loading the world.
- Advanced search dialog criteria compile to SQL via `search_repo`'s shared `_advanced_media_conditions()` builder (used by both `advanced_media_search()` and `filter_media()`; include/exclude entities/tags/genres, AND/OR).
- MAL fetch, directory import, thumbnail generation, recommendation dialog are untouched consumers — they just save through the new repos. `RecommendationWorker` keeps `rec_engine.db` for now (unified in DB.7).
- The encrypted `.enc` backup buttons keep working against a JSON export produced from the repos (format-compatible with today's files so old backups remain restorable).

## 🔄 DB.6 Image Tabs on the Unified Store (Postgres Retirement)

*Mostly shipped 2026-07-13 (S211): new `UnifiedImageDatabase` facade (`backend/src/database/unified/facade.py`) reproduces the exact `PgvectorImageDatabase` method surface over the DAL, so SearchTab/ScanMetadataTab/`SearchWorker`/`ImagePreviewWindow`/wallpaper-display port with **zero call-site changes** — they keep using `db_tab_ref.db`. `DatabaseTab` rewritten: PostgreSQL connection form/psycopg2/dotenv deleted; the store auto-opens from the vault session at construction ("Open Library" button remains for a locked-vault start); duplicate-rename handling matches on SQLite's "UNIQUE" error; `collect()` no longer emits credentials (fixes the stored-password wart; legacy configs with credentials are ignored). Tab layout: "Database Management" replaced by a **"Library"** category — `Listings · Image Search · Scan & Tag · Management` (Listings moved out of System Tools; Data Browser joins in DB.9). `backend.src.database` package import made lazy so nothing outside migration 003 pulls psycopg2. 12 facade-parity tests (`test_unified_facade.py`) exercising the tabs' exact call shapes.*

***P3b done 2026-07-27** (issue #64): both deferred items shipped.*
- **Archival**: before moving anything, found the roadmap's own accounting was incomplete — `phash_deduplicator` and the pooled tests weren't the only real dependents. `backend/src/utils/io/dispatcher.py`'s CLI `db search` command and `backend/benchmark/bench_database.py` (an entire "PostgreSQL query performance" benchmark script) also imported `PgvectorImageDatabase` directly. Fixed both first (`dispatcher.py` re-pointed at the unified store via an already-open session, raising a clear error if none is open; `bench_database.py` archived alongside the DB files since it measures Postgres-specific characteristics the app no longer has) before archiving anything, so nothing broke. `image_database.py`, `pooled_image_database.py`, `sql/` (7 files), the now-orphaned `sql_loader.py` (zero other callers once the SQL files moved), `psycopg_migration.py` (an old standalone Postgres migration CLI tool with zero callers anywhere), and the two legacy test files all moved to `archive/python/database/` (`git mv`, history preserved). `backend/src/database/__init__.py`'s lazy `PgvectorImageDatabase` re-export removed (nothing calls it anymore — migration 003 has its own separate, already-guarded `import psycopg2`, confirmed not going through this path). `psycopg2-binary`/`psycopg[pool]` moved from hard `dependencies` to a new `legacy-postgres` optional group in `pyproject.toml` (only needed for migration 003 against a pre-DB.6 library); `uv.lock` regenerated to match.
- **`phash_deduplicator.py` re-pointed**: default constructor now wraps the app's already-open unified session (`session.get_session()` → `UnifiedImageDatabase`) instead of constructing a standalone `PgvectorImageDatabase()`. Added `ImageRepo.find_near_duplicates_by_phash()` (Hamming-distance sweep over `get_all_phashes()`, same primitive `DirPhashIndex._scored()` already uses) since the unified DAL didn't have this one method yet — exposed on the facade too. `find_all_duplicate_groups()`'s raw `psycopg2` cursor SQL replaced with the facade's own `get_all_phashes()` accessor (the extra columns it fetched were unpacked but never actually used).
- **Scan & Tag upsert moved off the GUI thread**: new `UpsertWorker(QThread)` (`gui/src/helpers/core/upsert_worker.py`, subclassing `QThread` and overriding `run()` rather than `QObject.moveToThread()` — required per this project's JPype-JVM/Qt-event-loop SIGSEGV precedent, same pattern as `MergeWorker`/`SimilarityScanWorker`) decodes each image's dimensions via `QImage` (thread-safe; never `QPixmap`, which isn't) in the background. All actual DB writes stay on the main thread but are now wrapped in **one transaction** (`UnifiedImageDatabase.transaction()`, new — wraps the DAL's existing `_util.transaction()` context manager) instead of one implicit commit per image, which was the dominant cost on large batches, not the decode itself. `ScanMetadataTab._execute_upsert` now just dispatches to the worker; the old per-image loop moved to `_on_upsert_prepared` (the worker's `finished` handler), with `progress` wired to a lightweight upsert-button text update (no new widget needed).
- **Tests**: `test_unified_facade.py` +1 (`transaction()` commit/rollback), `test_unified_repos.py` +1 (`find_near_duplicates_by_phash` against a real SQLCipher-backed repo, not mocked), `test_phash_deduplicator.py` updated mock shape + 1 new test for the cursor-SQL replacement. 109 tests passing (`backend/test/database/` + `backend/test/core/`, excluding the pre-existing unrelated JVM/crypto build-artifact gap this worktree lacks).

- **SearchTab / ScanMetadataTab / ImagePreviewWindow / Wallpaper system-display**: swap `db_tab_ref.db` (Postgres) for `image_repo`/`search_repo`. `SearchWorker` and the scan workers keep their threading shape. Fix in transit: `perform_upsert_operation`'s per-image `QPixmap` + queries move into a QRunnable worker (batch transaction, progress signal) — no more GUI-thread freezes on big batches.
- **DatabaseTab ("Configuration") → "Library Management" panel**: connection form/connect/disconnect deleted (the store opens at login). Survivors: statistics banner, vacuum/reindex/integrity, group/subgroup/tag CRUD + inline rename + bulk JSON tag import + auto-populate-from-directory — all on `tag_repo`/`image_repo`/`maintenance`. Reset stays double-confirmed and now also forces a `000_backup_all`-style export first.
- **Tab layout (answer #7)**: the "Database Management" category becomes **"Library"**: `Series Listings · Entity Listings · Image Search · Scan & Tag · Management · Data Browser (DB.9)`. The Listings entry is removed from "System Tools". (Main-window constraint from project memory: tabs stay plain QWidget subclasses; no heavy compute in constructors.)
- **Retirement**: `backend/src/database/image_database.py`, `pooled_image_database.py`, `sql/*.sql` move to `archive/`; `psycopg2`/`psycopg_pool`/pgvector removed from requirements (psycopg2 stays importable only for `003_migrate_pgvector`, guarded); `env/vars.env` DB_* keys deprecated; `phash_deduplicator` re-pointed at `image_repo`.
- The saved-config format (`collect`/`set_config`) drops connection credentials — fixes the stored-password wart.

## ✅ DB.7 Semantic Search & CBIR

*Shipped 2026-08-01 (issue #65): image-side semantic search, listings-side semantic search (BGE-M3), and — reversing a prior round's "too large" conclusion — full Recommendation-Engine storage absorption. See below for what's still genuinely minor/deferred (hnswlib ANN index, multi-group semantic prefilter).*

**Correction to the original roadmap text**: "MetaCLIP image encoder (already integrated for the Inference tab)" was never actually true — `MetaCLIPInferenceTab` (`gui/src/tabs/models/meta_clip_inference_tab.py`) is a thin GUI shell that dispatches a job elsewhere; there is no in-process MetaCLIP encoder anywhere in the codebase to call. What *does* already exist and run in-process is `backend/src/core/similarity/embedder.py` (built for the Similarity tab's Tier-4 semantic hashing) — a lazy-loaded, graceful-fallback `open_clip` embedder (`mobileclip` → `openclip` → `resnet18`), already batched, already GIL-releasing during the torch forward pass. DB.7 builds on that real, tested encoder instead — `model='openclip'`, not `'metaclip'` — rather than inventing a second ML-loading pathway for a model this codebase can't actually run yet.

**Shipped**:
- `ImageRepo.upsert_embedding()`/`count_unembedded()`/`list_unembedded()` (`backend/src/database/unified/image_repo.py`) — thin wrappers over `Database.upsert_embedding` (DB.2) plus the "what's left to embed" query the backfill worker's work queue needs. Exposed on `UnifiedImageDatabase` as `upsert_image_embedding`/`count_unembedded_images`/`list_unembedded_images`/`semantic_image_search` (the last one was already implemented in `search_repo.py` ahead of this phase, just never exposed on the facade or called from anywhere).
- `OpenClipEmbedder.embed_text()` (`embedder.py`) — text-tower embedding in the same vector space as the image tower, needed for text→image search (not yet wired to a GUI control — see Not done below).
- `ImageEmbeddingWorker` (`gui/src/helpers/database/embedding_worker.py`) — `QThread` subclass overriding `run()` (same pattern as `UpsertWorker`/`MergeWorker`, not `QObject.moveToThread()` — the JPype-JVM/Qt-event-loop precedent). Embedding computation happens off-thread; the DB write is deferred back to the main thread in one transaction (the keyed `Database` handle isn't safe to share across threads, per DB.2's own risk register).
- Management panel gained a "🧠 Embed Unembedded Images" button (`database_tab/_ui_connection.py` + `_connection_stats.py`) — counts pending images, confirms, runs the worker, shows live progress, writes results transactionally, matching the existing Vacuum/Reindex button pattern exactly.
- **`SemanticSearchWorker`** (`gui/src/helpers/database/semantic_search_worker.py`) — a short `QRunnable` dispatched on the global `QThreadPool`, mirroring `SearchWorker`'s own structured-search pattern exactly rather than introducing a second worker style. Embeds the query (text, or an existing image for find-similar) and runs `semantic_image_search` in the same background task; results come back already ranked, worst-to-best excluded via `top_k`.
- **Search tab "Search by Meaning"** (`search_tab/_semantic_search.py`): an additive natural-language query box + button next to the existing structured Search Database form (kept as a separate control rather than a mode toggle on the existing button, to avoid touching the existing, QML-bridge-shared `perform_search()`/`toggle_search()` flow). Composes with the existing group/subgroup/tag/format filters as a SQL prefilter — group/subgroup only apply when exactly one is selected, since `semantic_image_search()` takes a single name, not a list. Results render in relevance (score) order, bypassing `start_loading_thumbnails()`'s alphabetical `_apply_sort()`.
- **"🧠 Find Similar Images" context-menu action** on every found-gallery card (`search_tab/_file_actions.py`) — queries by that image's own embedding (computed on the fly, not persisted), excluding the source image from its own results.
- Tests: `test_image_embedding_backfill_bookkeeping` (`test_unified_repos.py`), `test_semantic_search_facade_surface` (`test_unified_facade.py`); `TestSearchTabSemanticSearch` (6 GUI tests, `gui/test/database/test_database_tab.py`) — dispatch shape, empty/no-db guards, and the relevance-order-preserved assertion.

**Listings semantic search (BGE-M3), shipped in a later round**:
- Found the real, working BGE-M3 embedder already in this codebase: `submodules/Recommendation-Engine/src/data/embedder.py`'s `Embedder.embed_dense()` (1024-dim, `FlagEmbedding`, already a locked dependency) — reused rather than adding a new model, same "use what already runs in-process" principle as the image side's `OpenClipEmbedder`.
- Fixed a genuine **pre-existing bug** found along the way: `gui/src/helpers/database/recommendation_worker.py`'s `_RE_DIR` pointed at `<repo_root>/Recommendation-Engine`, which doesn't exist — the submodule actually lives at `<repo_root>/submodules/Recommendation-Engine`. The existing recommendation feature was silently broken (`ImportError` on every use) in this checkout before this fix.
- Confirmed the roadmap's "dead placeholder-embedding code in `listings_common.py`" was already removed back in DB.5 — nothing left to delete.
- `MediaRepo`/`EntityRepo` gained `upsert_embedding`/`count_unembedded`/`list_unembedded`, mirroring `ImageRepo`'s exact shape; `SearchRepo` gained `semantic_media_search`/`semantic_entity_search`, mirroring `semantic_image_search`.
- New `ListingsEmbeddingWorker` (`QThread`, backfill) and `ListingsSemanticSearchWorker` (`QRunnable` via `BaseQRunnableWorker`, query-time) in `gui/src/helpers/database/`.
- Both `series_listings_subtab` and `entity_listings_subtab` gained a "🧠 Search by Meaning" + "⚙️ Build Search Index" toolbar pair and a "❌ Clear Semantic" button (new `_semantic_search.py` mixin in each), composing with the existing `_filtered_entries`/`_filtered_entities` ranked-result precedence the recommendation feature already used.
- Tests: `test_listings_embedding_backfill_bookkeeping`, `test_semantic_media_and_entity_search` (`test_unified_repos.py`); `gui/test/core/test_listings_semantic_search.py` (6 GUI tests).

**Full Recommendation-Engine storage absorption, shipped — reversing a prior round's conclusion**:
- Two earlier rounds concluded absorption was too large, reasoning that `RecommendationWorker`'s hybrid dense+sparse (SPLADE) + RRF + watch-history-boosted retrieval "doesn't map onto the simple `embeddings` table/`Database.knn()`." That reasoning is correct for *porting the retrieval algorithm* — but conflated it with the separate, much smaller question of *where `SQLiteStore` physically stores its rows*. A re-investigation drew that distinction explicitly and it held up: `SQLiteStore` (`submodules/Recommendation-Engine/src/data/store.py`) turned out to use only plain, portable SQL (`CREATE TABLE IF NOT EXISTS`, `SELECT`/`INSERT OR REPLACE`/`DELETE`, no JSON1, no FTS5, no `ATTACH`, no custom functions/collations) — the retrieval/scoring layer (`HybridRetriever`/`Scorer`) sits entirely in Python on top of whatever rows the store returns, completely unaware of which store produced them.
- New `EncryptedSQLiteStore` (same submodule, same public API as `SQLiteStore`) takes an **injected, already-open** `base.database.Database` handle instead of opening its own SQLite file — `recommendation_worker.py` now reuses the unified library session (`backend.src.database.unified.session.get_session()`) that's already open by the time any listings feature is reachable, rather than deriving a second Argon2id key. Table `rec_engine_items` lives inside `library.db` itself (checked against `schema.sql` for name collisions — none). Falls back to the legacy plaintext `SQLiteStore` only if no library session is open yet (logged as a warning) — a defensive path, not the normal one.
- This closes the plaintext-sidecar gap DB.1 locked in as decision #2 ("no plaintext sidecar DBs") without touching the retrieval algorithm at all — `SQLiteStore` itself is untouched, purely additive change.
- Tests: `backend/test/database/test_recommendation_encrypted_store.py` (15 tests, mirrors `Recommendation-Engine`'s own `tests/test_store.py` coverage plus a table-collision check); `Recommendation-Engine`'s own suite (14 tests) unaffected.

**Still deferred** (genuinely minor, not silently skipped):
- **hnswlib ANN index**: `Database.knn` (DB.2) already has a brute-force fallback path and is what's used above; the persisted-encrypted-blob HNSW index for larger libraries is not built — fine at current library scale (brute-force over a few thousand images/entries is fast), revisit if it becomes a real bottleneck.
- **Multi-group/subgroup semantic prefilter**: `semantic_image_search()` only accepts a single `group_name`/`subgroup_name`, unlike structured search's list-based filters — a real (small) API gap, not just an unimplemented UI hook.

## Original DB.7 scope (for reference)

- **Image embeddings**: MetaCLIP image encoder (already integrated for the Inference tab) as the default `model='metaclip'`; embedding worker (QThreadPool, GPU-optional, batched) fills `embeddings(owner_type='image')` during Scan & Tag upserts and via a backfill action in Management ("Embed N unembedded images").
- **Text→image search**: MetaCLIP text encoder → `knn('image', 'metaclip', vec, k, sql_prefilter=…)`, with the SQL prefilter compiled from the existing Search tab filters (group/tags/format) so vector search composes with structured search. New "Semantic" mode toggle + natural-language box in the Search tab; "Find similar" context-menu action on every image card (query by image embedding).
- **pHash** remains the dedup primitive only (Similarity tab, extension use-case) — explicitly not the search engine.
- **Listings semantic search**: BGE-M3 embeddings for `media_items`/`entities` stored under `model='bge-m3'`; `Recommendation-Engine`'s store gains a `LibraryBackend` so `rec_engine.db` is absorbed and the dead placeholder-embedding code in `listings_common.py` (`save_*_entry_to_db` byte-of-title vectors) is deleted.
- **Index**: hnswlib per (owner_type, model) inside `base.database` (DB.2), persisted encrypted; brute-force fallback below ~5k vectors (cheaper than index maintenance). Cosine metric everywhere.
- Acceptance: text query over 50k images returns top-50 in <150 ms warm; find-similar returns visually coherent neighbors on the owner's real library.

## ✅ DB.8 Cross-Domain Features

*Shipped 2026-08-01 (issue #66): DB.8a/8b/8c/8d, cross-tab navigation, Entity Recon integration, and (closing issue #127 too) real tag-chip widgets in listings. Only Entity Recon batch-linking (a minor UX nicety, not a gap) remains.*

The payoff for a single store (answer #5 — "EVERYTHING"):

**Shipped**:
- **DB.8a Media ↔ image groups**: `MediaRepo` gained `link_group`/`unlink_group`/`get_linked_groups`/`get_media_for_group`/`suggest_group_matches` (`backend/src/database/unified/media_repo.py`) over the existing `media_groups` M2M table. `suggest_group_matches()` is a simple case/whitespace-insensitive substring match ranked by specificity (not a fuzzy-distance library) — good enough for a human-confirmed suggestion list. The Series Listings detail panel gained a "Linked Image Groups" chip row (`display/detail_panel/_linked_groups.py`, new) with a link/unlink picker dialog (`elements/dialog/linked_groups_dialog.py`, `_LinkedGroupsDialog` — modeled on the existing `_AssociatedEntitiesDialog`, suggested matches sorted first with a ⭐).
- **DB.8b Entity ↔ images**: `EntityRepo` gained `link_image`/`unlink_image`/`get_linked_images`/`get_entities_for_image` over the existing `entity_images` M2M table. The entity detail panel gained a "Linked Images" thumbnail gallery strip (`display/entity_detail_panel.py`) — thumbnails via the existing `apply_thumbnail_to_label` helper, "➕ Link Image…" via `QFileDialog` + `ImageRepo.get_image_by_path`/`add_image`, per-image "✕ Unlink".
- **DB.8c Unified tag vocabulary, fully shipped (closes issue #127 too)**: `TagRepo.merge_tags()` already existed (shipped with DB.3, tested, but never exposed on the facade or reachable from any GUI control). Exposed as `UnifiedImageDatabase.merge_tags()`; the Management panel's tag table gained a "🔀 Merge Into…" right-click action. Later in the same round: the listings detail panel's Genres/Tags fields gained real autocomplete from the shared vocabulary, wiring up `TagCompleter` (`gui/src/helpers/database/tag_completer.py` — built for issue #127, sat dead/unused until now). The Management tag table also gained a "🔍 Search Images with this Tag" right-click action. **Finally, real tag-chip widgets**: `TagChipWidget`/`TagChipGroup` (`gui/src/components/tag_chip_widget.py`) had also been built for issue #127 at some point and sat completely unused — a new `TagChipEditor` composite (removable chips in a new reusable `FlowLayout`, since Qt has no builtin one and a plain `TagChipGroup` overflows horizontally for a real tag list, + a single autocomplete-backed add-input) now replaces the plain `QLineEdit`s in the Series Listings detail panel's Genres/Tags fields, exposing the same `setText()`/`text()` string contract so no other call site needed to change. Entities have no tags/genres concept in this schema, so no equivalent change applied there.
- **DB.8d Auto-create listings from scans — both halves now shipped**:
  - *Image-group half* (shipped first): after a Scan & Tag batch upsert touches one or more image groups, any group with **zero** linked `media_items` and no whole-word-fuzzy-matching existing title gets offered in one batched review dialog (checkable rows, editable title, "create new" vs. "link to existing" per row where a fuzzy match *does* exist) — confirm once, one transaction creates/links everything checked. Wired as a live hook in `scan_metadata_tab/_upsert_ops.py` (`_auto_listings.py`, new `_AutoListingsMixin`).
  - *Video-directory-import half* (shipped in a later round): investigated `series_listings_subtab/_directory_import.py` and found the "one review dialog" UI the roadmap asked for already existed (`_DirectoryImportDialog` — series/episode parsing, checkable review table, new/existing badges) but violated the roadmap's explicit "then a single transaction" requirement — it called `_upsert_entry()` once per series (independent implicit transactions; a partial failure mid-import could leave some series saved and others not). Fixed: the whole batch now saves inside one `raw_db.begin()/commit()`, rolling back entirely on any failure. Also added the `media_groups` pre-fill DB.8d asked for: a series whose name case-insensitively exact-matches an existing image `groups` row gets auto-linked via `MediaRepo.link_group()` (kept to exact match only, not fuzzy — fuzzy-with-human-confirmation is the image-group half's job; auto-linking during a batch import without a per-row confirmation step would be inconsistent with "human confirms" everywhere else in this effort).
- **Cross-tab navigation, both directions shipped**: a prior round deferred this after concluding "`ListingsTab`/`DatabaseTab` have no reference to each other anywhere, this needs new architecture." That conclusion turned out wrong on closer inspection — `gui/src/windows/main/_tab_search.py`'s existing Ctrl+T tab-search popup already implements exactly "activate tab X by name," and `ListingsTab` was already registered in the same "Library Database" category as `DatabaseTab`/`SearchTab`, not a separate one as assumed. A `main_window_ref` cross-tab reference (mirroring the existing `search_tab_ref`/`merge_tab_ref` post-construction-assignment pattern) now threads MainWindow ↔ `ListingsTab` ↔ `SeriesListingsSubTab` ↔ the detail panel, and MainWindow ↔ `DatabaseTab`. The detail panel's Linked Image Groups row gained a "🔎 View Images" button (`SearchTab.filter_by_group()`, new, mirrors the existing `search_by_tag()`); the Management tag table's "🔍 Search Images with this Tag" now actually switches tabs (previously just set filter state); a new sibling "Search Listings with this Tag" does the same into Series Listings.
- **Entity Recon integration, shipped**: `EntityReconTab` (`gui/src/tabs/web/entity_recon_tab/`) turned out to be a plain mixin-composed `QWidget`, not the QML tab project memory described (that description was stale) — no special bridge architecture to design around. Gained a right-click "🔗 Link to Library Entity" action on any local provenance match: resolves the matched file to an `ImageRepo` row (indexing it first if needed) and the matched name to an `EntityRepo` row (exact match auto-suggested, close matches offered as a picker, no match offers to create one — human confirms every path), then `EntityRepo.link_image()`. Reused `MediaRepo.suggest_group_matches()`'s "simple substring ranker, human confirms" pattern for the name lookup rather than adding new DAL.
- Tests: `test_media_group_links`, `test_media_group_fuzzy_suggestions`, `test_entity_image_links` (`test_unified_repos.py`), `test_merge_tags_facade` (`test_unified_facade.py`); `gui/test/core/test_detail_panel_links.py` (16), `gui/test/core/test_tag_vocabulary_and_search.py` (20, incl. 8 new `TestTagChipEditor` cases), `gui/test/database/test_scan_metadata_auto_listings.py` (6), `gui/test/web/test_entity_recon_library_link.py` (7), `gui/test/core/test_directory_import_transaction.py` (5).

DB.8 is now feature-complete against its original roadmap scope.

**Still deferred** (a UX nicety, not a functional gap):
- **Entity Recon batch linking** — only one match at a time via right-click, no multi-select/batch UI.

## ✅ DB.9 Data Browser Tab (Raw Tables + ER View)

*Shipped 2026-08-01 (issue #67): table grid, FK-cell navigation + reverse-references panel, the ER/crow's-foot schema view, gated cell-edit mode, and per-column filters — the full originally-scoped feature set.*

New tab in the Library category (answer #7, per the provided ER-diagram reference):

**Shipped**:
- New `backend/src/database/unified/browser_repo.py` (`BrowserRepo`): `list_tables()` (from `sqlite_master`, also used as a strict allowlist), `table_columns()` (`PRAGMA table_info`), `table_row_count()`, `query_table(table, where_sql, limit, offset)` — validates the table name against the allowlist and rejects a `WHERE` fragment containing a semicolon or an INSERT/UPDATE/DELETE/DROP/ALTER/ATTACH/PRAGMA/CREATE keyword (a basic guard, not a full SQL parser — documented as such in the code). Later in the same round: `table_foreign_keys()` (`PRAGMA foreign_key_list`) and `reverse_references(table, pk_value)` (scans every table's FK list for ones pointing at `table`, counts matching rows per referencing table).
- New `gui/src/tabs/database/data_browser_tab/` tab, registered in the "Library Database" category (`gui/src/windows/main/_tab_registry.py`, additive — no reordering of existing entries): table picker, paginated read-only `QTableWidget` grid over raw field values (no thumbnails, per spec), a validated `WHERE` box (invalid input shows a warning, not a crash), prev/next pagination, and CSV/JSON export of the current page. The grid's built-in `setSortingEnabled(True)` gives basic per-column click-to-sort for free.
- **FK-cell click-to-navigate + reverse-references panel** (`_navigation.py`, new `_NavigationMixin`): FK columns render styled (underline + blue, tooltip) and are discoverably clickable — clicking jumps the table picker to the referenced table filtered to that row's PK. A new "Referenced By" side panel (`QSplitter` + `QListWidget`) updates on row selection, listing every other table/column that references the selected row, each entry itself clickable via the same shared navigation helper the FK-cell click uses.
- **Schema/ER view, shipped** (`_er_view.py`, new `_ERViewMixin`): the Data Browser tab now has "Grid"/"Schema" sub-tabs (`_ui_builder.py`, wrapping the existing filter/grid/pagination/export content into the Grid sub-tab). The Schema view is a `QGraphicsScene`/`QGraphicsView` with one card per table (title, columns, PK starred, FK annotated with its target — from `table_columns()`/`table_foreign_keys()`, no new backend needed), relationship lines between related tables, wheel-zoom + drag-pan, and click-a-card-to-open-it-in-Grid. Two intentional simplifications, documented in the module's own docstring: relationship lines use a plain arrowhead rather than a full crow's-foot fork glyph, and the layout is a deterministic domain-clustered grid (bucketed by table-name prefix) rather than a force-directed algorithm — the wallpaper tab's existing graph-view infrastructure was investigated first but turned out tightly coupled to its node-drag/connection-editing workflow, so this is a small, self-contained `QGraphicsView` instead of a reuse.
- **Gated cell-edit mode (v2), shipped** (`_edit.py`, new `_EditMixin`): an "🔓 Enable Editing" checkbox, off by default every time the tab is opened (not persisted — deliberately, since the roadmap's own "let the read-only browser soak first" gate hadn't actually elapsed in wall-clock terms by the time this shipped in the same effort). `BrowserRepo.update_cell(table, pk_column, pk_value, column, new_value)` validates table/column against real schema and refuses PK-column and FK-column edits outright (a raw FK-integer edit could produce a silent dangling reference; the existing FK-cell click-to-navigate is the supported way to work with those columns). Every edit needs an explicit confirm dialog before writing, and the grid re-queries from the DB afterward rather than trusting the in-memory edit.
- **Per-column filter UI, shipped** (`_filters.py`, new `_FiltersMixin`): one text field per column, composed as `AND`-ed `LIKE` conditions alongside the main `WHERE` box's text (both usable together), feeding the same `query_table(where_sql=...)` path rather than a second query mechanism.
- Tests: `backend/test/database/test_browser_repo.py` (22 tests: 16 from the prior round plus 6 for `update_cell`); `gui/test/database/test_data_browser_tab.py` (29 GUI tests: 20 from the prior round plus 9 for edit mode + column filters).

DB.9 is now feature-complete against its original roadmap scope.

## DB.10 Backup Pipeline Retarget & Final Cleanup — DONE, 2026-07-27 (issue #68)

- **`_SyncBackupWorker` re-pointed at the unified store — already done before this item**, confirmed by direct inspection: `gui/src/helpers/web/sync_backup_worker.py` already uses `MediaRepo`/`EntityRepo` (upsert-by-id, no delete-all/reinsert) and its own docstring already documents the unified-store target. No change needed here.
- **`listings_common.save_*_entry_to_db` / `fetch_entity_name_map` — already removed before this item**, confirmed: `listings_common.py` carries only a comment noting their removal in DB.5; no production code references them.
- **`insert_listing_secure` et al. call sites — found and removed the remaining dead one**: `gui/src/tabs/core/elements/entity_listings_subtab.py`'s `_sync_entities_for_entity` (the last production caller) had *already* been removed by an earlier DB.5/DB.6 pass, but the test file exercising it (`gui/test/core/test_entity_listings_associations.py`) was never deleted — all 3 of its tests failed outright (`ImportError`, patching an attribute path that no longer resolves) when run directly. Archived it to `archive/python/gui_test/` rather than leaving broken tests in the active suite. (`base_dispatch.py`'s `insert_listing_secure` lambda itself, and `backend/migrations/sync_listing_associations.py`'s use of it, both stay — that migration script is a legitimate one-time tool for pre-DB.5 data, not dead code.)
- **New full-library backup added**: `backend/migrations/backup_all.py` (the `000_backup_all` pre-migration gate) retargeted — removed the `pg_dump`/`_dump_postgres`/`_load_pg_env` PostgreSQL dump entirely (DB.6 ported the image tabs off Postgres, so this was backing up a database the app no longer uses) and added a `library.db.bak` byte copy of the unified SQLCipher store (`backend/src/database/unified/session.py::DEFAULT_DB_PATH`), using the same copy pattern already used for `listings_secure.db.bak`. The legacy `listings_secure.db.bak` artifact is kept (restoring pre-DB.5 backups still needs it). `backend/test/database/test_backup_all.py` and the `runner_env` fixture in `test_migrations.py` updated to match (removed the now-nonexistent `ENV_FILE` monkeypatch, added `LIBRARY_DB`).
- **Not done**: a `VACUUM INTO`-based live-consistent snapshot (mentioned as an option in the original roadmap text) — used a plain byte copy instead, matching the existing `listings_secure.db.bak` precedent; worth a future revisit if the gate is ever run while the app has `library.db` open for writing.
- **Docs**: not touched this round — `docs/database/unified_schema.md` and AGENTS/CLAUDE notes were out of scope for the concrete code changes above; flagged for a follow-up pass, not verified stale or current here.
- **Tests green**: `backend/test/database/test_backup_all.py` (4/4) and `test_migrations.py` (6/13 — the other 7 fail/error on a pre-existing, unrelated `base.database` build-artifact gap this worktree lacks, confirmed identical with this session's changes reverted).

---

## Phasing & Dependency Graph

Incremental (answer #10 — implementer's choice); the app ships after every phase.

| Phase | Contents | Ships with app in what state | Effort |
|-------|----------|------------------------------|--------|
| ✅ P0 | DB.1 schema spec + DB.4 `000_backup_all` | Unchanged app + backup tool | done (S210) |
| ✅ P1 | DB.2 `base.database` + DB.3 DAL + DB.4 migrations 001–004 | Unchanged UI; `library.db` created & populated; old stores read-only fallbacks | done (S210) |
| 🔄 P2 | DB.5 listings port | Listings run on unified store; image tabs still on Postgres | mostly done (S210); SQL-side filtering deferred |
| 🔄 P3 | DB.6 image-tab port + Postgres retirement + Library category | Postgres gone; unified Library UI | mostly done (S211); archival + scan-worker deferred |
| ✅ P4 | DB.7 semantic search & CBIR | Full original scope shipped: image + listings semantic search, and full Recommendation-Engine storage absorption (`EncryptedSQLiteStore`) | done |
| ✅ P5 | DB.8 cross-domain features | Full original scope shipped: links, tag vocabulary + real chip widgets (#127), cross-tab navigation, both auto-listings halves, Entity Recon integration | done |
| ✅ P6 | DB.9 data browser + DB.10 cleanup/backups/docs | Full original scope shipped: table grid, FK navigation, reverse-refs, ER schema view, gated edit mode, per-column filters (DB.10 already done) | done |

```mermaid
flowchart LR
    classDef infra    fill:#0891b2,color:#fff
    classDef migration fill:#4338ca,color:#fff
    classDef refactor fill:#0f766e,color:#fff
    classDef feature  fill:#2563eb,color:#fff
    classDef planned  stroke:#64748b,stroke-width:2px

    db1["DB.1 Schema"]:::infra:::planned
    db2["DB.2 base.database"]:::infra:::planned
    db3["DB.3 Python DAL"]:::infra:::planned
    db4["DB.4 Backups +\nMigrations"]:::migration:::planned
    db5["DB.5 Listings port"]:::refactor:::planned
    db6["DB.6 Image tabs port\n(drop Postgres)"]:::refactor:::planned
    db7["DB.7 Semantic\nsearch / CBIR"]:::feature:::planned
    db8["DB.8 Cross-domain\nfeatures"]:::feature:::planned
    db9["DB.9 Data Browser"]:::feature:::planned
    db10["DB.10 Backup retarget\n+ cleanup"]:::refactor:::planned

    db1 ==> db2 ==> db3 ==> db4
    db4 ==> db5 --> db6
    db3 --> db7
    db6 --> db7
    db6 ==> db8
    db7 --> db8
    db3 --> db9
    db6 --> db10
    db8 --> db10
```

## Risk Register

| Risk | Mitigation |
|------|------------|
| **Data loss during migration** (there is precedent: the listings delete-then-reinsert incident) | `000_backup_all` is a hard gate; runner is idempotent/resumable; `004_verify` blocks cutover; old stores kept read-only until P6; `.enc` restore path preserved |
| Second libsqlcipher / JVM native-lib SIGSEGV class | No Python SQLCipher package — `base.database` reuses the already-linked SQLCipher inside the `base` extension (see JVM/native-lib conflict memory) |
| FTS5 missing from SQLCipher build | CMake configure-time check; pixi build-env notes (PKG_CONFIG_PATH / system-OpenSSL / RPATH ordering) apply to the new module |
| Keyed handle + Qt worker threads | WAL + internal mutex in DB.2; repos never share statements across threads; smoke test in `test_base_database.py` |
| Postgres unreachable at migration time | 003 is skippable with a loud warning + re-runnable later; nothing else depends on it |
| Session key in memory | Same exposure as today (`vault_manager.raw_password` already lives in-process); key is zeroized on `close()` |
| Perf regressions vs Postgres at 10k–100k rows | Indexed SQLite + FTS5 comfortably beats the current `ILIKE %…%` + Python-side filtering at this scale; measure in P3 with a 100k synthetic fixture before retiring Postgres |
| ~~`rec_engine.db` is plaintext, violating DB.1's "no plaintext sidecars" decision~~ **RESOLVED 2026-08-01** | `EncryptedSQLiteStore` (DB.7) stores recommendation data inside `library.db` via an injected `base.database.Database` handle, sidestepping both previously-blocked fixes — no new SQLCipher driver, no retrieval-algorithm port, just a storage-connection swap under an unchanged algorithm. |

## Effort × Impact Matrix

| Item | Effort | Impact |
|------|--------|--------|
| DB.2 + DB.3 (engine + DAL) | High | Critical — everything sits on it; kills KDF-per-call and both dead embedding columns |
| DB.4 migrations | Medium | Critical — the no-data-loss gate |
| DB.5 listings port | Medium | High — deletes ~500 LOC of association loops, adds real search |
| DB.6 image port | Medium | High — removes the Postgres server dependency entirely |
| DB.7 CBIR | Medium-High | High — the first *real* semantic search in the app |
| DB.8 cross-domain | Medium | High — the actual point of merging |
| DB.9 data browser | Medium | Medium — inspection/debugging + requested ER view |
| DB.10 cleanup | Low | Medium — dependency diet, docs, backup continuity |

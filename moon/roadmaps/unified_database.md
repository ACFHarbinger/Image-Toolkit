# Unified Database Roadmap — Merging the Listings Subtabs and the Database Tabs

*Created: 2026-07-11. Merges the two storage/UI stacks — the SQLCipher listings store (`base.secret` → `~/.image-toolkit/listings_secure.db`, Content/Entity Listings subtabs) and the PostgreSQL + pgvector image index (`backend/src/database/image_database.py`, Configuration/Search/Metadata tabs) — into a single encrypted, serverless, relational store with real semantic search. PostgreSQL is **dropped entirely**.*

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

## DB.2 base.database — the Native Storage Engine

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

## DB.3 Python DAL (`backend/src/database/unified/`)

Repository layer that both tab families consume; no GUI file touches SQL directly.

```
backend/src/database/unified/
    session.py        # login-time Database construction, singleton accessor
    media_repo.py     # media_items + episodes + media_entity + media_tags
    entity_repo.py    # entities + credits + entity_entity + entity_images
    image_repo.py     # images + groups/subgroups + image_tags + phash queries
    tag_repo.py       # unified tag vocabulary (typed), rename/merge ops
    search_repo.py    # FTS5 queries, advanced-search SQL builder, knn wrappers
    maintenance.py    # vacuum/reindex/integrity/statistics/reset(dev-gated)
```

- Mirrors `PgvectorImageDatabase`'s method names where practical (`add_image`, `search_images`, `get_all_tags_with_types`, `get_subgroups_for_group`, …) so DB.6's tab port is mostly an import swap.
- Replaces the listings side's dict-blob contract with typed dicts/dataclasses; a thin compatibility function reconstructs the legacy entry-dict shape for the detail panels until DB.5 finishes.
- All mutations transactional; save-of-a-listing (entry + associations + tags) is **one** transaction instead of today's N upserts × N KDFs.
- Unit tests per repo module (these are plain SQLite-level tests — safe to run, no GUI, no JVM).

## DB.4 Backups & Migration Scripts (`backend/migrations/`)

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

## DB.5 Listings Subtabs on the Unified Store

Port `ContentListingsSubTab` / `EntityListingsSubTab` + detail panels/dialogs to the DAL. UI appearance unchanged; internals simplified:

- `_load_data` → repo list calls (already-joined, typed rows). `_upsert_entry`/`_upsert_entity` → single-transaction repo saves. Delete → FK cascades.
- The four association-sync methods and both `_save_data` full-rewrites are **deleted**, along with the cross-subtab `_on_external_reload` fetch-all churn (subtabs re-query only affected rows; the existing changed signals stay as the notification bus).
- Search/filter/sort move to `search_repo` (FTS5 + SQL) — fixes the O(N·M) entity-name search and enables searching without loading the world.
- Advanced search dialog criteria compile to SQL via `search_repo.build_advanced_query()` (include/exclude entities/tags/genres, AND/OR).
- MAL fetch, directory import, thumbnail generation, recommendation dialog are untouched consumers — they just save through the new repos. `RecommendationWorker` keeps `rec_engine.db` for now (unified in DB.7).
- The encrypted `.enc` backup buttons keep working against a JSON export produced from the repos (format-compatible with today's files so old backups remain restorable).

## DB.6 Image Tabs on the Unified Store (Postgres Retirement)

- **SearchTab / ScanMetadataTab / ImagePreviewWindow / Wallpaper system-display**: swap `db_tab_ref.db` (Postgres) for `image_repo`/`search_repo`. `SearchWorker` and the scan workers keep their threading shape. Fix in transit: `perform_upsert_operation`'s per-image `QPixmap` + queries move into a QRunnable worker (batch transaction, progress signal) — no more GUI-thread freezes on big batches.
- **DatabaseTab ("Configuration") → "Library Maintenance" panel**: connection form/connect/disconnect deleted (the store opens at login). Survivors: statistics banner, vacuum/reindex/integrity, group/subgroup/tag CRUD + inline rename + bulk JSON tag import + auto-populate-from-directory — all on `tag_repo`/`image_repo`/`maintenance`. Reset stays double-confirmed and now also forces a `000_backup_all`-style export first.
- **Tab layout (answer #7)**: the "Database Management" category becomes **"Library"**: `Content Listings · Entity Listings · Image Search · Scan & Tag · Maintenance · Data Browser (DB.9)`. The Listings entry is removed from "System Tools". (Main-window constraint from project memory: tabs stay plain QWidget subclasses; no heavy compute in constructors.)
- **Retirement**: `backend/src/database/image_database.py`, `pooled_image_database.py`, `sql/*.sql` move to `archive/`; `psycopg2`/`psycopg_pool`/pgvector removed from requirements (psycopg2 stays importable only for `003_migrate_pgvector`, guarded); `env/vars.env` DB_* keys deprecated; `phash_deduplicator` re-pointed at `image_repo`.
- The saved-config format (`collect`/`set_config`) drops connection credentials — fixes the stored-password wart.

## DB.7 Semantic Search & CBIR

Real semantic image search (answer #4), shared engine across both domains:

- **Image embeddings**: MetaCLIP image encoder (already integrated for the Inference tab) as the default `model='metaclip'`; embedding worker (QThreadPool, GPU-optional, batched) fills `embeddings(owner_type='image')` during Scan & Tag upserts and via a backfill action in Maintenance ("Embed N unembedded images").
- **Text→image search**: MetaCLIP text encoder → `knn('image', 'metaclip', vec, k, sql_prefilter=…)`, with the SQL prefilter compiled from the existing Search tab filters (group/tags/format) so vector search composes with structured search. New "Semantic" mode toggle + natural-language box in the Search tab; "Find similar" context-menu action on every image card (query by image embedding).
- **pHash** remains the dedup primitive only (Similarity tab, extension use-case) — explicitly not the search engine.
- **Listings semantic search**: BGE-M3 embeddings for `media_items`/`entities` stored under `model='bge-m3'`; `Recommendation-Engine`'s store gains a `LibraryBackend` so `rec_engine.db` is absorbed and the dead placeholder-embedding code in `listings_common.py` (`save_*_entry_to_db` byte-of-title vectors) is deleted.
- **Index**: hnswlib per (owner_type, model) inside `base.database` (DB.2), persisted encrypted; brute-force fallback below ~5k vectors (cheaper than index maintenance). Cosine metric everywhere.
- Acceptance: text query over 50k images returns top-50 in <150 ms warm; find-similar returns visually coherent neighbors on the owner's real library.

## DB.8 Cross-Domain Features

The payoff for a single store (answer #5 — "EVERYTHING"):

- **DB.8a Media ↔ image groups**: `media_groups` M2M; detail panel gains a "Linked Image Groups" chip row (picker over `groups`); a "View images" button jumps to Image Search pre-filtered to that group. Auto-suggest links by title↔group-name fuzzy match (reuse the MAL name-matching normalizer).
- **DB.8b Entity ↔ images**: `entity_images` M2M; entity detail panel gets a linked-images gallery strip; Entity Recon tab gets a "link matches to library entity" action writing `entity_images` (bridges `base.recon` IdentityIndex hits into the library).
- **DB.8c Unified tag vocabulary**: listings' free-CSV tags/genres and the image DB's typed tags are the same `tags` table post-migration; Maintenance gains a tag-merge tool (case/underscore duplicates produced by the CSV split); tag chips in listings autocomplete from the shared vocabulary; clicking a tag anywhere offers "search images / search listings with this tag".
- **DB.8d Auto-create listings from scans**: the video-directory import already parses series/episodes; extend Scan & Tag so an image/video scan can propose `media_items` (one per detected series/group) with `media_groups` links pre-filled — one review dialog, then a single transaction.

## DB.9 Data Browser Tab (Raw Tables + ER View)

New tab in the Library category (answer #7, per the provided ER-diagram reference):

- **Schema/ER view**: QGraphicsScene rendering each table as a titled column-list card (PK starred, FK annotated) with crow's-foot relationship edges — same visual grammar as the reference image. Layout auto-generated from `PRAGMA table_info`/`foreign_key_list` (so it never drifts from the real schema), domain-clustered (media / images / shared / search) like the Sales/Production grouping in the reference. Pan/zoom; clicking a table opens it in the grid. The wallpaper graph-view infrastructure (`elements/graph/`) is the starting point for scene/zoom plumbing.
- **Table grid view**: table picker → paginated read-only `QTableView` over `Database.query` showing **raw field values** (file-path strings, FK integers, dates — no thumbnails). FK cells are hyperlinks that navigate to the referenced row; a reverse-references side panel lists incoming rows ("this group is referenced by 214 images, 3 media_items"). Column sort + per-column filter + `WHERE` box (read-only: statements are wrapped in `SELECT`, mutations rejected).
- **Edit mode (v2, gated)**: opt-in cell editing for scalar columns with FK validation — deferred until the read-only browser has soaked.
- Export current view as CSV/JSON.

## DB.10 Backup Pipeline Retarget & Final Cleanup

- `_SyncBackupWorker` re-pointed at the unified store: "Update Backup" exports repos → the same `listings.json.enc`/`entities.json.enc` format (old backups remain restorable via the migration importer); a new full-library encrypted dump (`library.json.enc` or SQLCipher `VACUUM INTO` copy) added for the image domain; image ZIP parts unchanged.
- Delete dead code: `base.secret` **stays as-is** for the Vault, but the listings-specific callers (`insert_listing_secure` et al. call sites, `listings_common.save_*_entry_to_db`, sync-worker delete-all/reinsert path) are removed; `hybrid_search_secure` becomes unused by the GUI (left in place — it's Vault-module territory, not ours to prune).
- Docs: `docs/database/unified_schema.md` finalized; AGENTS/CLAUDE notes updated (new login-time DB handle, no Postgres); `docs/CHANGELOG.md` entries per phase.
- Tests green: `backend/test/database/` (new engine + repos + migration round-trip on synthetic fixtures) — no GUI tests, no full-suite runs (per project testing rules).

---

## Phasing & Dependency Graph

Incremental (answer #10 — implementer's choice); the app ships after every phase.

| Phase | Contents | Ships with app in what state | Effort |
|-------|----------|------------------------------|--------|
| P0 | DB.1 schema spec + DB.4 `000_backup_all` | Unchanged app + backup tool | ~3d |
| P1 | DB.2 `base.database` + DB.3 DAL + DB.4 migrations 001–004 | Unchanged UI; `library.db` created & populated; old stores read-only fallbacks | ~1.5w |
| P2 | DB.5 listings port | Listings run on unified store; image tabs still on Postgres | ~1w |
| P3 | DB.6 image-tab port + Postgres retirement + Library category | Postgres gone; unified Library UI | ~1.5w |
| P4 | DB.7 semantic search & CBIR | Text→image + find-similar live; rec engine unified | ~1.5w |
| P5 | DB.8 cross-domain features | Links, shared tags, auto-listings | ~1w |
| P6 | DB.9 data browser + DB.10 cleanup/backups/docs | End state | ~1w |

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

-- ---------------------------------------------------------------------------
-- Unified Library Database — schema v1  (Phase DB, DB.1)
--
-- Single SQLCipher store at ~/.image-toolkit/library.db replacing:
--   * listings_secure.db (base.secret document store — listings JSON blobs)
--   * PostgreSQL + pgvector image index (backend/src/database/image_database.py)
--
-- Source of truth for the DDL. Consumed by:
--   * backend/migrations/001_create_library_db.py  (applies it)
--   * backend/test/database/*                      (fixture DBs)
--   * docs/database/unified_schema.md              (documentation mirror)
--
-- Statements are idempotent (IF NOT EXISTS) so re-applying is safe.
-- FTS5 virtual tables live in schema_fts.sql — applied separately with a
-- graceful fallback when the linked SQLCipher lacks FTS5.
-- ---------------------------------------------------------------------------

-- name: schema_meta
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ===========================================================================
-- Media / entity domain (from the Listings subtabs)
-- ===========================================================================

-- name: media_items
-- One row per content listing (Anime/Movie/Show/Book/Manga/Game/Other).
-- TEXT ids preserve the legacy uuid4 listing ids across migration.
-- `extra` absorbs legacy metadata keys with no normalized column (compat
-- shim — new code must not add semantics to it).
CREATE TABLE IF NOT EXISTS media_items (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    type             TEXT NOT NULL DEFAULT 'Other',
    status           TEXT NOT NULL DEFAULT '',
    personal_rating  REAL NOT NULL DEFAULT 0,
    community_rating REAL NOT NULL DEFAULT 0,
    year             INTEGER,
    episodes_total   INTEGER NOT NULL DEFAULT 0,
    current_episode  INTEGER NOT NULL DEFAULT 0,
    creator          TEXT NOT NULL DEFAULT '',
    review           TEXT NOT NULL DEFAULT '',
    web_link         TEXT NOT NULL DEFAULT '',
    local_file       TEXT NOT NULL DEFAULT '',
    image_path       TEXT NOT NULL DEFAULT '',
    date_added       TEXT NOT NULL DEFAULT (date('now')),
    date_watched     TEXT NOT NULL DEFAULT '',
    extra            TEXT NOT NULL DEFAULT '{}'
);

-- name: idx_media_items_title
CREATE INDEX IF NOT EXISTS idx_media_items_title ON media_items(title);

-- name: idx_media_items_type
CREATE INDEX IF NOT EXISTS idx_media_items_type ON media_items(type);

-- name: episodes
-- Per-episode sub-records (legacy episode_list JSON array).
CREATE TABLE IF NOT EXISTS episodes (
    id            TEXT PRIMARY KEY,
    media_item_id TEXT NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    number        INTEGER,
    title         TEXT NOT NULL DEFAULT '',
    date_watched  TEXT NOT NULL DEFAULT '',
    rating        REAL NOT NULL DEFAULT 0,
    review        TEXT NOT NULL DEFAULT '',
    image_path    TEXT NOT NULL DEFAULT '',
    local_file    TEXT NOT NULL DEFAULT '',
    web_link      TEXT NOT NULL DEFAULT ''
);

-- name: idx_episodes_media
CREATE INDEX IF NOT EXISTS idx_episodes_media ON episodes(media_item_id);

-- name: entities
-- People / organizations / fictional characters (legacy category='Entity'
-- rows). TEXT ids preserve the legacy `ent-xxxxxxxx` / uuid4 ids.
CREATE TABLE IF NOT EXISTS entities (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    first_name TEXT NOT NULL DEFAULT '',
    last_name  TEXT NOT NULL DEFAULT '',
    type       TEXT NOT NULL DEFAULT 'Person',
    role       TEXT NOT NULL DEFAULT '',
    rating     REAL NOT NULL DEFAULT 0,
    year       INTEGER,
    notes      TEXT NOT NULL DEFAULT '',
    image_path TEXT NOT NULL DEFAULT '',
    date_added TEXT NOT NULL DEFAULT (date('now')),
    extra      TEXT NOT NULL DEFAULT '{}'
);

-- name: idx_entities_name
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);

-- name: credits
-- Per-entity credit sub-records (legacy credit_list JSON array).
CREATE TABLE IF NOT EXISTS credits (
    id         TEXT PRIMARY KEY,
    entity_id  TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    title      TEXT NOT NULL DEFAULT '',
    role       TEXT NOT NULL DEFAULT '',
    year       INTEGER,
    rating     REAL NOT NULL DEFAULT 0,
    review     TEXT NOT NULL DEFAULT '',
    image_path TEXT NOT NULL DEFAULT '',
    web_link   TEXT NOT NULL DEFAULT ''
);

-- name: idx_credits_entity
CREATE INDEX IF NOT EXISTS idx_credits_entity ON credits(entity_id);

-- name: media_entity
-- Replaces media_items.associated_entities / entities.associated_content
-- (previously kept bidirectionally consistent by Python loops).
CREATE TABLE IF NOT EXISTS media_entity (
    media_item_id TEXT NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    entity_id     TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    PRIMARY KEY (media_item_id, entity_id)
);

-- name: idx_media_entity_entity
CREATE INDEX IF NOT EXISTS idx_media_entity_entity ON media_entity(entity_id);

-- name: entity_entity
-- Undirected peer link (replaces entities.associated_entities).
-- Stored with entity_a < entity_b so each pair exists exactly once.
CREATE TABLE IF NOT EXISTS entity_entity (
    entity_a TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    entity_b TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    PRIMARY KEY (entity_a, entity_b),
    CHECK (entity_a < entity_b)
);

-- name: idx_entity_entity_b
CREATE INDEX IF NOT EXISTS idx_entity_entity_b ON entity_entity(entity_b);

-- ===========================================================================
-- Image domain (from the PostgreSQL image index)
-- ===========================================================================

-- name: groups
CREATE TABLE IF NOT EXISTS groups (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- name: subgroups
CREATE TABLE IF NOT EXISTS subgroups (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    UNIQUE (name, group_id)
);

-- name: idx_subgroups_group
CREATE INDEX IF NOT EXISTS idx_subgroups_group ON subgroups(group_id);

-- name: images
-- Normalized: group/subgroup are FKs (the Postgres schema stored both text
-- columns and separate tables). phash = 64-bit perceptual hash as signed int.
CREATE TABLE IF NOT EXISTS images (
    id            INTEGER PRIMARY KEY,
    file_path     TEXT NOT NULL UNIQUE,
    filename      TEXT NOT NULL,
    file_size     INTEGER NOT NULL DEFAULT 0,
    width         INTEGER,
    height        INTEGER,
    phash         INTEGER,
    group_id      INTEGER REFERENCES groups(id)    ON DELETE SET NULL,
    subgroup_id   INTEGER REFERENCES subgroups(id) ON DELETE SET NULL,
    date_added    TEXT NOT NULL DEFAULT (datetime('now')),
    date_modified TEXT
);

-- name: idx_images_group
CREATE INDEX IF NOT EXISTS idx_images_group ON images(group_id);

-- name: idx_images_subgroup
CREATE INDEX IF NOT EXISTS idx_images_subgroup ON images(subgroup_id);

-- name: idx_images_filename
CREATE INDEX IF NOT EXISTS idx_images_filename ON images(filename);

-- name: idx_images_phash
CREATE INDEX IF NOT EXISTS idx_images_phash ON images(phash) WHERE phash IS NOT NULL;

-- ===========================================================================
-- Shared vocabulary
-- ===========================================================================

-- name: tags
-- Unified typed vocabulary: Artist/Series/Character/General/Meta (image side)
-- + Genre/Tag (from the listings CSV split). type NULL = untyped.
CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    type TEXT
);

-- name: image_tags
CREATE TABLE IF NOT EXISTS image_tags (
    image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id)   ON DELETE CASCADE,
    PRIMARY KEY (image_id, tag_id)
);

-- name: idx_image_tags_tag
CREATE INDEX IF NOT EXISTS idx_image_tags_tag ON image_tags(tag_id);

-- name: media_tags
CREATE TABLE IF NOT EXISTS media_tags (
    media_item_id TEXT    NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    tag_id        INTEGER NOT NULL REFERENCES tags(id)        ON DELETE CASCADE,
    PRIMARY KEY (media_item_id, tag_id)
);

-- name: idx_media_tags_tag
CREATE INDEX IF NOT EXISTS idx_media_tags_tag ON media_tags(tag_id);

-- ===========================================================================
-- Cross-domain links (DB.8)
-- ===========================================================================

-- name: media_groups
CREATE TABLE IF NOT EXISTS media_groups (
    media_item_id TEXT    NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    group_id      INTEGER NOT NULL REFERENCES groups(id)      ON DELETE CASCADE,
    PRIMARY KEY (media_item_id, group_id)
);

-- name: idx_media_groups_group
CREATE INDEX IF NOT EXISTS idx_media_groups_group ON media_groups(group_id);

-- name: entity_images
CREATE TABLE IF NOT EXISTS entity_images (
    entity_id TEXT    NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    image_id  INTEGER NOT NULL REFERENCES images(id)   ON DELETE CASCADE,
    PRIMARY KEY (entity_id, image_id)
);

-- name: idx_entity_images_image
CREATE INDEX IF NOT EXISTS idx_entity_images_image ON entity_images(image_id);

-- ===========================================================================
-- Search infrastructure (DB.7)
-- ===========================================================================

-- name: embeddings
-- owner_type: 'image' | 'media_item' | 'entity'; owner_id: images.id as text
-- or the TEXT PK. vector = little-endian float32 array, dim entries.
CREATE TABLE IF NOT EXISTS embeddings (
    owner_type TEXT    NOT NULL,
    owner_id   TEXT    NOT NULL,
    model      TEXT    NOT NULL,
    dim        INTEGER NOT NULL,
    vector     BLOB    NOT NULL,
    PRIMARY KEY (owner_type, owner_id, model)
);

-- name: idx_embeddings_scope
CREATE INDEX IF NOT EXISTS idx_embeddings_scope ON embeddings(owner_type, model);

-- name: vector_index
-- Persisted ANN index blobs (one per owner_type × model), rebuilt on demand.
CREATE TABLE IF NOT EXISTS vector_index (
    owner_type TEXT NOT NULL,
    model      TEXT NOT NULL,
    data       BLOB NOT NULL,
    built_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (owner_type, model)
);

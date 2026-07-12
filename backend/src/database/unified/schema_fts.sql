-- ---------------------------------------------------------------------------
-- Unified Library Database — FTS5 layer (Phase DB, DB.1)
--
-- Applied after schema.sql, and only when the linked SQLCipher was built with
-- FTS5 (checked at runtime; schema_meta.fts_enabled records the outcome and
-- search_repo falls back to LIKE queries when it is '0').
--
-- External-content tables: the base tables own the data; triggers keep the
-- FTS shadow in sync. content_rowid uses the implicit rowid of the base
-- table (present even with TEXT primary keys).
-- ---------------------------------------------------------------------------

-- name: media_fts
CREATE VIRTUAL TABLE IF NOT EXISTS media_fts USING fts5(
    title, review, creator,
    content='media_items', content_rowid='rowid'
);

-- name: media_fts_triggers
CREATE TRIGGER IF NOT EXISTS media_fts_ai AFTER INSERT ON media_items BEGIN
    INSERT INTO media_fts(rowid, title, review, creator)
    VALUES (new.rowid, new.title, new.review, new.creator);
END;
CREATE TRIGGER IF NOT EXISTS media_fts_ad AFTER DELETE ON media_items BEGIN
    INSERT INTO media_fts(media_fts, rowid, title, review, creator)
    VALUES ('delete', old.rowid, old.title, old.review, old.creator);
END;
CREATE TRIGGER IF NOT EXISTS media_fts_au AFTER UPDATE ON media_items BEGIN
    INSERT INTO media_fts(media_fts, rowid, title, review, creator)
    VALUES ('delete', old.rowid, old.title, old.review, old.creator);
    INSERT INTO media_fts(rowid, title, review, creator)
    VALUES (new.rowid, new.title, new.review, new.creator);
END;

-- name: entity_fts
CREATE VIRTUAL TABLE IF NOT EXISTS entity_fts USING fts5(
    name, notes,
    content='entities', content_rowid='rowid'
);

-- name: entity_fts_triggers
CREATE TRIGGER IF NOT EXISTS entity_fts_ai AFTER INSERT ON entities BEGIN
    INSERT INTO entity_fts(rowid, name, notes)
    VALUES (new.rowid, new.name, new.notes);
END;
CREATE TRIGGER IF NOT EXISTS entity_fts_ad AFTER DELETE ON entities BEGIN
    INSERT INTO entity_fts(entity_fts, rowid, name, notes)
    VALUES ('delete', old.rowid, old.name, old.notes);
END;
CREATE TRIGGER IF NOT EXISTS entity_fts_au AFTER UPDATE ON entities BEGIN
    INSERT INTO entity_fts(entity_fts, rowid, name, notes)
    VALUES ('delete', old.rowid, old.name, old.notes);
    INSERT INTO entity_fts(rowid, name, notes)
    VALUES (new.rowid, new.name, new.notes);
END;

-- name: image_fts
CREATE VIRTUAL TABLE IF NOT EXISTS image_fts USING fts5(
    filename, file_path,
    content='images', content_rowid='id'
);

-- name: image_fts_triggers
CREATE TRIGGER IF NOT EXISTS image_fts_ai AFTER INSERT ON images BEGIN
    INSERT INTO image_fts(rowid, filename, file_path)
    VALUES (new.id, new.filename, new.file_path);
END;
CREATE TRIGGER IF NOT EXISTS image_fts_ad AFTER DELETE ON images BEGIN
    INSERT INTO image_fts(image_fts, rowid, filename, file_path)
    VALUES ('delete', old.id, old.filename, old.file_path);
END;
CREATE TRIGGER IF NOT EXISTS image_fts_au AFTER UPDATE ON images BEGIN
    INSERT INTO image_fts(image_fts, rowid, filename, file_path)
    VALUES ('delete', old.id, old.filename, old.file_path);
    INSERT INTO image_fts(rowid, filename, file_path)
    VALUES (new.id, new.filename, new.file_path);
END;

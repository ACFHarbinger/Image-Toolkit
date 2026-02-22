-- name: upsert_tag_entity
INSERT INTO tags (name) VALUES (%s)
ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
RETURNING id;

-- name: upsert_tag
INSERT INTO tags (name, type) VALUES (%s, %s)
ON CONFLICT (name) DO UPDATE SET type = EXCLUDED.type;

-- name: delete_tag
DELETE FROM tags WHERE name = %s;

-- name: rename_tag
UPDATE tags SET name = %s WHERE name = %s;

-- name: update_tag_type
UPDATE tags SET type = %s WHERE name = %s;

-- name: get_all_tags
SELECT name FROM tags ORDER BY name;

-- name: get_all_tags_with_types
SELECT name, type FROM tags ORDER BY name;

-- name: get_image_tags
SELECT t.name FROM tags t
JOIN image_tags it ON t.id = it.tag_id
WHERE it.image_id = %s;

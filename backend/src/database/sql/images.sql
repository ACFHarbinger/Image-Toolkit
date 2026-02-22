-- name: upsert_image
INSERT INTO images
    (file_path, filename, file_size, width, height, group_name, subgroup_name, date_added, date_modified, embedding)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (file_path) DO UPDATE SET
    file_size = EXCLUDED.file_size,
    width = EXCLUDED.width,
    height = EXCLUDED.height,
    group_name = EXCLUDED.group_name,
    subgroup_name = EXCLUDED.subgroup_name,
    date_modified = %s,
    embedding = EXCLUDED.embedding
RETURNING id;

-- name: delete_image
DELETE FROM images WHERE id = %s;

-- name: get_image_id_by_path
SELECT id FROM images WHERE file_path = %s;

-- name: get_image_by_id
SELECT * FROM images WHERE id = %s;

-- name: get_image_group_name
SELECT group_name FROM images WHERE id = %s;

-- name: delete_image_tags
DELETE FROM image_tags WHERE image_id = %s;

-- name: insert_image_tag
INSERT INTO image_tags (image_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;

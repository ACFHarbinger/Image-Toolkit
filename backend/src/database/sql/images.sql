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

-- §4.6 Perceptual hash deduplication -------------------------------------------

-- name: update_phash
-- Store the 64-bit perceptual hash (signed BIGINT) for a single image.
UPDATE images SET phash = %s WHERE id = %s;

-- name: find_near_duplicates_phash
-- Return all images whose perceptual hash is within *threshold* Hamming bits of
-- the query hash.  Hamming distance is computed via XOR then bit_count on the
-- 64-bit representation.  Results are ordered closest-first.
-- Parameters: %s = query_phash BIGINT, %s = query_phash BIGINT (repeated for bit_count), %s = threshold INT, %s = limit INT
SELECT
    id,
    file_path,
    filename,
    group_name,
    subgroup_name,
    phash,
    bit_count(phash::bit(64) # (%s)::bigint::bit(64)) AS hamming_dist
FROM images
WHERE phash IS NOT NULL
  AND bit_count(phash::bit(64) # (%s)::bigint::bit(64)) <= %s
ORDER BY hamming_dist ASC
LIMIT %s;

-- name: vacuum
VACUUM;

-- name: vacuum_full
VACUUM FULL;

-- name: reindex
REINDEX DATABASE CURRENT_DATABASE;

-- name: drop_image_tags
DROP TABLE IF EXISTS image_tags CASCADE;

-- name: drop_images
DROP TABLE IF EXISTS images CASCADE;

-- name: drop_tags
DROP TABLE IF EXISTS tags CASCADE;

-- name: drop_groups
DROP TABLE IF EXISTS groups CASCADE;

-- name: drop_subgroups
DROP TABLE IF EXISTS subgroups CASCADE;

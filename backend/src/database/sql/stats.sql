-- name: count_images
SELECT COUNT(*) FROM images;

-- name: count_tags
SELECT COUNT(*) FROM tags;

-- name: count_groups
SELECT COUNT(*) FROM groups;

-- name: count_subgroups
SELECT COUNT(*) FROM subgroups;

-- name: sum_file_size
SELECT SUM(file_size) FROM images;

-- name: max_date_added
SELECT MAX(date_added) FROM images;

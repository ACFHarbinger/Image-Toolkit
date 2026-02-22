-- name: upsert_group
INSERT INTO groups (name) VALUES (%s)
ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
RETURNING id;

-- name: insert_group
INSERT INTO groups (name) VALUES (%s)
ON CONFLICT (name) DO NOTHING;

-- name: upsert_subgroup
INSERT INTO subgroups (name, group_id) VALUES (%s, %s)
ON CONFLICT (name, group_id) DO NOTHING;

-- name: delete_group
DELETE FROM groups WHERE name = %s;

-- name: delete_subgroup
DELETE FROM subgroups s USING groups g
WHERE s.group_id = g.id AND s.name = %s AND g.name = %s;

-- name: rename_group_in_images
UPDATE images SET group_name = %s WHERE group_name = %s;

-- name: rename_group_in_groups
UPDATE groups SET name = %s WHERE name = %s;

-- name: rename_subgroup_in_images
UPDATE images SET subgroup_name = %s WHERE subgroup_name = %s AND group_name = %s;

-- name: rename_subgroup_in_subgroups
UPDATE subgroups s SET name = %s
FROM groups g
WHERE s.group_id = g.id AND s.name = %s AND g.name = %s;

-- name: get_all_groups
SELECT name FROM groups ORDER BY name;

-- name: get_all_subgroups
SELECT DISTINCT name FROM subgroups ORDER BY name;

-- name: get_subgroups_for_group
SELECT s.name FROM subgroups s
JOIN groups g ON s.group_id = g.id
WHERE g.name = %s
ORDER BY s.name;

-- name: get_all_subgroups_detailed
SELECT s.name, g.name
FROM subgroups s
JOIN groups g ON s.group_id = g.id
ORDER BY g.name, s.name;

-- name: create_extension
CREATE EXTENSION IF NOT EXISTS vector;

-- name: create_table_images
CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_size BIGINT,
    width INTEGER,
    height INTEGER,
    group_name TEXT,
    subgroup_name TEXT,
    date_added TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    date_modified TIMESTAMP WITHOUT TIME ZONE,
    embedding vector({embedding_dim})
);

-- name: create_table_groups
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL
);

-- name: create_table_subgroups
CREATE TABLE IF NOT EXISTS subgroups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
    UNIQUE(name, group_id)
);

-- name: create_table_tags
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(255)
);

-- name: create_table_image_tags
CREATE TABLE IF NOT EXISTS image_tags (
    image_id INTEGER REFERENCES images(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (image_id, tag_id)
);

-- name: create_index_group
CREATE INDEX IF NOT EXISTS idx_images_group ON images(group_name);

-- name: create_index_subgroup
CREATE INDEX IF NOT EXISTS idx_images_subgroup ON images(subgroup_name);

-- name: create_index_path
CREATE INDEX IF NOT EXISTS idx_images_path ON images(file_path);

-- name: create_index_embedding
CREATE INDEX IF NOT EXISTS idx_images_embedding ON images USING hnsw (embedding vector_l2_ops) WHERE embedding IS NOT NULL;

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create groups table
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL
);

-- Create subgroups table
CREATE TABLE IF NOT EXISTS subgroups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
    UNIQUE(name, group_id)
);

-- Create tags table
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(255)
);

-- Create images table with pgvector support
CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_size BIGINT,
    width INTEGER,
    height INTEGER,
    group_name TEXT,
    subgroup_name TEXT,
    date_added TIMESTAMP WITH TIME ZONE NOT NULL,
    date_modified TIMESTAMP WITH TIME ZONE,
    embedding vector(128)
);

-- Create image_tags junction table
CREATE TABLE IF NOT EXISTS image_tags (
    image_id INTEGER REFERENCES images(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (image_id, tag_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_images_group ON images(group_name);
CREATE INDEX IF NOT EXISTS idx_images_subgroup ON images(subgroup_name);
CREATE INDEX IF NOT EXISTS idx_images_path ON images(file_path);
CREATE INDEX IF NOT EXISTS idx_images_embedding ON images USING hnsw (embedding vector_l2_ops) WHERE embedding IS NOT NULL;

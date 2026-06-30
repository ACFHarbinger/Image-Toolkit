-- Anime training pipeline schema additions
-- Extends the core images/tags schema with video ingestion,
-- quality metadata, hybrid captions, embeddings, and training run bookkeeping.

-- ───────────────────────────────────────────────────────────────
-- Video source catalogue
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS video_sources (
    id              BIGSERIAL PRIMARY KEY,
    path            TEXT NOT NULL UNIQUE,
    blake3          BYTEA NOT NULL,
    duration_sec    DOUBLE PRECISION,
    fps             DOUBLE PRECISION,
    width           INT,
    height          INT,
    codec           TEXT,
    series_tag      TEXT,
    licensed        BOOLEAN DEFAULT FALSE,
    inserted_at     TIMESTAMPTZ DEFAULT now()
);

-- ───────────────────────────────────────────────────────────────
-- Individual frames extracted from video sources
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS video_frames (
    id              BIGSERIAL PRIMARY KEY,
    image_id        BIGINT NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    video_id        BIGINT NOT NULL REFERENCES video_sources(id) ON DELETE CASCADE,
    scene_idx       INT NOT NULL,
    pts_seconds     DOUBLE PRECISION NOT NULL,
    frame_idx       BIGINT NOT NULL,
    is_keyframe     BOOLEAN DEFAULT FALSE,
    UNIQUE (video_id, scene_idx, frame_idx)
);

CREATE INDEX IF NOT EXISTS ix_vf_video_id ON video_frames (video_id);
CREATE INDEX IF NOT EXISTS ix_vf_image_id ON video_frames (image_id);

-- ───────────────────────────────────────────────────────────────
-- Per-image quality scores (populated by QA pass)
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS image_quality (
    image_id        BIGINT PRIMARY KEY REFERENCES images(id) ON DELETE CASCADE,
    fg_ratio        REAL,           -- BiRefNet foreground fraction [0,1]
    blur_lap_var    REAL,           -- Laplacian variance (>80 = acceptably sharp)
    niqe            REAL,           -- lower is better (no-reference IQA)
    brisque         REAL,           -- lower is better
    flat_field_norm REAL,           -- BaSiC flat-field deviation
    motion_blur     REAL,           -- Sobel orientation coherence [0,1]
    compression     REAL,           -- DCT block-artefact ratio
    accept          BOOLEAN DEFAULT NULL,
    reject_reason   TEXT,
    audited_at      TIMESTAMPTZ
);

-- ───────────────────────────────────────────────────────────────
-- Hybrid captions (WD14 tags + Florence-2 natural language)
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS image_captions (
    image_id        BIGINT PRIMARY KEY REFERENCES images(id) ON DELETE CASCADE,
    wd14_general    TEXT[],
    wd14_character  TEXT[],
    wd14_rating     TEXT[],
    nl_caption      TEXT,
    pruned_tags     TEXT[] NOT NULL,
    trigger_word    TEXT,
    final_caption   TEXT NOT NULL,
    captioned_at    TIMESTAMPTZ DEFAULT now()
);

-- ───────────────────────────────────────────────────────────────
-- Extended embedding vectors (CLIP-L, CLIP-G, Siamese, pHash)
-- ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS image_embeddings (
    image_id        BIGINT PRIMARY KEY REFERENCES images(id) ON DELETE CASCADE,
    siamese_512     vector(512),
    clip_l_768      vector(768),
    clip_g_1280     vector(1280),
    phash64         BIGINT
);

CREATE INDEX IF NOT EXISTS ix_emb_siamese_hnsw ON image_embeddings
    USING hnsw (siamese_512 vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_emb_clipl_hnsw ON image_embeddings
    USING hnsw (clip_l_768  vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_emb_clipg_hnsw ON image_embeddings
    USING hnsw (clip_g_1280 vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_emb_phash ON image_embeddings (phash64);

-- ───────────────────────────────────────────────────────────────
-- Training run bookkeeping
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS training_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    method          TEXT NOT NULL,      -- 'lora','dora','locon','loha','lokr','dreambooth','full'
    base_model      TEXT NOT NULL,      -- e.g. 'NoobAI-XL-Vpred-1.0'
    config_json     JSONB NOT NULL,
    started_at      TIMESTAMPTZ DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    final_loss      REAL,
    final_fid       REAL,
    final_kid       REAL,
    output_path     TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS training_run_images (
    run_id          UUID REFERENCES training_runs(id) ON DELETE CASCADE,
    image_id        BIGINT REFERENCES images(id) ON DELETE CASCADE,
    repeats         INT DEFAULT 1,
    PRIMARY KEY (run_id, image_id)
);

-- Audit prompts and seeds stored at run start for memorization checks
CREATE TABLE IF NOT EXISTS training_run_audit_prompts (
    run_id          UUID REFERENCES training_runs(id) ON DELETE CASCADE,
    prompt          TEXT NOT NULL,
    seed            INT NOT NULL,
    PRIMARY KEY (run_id, prompt, seed)
);

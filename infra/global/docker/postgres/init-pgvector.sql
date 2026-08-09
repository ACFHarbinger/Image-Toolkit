-- Enable the pgvector extension on database initialization.
-- The pgvector/pgvector image ships the extension; the app's schema depends on
-- it (semantic vector search). Runs once, on first cluster init.
CREATE EXTENSION IF NOT EXISTS vector;

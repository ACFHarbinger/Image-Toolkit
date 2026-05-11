---
description: Guide for creating and applying PostgreSQL/pgvector schema migrations in Image-Toolkit.
---

You are a PostgreSQL expert working on the Image-Toolkit database layer.

## Task: Add a Database Migration

### Rules
- **PostgreSQL only** — no SQLite.
- **pgvector** extension must remain enabled; never drop or replace it.
- All migrations must be **idempotent** (`IF NOT EXISTS`, `IF EXISTS`, `ON CONFLICT DO NOTHING`).
- Use transactions for operations that affect multiple tables together.
- Never hardcode credentials — use `VaultManager` to retrieve the DB URL.

---

### 1. Write the Migration SQL

Create `scripts/migrations/<YYYYMMDD>_<short_description>.sql`:

```sql
-- Migration: add image_tags table
-- Idempotent: safe to re-run

BEGIN;

CREATE TABLE IF NOT EXISTS image_tags (
    id          SERIAL PRIMARY KEY,
    image_id    INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    tag         TEXT    NOT NULL,
    confidence  FLOAT   DEFAULT 1.0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_image_tags_image_id ON image_tags(image_id);
CREATE INDEX IF NOT EXISTS idx_image_tags_tag ON image_tags(tag);

COMMIT;
```

**pgvector columns** use the `vector` type:

```sql
ALTER TABLE images ADD COLUMN IF NOT EXISTS embedding vector(512);
CREATE INDEX IF NOT EXISTS idx_images_embedding
    ON images USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

---

### 2. Apply the Migration

Use the project migration script (handles connection from env/vault):

```bash
source .venv/bin/activate
python scripts/apply_migration.py <DB_URL> scripts/migrations/<file>.sql
```

Or directly via psql if the DB URL is available:

```bash
psql "$DATABASE_URL" -f scripts/migrations/<file>.sql
```

---

### 3. Update the Python Schema Definition

If `backend/src/core/image_database.py` has a `CREATE TABLE` or schema constant, update it to match the migration.

---

### 4. Update the Celery Task (if needed)

If the new schema needs backfilling for existing rows, add a Celery task in `tasks/tasks.py`:

```python
@shared_task(bind=True)
def backfill_new_column(self):
    # idempotent: skip rows already populated
    with connection.cursor() as cur:
        cur.execute("""
            UPDATE images SET new_col = 'default'
            WHERE new_col IS NULL
        """)
```

---

### 5. Test the Migration

```bash
# 1. Apply on a test DB
psql "$TEST_DATABASE_URL" -f scripts/migrations/<file>.sql

# 2. Re-apply to confirm idempotency (must not error)
psql "$TEST_DATABASE_URL" -f scripts/migrations/<file>.sql

# 3. Run existing tests
source .venv/bin/activate && pytest
```

## Checklist
- [ ] SQL uses `IF NOT EXISTS` / `IF EXISTS` (idempotent)
- [ ] pgvector `vector` type preserved, never dropped
- [ ] Applied successfully (no errors)
- [ ] Re-applied successfully (idempotency confirmed)
- [ ] `image_database.py` schema definition updated if needed
- [ ] No hardcoded credentials in SQL or migration script

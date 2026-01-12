I’m going to scan the repo for the Tauri backend and related files, then open key Rust/React files to review the current implementation before suggesting corrections.
Here’s a focused code review of the current Tauri + React migration, with concrete fixes and what to do next.

**Findings**
- frontend/src-tauri/Cargo.toml:20
  - Missing async/runtime and DB deps. No `tokio`, `anyhow`/`thiserror`, or `sqlx` + pgvector support. This blocks Step 1 (database layer).
- frontend/src-tauri/src/core_commands.rs:47 and :75
  - Heavy CPU/IO (batch convert, merge) run synchronously on the command thread. Risk of UI hangs; AGENTS.md requires off-main-thread work.
- frontend/src-tauri/src/wallpaper_commands.rs:59
  - Spawns Python “main.py” via `Command::new("python")` with an implicit working dir. Brittle and a security risk. AGENTS.md recommends using sidecars; this should be migrated.
- frontend/src-tauri/src/wallpaper_commands.rs:19
  - Config file stored in `~/.myapp_slideshow_config.json`. Prefer Tauri’s app config dir (`app.path().app_config_dir()`) for portability and sandboxed OS conventions.
- frontend/src-tauri/src/wallpaper_commands.rs:118
  - Uses external `which` binary to resolve qdbus. Prefer the `which` crate (or handle PATH resolution via Rust) to avoid shelling out.
- frontend/src/tabs/database/SearchTab.tsx
  - Search is mocked; no wiring to backend. This matches the “Gap” and “Task 2”, but means the most important UX is currently a stub.
- frontend/src/api.ts
  - Dead code (hardcoded Python API base). Nothing imports it; it risks confusion and future divergence.

**Corrections**
- Make heavy Tauri commands non-blocking
  - Convert to async commands and offload blocking work using `tauri::async_runtime::spawn_blocking` (or `tokio::task::spawn_blocking`) to satisfy the “no blocking on UI thread” rule.
  - Example (convert): wrap the batch call inside `spawn_blocking(...).await.map_err(|e| e.to_string())?`.
- Use app config directory for slideshow settings
  - Replace `home_dir().join(".myapp_slideshow_config.json")` with `app.path().app_config_dir()?.join("slideshow_config.json")`. Update reads/writes accordingly.
- Avoid shelling out to “which”
  - Replace the external command lookup with the `which` crate or a simple PATH walk using Rust’s std APIs.
- Remove or gate dead `frontend/src/api.ts`
  - Either delete it or annotate as “legacy” with a clear TODO and keep it unused to avoid accidental imports.

**Database Layer (Step 1)**
- Dependencies (frontend/src-tauri/Cargo.toml)
  - Add:
    - `tokio = { version = "1", features = ["rt-multi-thread", "macros"] }`
    - `anyhow = "1", thiserror = "1"`
    - `sqlx = { version = "0.7", features = ["runtime-tokio-rustls", "postgres", "macros", "uuid", "chrono", "migrate"] }`
    - `pgvector = { version = "0.3", features = ["sqlx"] }`
    - Optionally `once_cell = "1"` for lazy globals if desired.
- Connection management
  - Create a `db.rs` with a `struct Db { pool: sqlx::PgPool }`.
  - Initialize once in `run()` setup and `.manage(Db)` on the Tauri builder, reading `DATABASE_URL` (via env/dotenv) and running migrations if present.
  - Commands that need DB access accept `tauri::State<Db>` and use the pooled connection.
- Types and schema
  - Ensure `CREATE EXTENSION IF NOT EXISTS vector;` is in your migrations.
  - Model image rows with proper typed fields (ids, paths, tags, embedding vector). Use `pgvector::Vector` or `pgvector::VectorRef` for embeddings.
- Command stubs
  - `#[tauri::command] async fn search_images(db: State<Db>, q: SearchQuery) -> Result<Vec<ImageHit>, String>`
  - `#[tauri::command] async fn get_tags(db: State<Db>) -> Result<Vec<String>, String>`
  - Keep return types Serde-friendly; convert `anyhow::Error` to `String`.
- Frontend wiring
  - Replace mock in `SearchTab` with `invoke("search_images", {...})` and `invoke("get_tags")`. Maintain paging client-side to start.

**Open Questions**
- What is the expected Postgres URL source for Tauri? Env file next to the app, OS keychain, or your VaultManager via sidecar? (AGENTS.md: use VaultManager; we can wire a sidecar or prompt on first run.)
- Do we already have pgvector migrations/schema in the Python backend that we should mirror exactly? If so, link to the DDL so we keep parity.
- Is there any existing tagging/embedding pipeline we should read-only mirror first (search-only), then later port the writers to Rust?

**Next Steps**
1) Add `sqlx`, `tokio`, `pgvector` deps and a `Db` state managed by Tauri.
2) Implement `search_images` + `get_tags` with minimal schema and migrations.
3) Make `convert_image_batch` and `merge_images` async and offload blocking work.
4) Move slideshow config to `app_config_dir`; replace external `which`.
5) Wire `SearchTab` to the Tauri commands and drop the mock path.

If you want, I can apply item 1–3 now (Cargo.toml, `db.rs`, `lib.rs` state, async command changes) and leave SearchTab wiring for a quick follow-up. Also, yes—proceeding with sqlx and the database connection in Rust is the right next move. To start, I’ll need:
- `DATABASE_URL` format you prefer (env or config file location).
- The current Postgres schema (especially the pgvector column type and table names), or approval to create a minimal initial schema and migrations.

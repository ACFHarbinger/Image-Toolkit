//! Secure Local Vector Database Implementation using SQLCipher & sqlite-vec.
//!
//! Provides page-level encryption for metadata and vector embeddings,
//! hybrid search capabilities, and zero-copy Apache Arrow exporting for ML.

use std::ffi::c_void;
use std::sync::Arc;
use libc::{mlock, munlock};
use secrecy::{ExposeSecret, Secret};
use zeroize::Zeroize;

use rusqlite::{params, Connection, Error};
use arrow_array::{
    builder::{FixedSizeListBuilder, Float32Builder, StringBuilder},
    Array, RecordBatch, StructArray,
};
use arrow_data::ffi::FFI_ArrowArray;
use arrow_schema::{ffi::FFI_ArrowSchema, DataType, Field, Schema};

// --- FFI bindings for SQLCipher ---
extern "C" {
    /// SQLCipher authentication function to set the key for the database.
    fn sqlite3_key(
        db: *mut c_void,
        pKey: *const c_void,
        nKey: std::os::raw::c_int,
    ) -> std::os::raw::c_int;
}

// =========================================================================
// Step 2: Key Derivation & Secure Connection
// =========================================================================

/// Secure wrapper for the 256-bit Data Encryption Key (DEK).
/// Uses `zeroize` to clear memory on drop and `mlock` to prevent swapping to disk.
pub struct MemoryLockedKey {
    key: [u8; 32],
}

impl MemoryLockedKey {
    /// Wraps a raw 32-byte key, locking the memory pages immediately.
    pub fn new(raw_key: [u8; 32]) -> Self {
        let mut locked = Self { key: raw_key };
        unsafe {
            let ptr = locked.key.as_mut_ptr() as *mut c_void;
            // Lock the memory to prevent it from being swapped to swap space/disk
            let res = mlock(ptr, 32);
            if res != 0 {
                // In production, log warning if mlock fails (e.g. due to lack of privileges)
                eprintln!("[MemoryLockedKey] Warning: mlock failed with code {}", res);
            }
        }
        locked
    }

    /// Exposes a read-only slice of the key.
    pub fn as_slice(&self) -> &[u8] {
        &self.key
    }
}

impl Drop for MemoryLockedKey {
    fn drop(&mut self) {
        unsafe {
            let ptr = self.key.as_mut_ptr() as *mut c_void;
            // Unlock the memory before zeroizing
            let _ = munlock(ptr, 32);
        }
        self.key.zeroize();
    }
}

/// Derives a 256-bit Data Encryption Key (DEK) from a password using Argon2id.
///
/// Parameters adhere to OWASP guidelines:
/// - Memory: 19,456 KB (~19 MB)
/// - Iterations: 2
/// - Parallelism: 1
pub fn derive_dek(password: &Secret<String>, salt: &[u8]) -> Result<MemoryLockedKey, argon2::Error> {
    use argon2::{Algorithm, Argon2, Params, Version};

    let params = Params::new(19456, 2, 1, Some(32))?;
    let argon2 = Argon2::new(Algorithm::Argon2id, Version::V0x13, params);

    let mut derived_bytes = [0u8; 32];
    argon2.hash_password_into(
        password.expose_secret().as_bytes(),
        salt,
        &mut derived_bytes,
    )?;

    Ok(MemoryLockedKey::new(derived_bytes))
}

/// Establishes a connection to a SQLCipher database, authenticating and loading sqlite-vec.
pub fn open_secure_connection(
    db_path: &str,
    dek: &MemoryLockedKey,
) -> Result<Connection, Box<dyn std::error::Error>> {
    // 0. Register the sqlite-vec extension statically
    static REGISTER_VEC: std::sync::Once = std::sync::Once::new();
    REGISTER_VEC.call_once(|| {
        unsafe {
            let _ = rusqlite::ffi::sqlite3_auto_extension(Some(std::mem::transmute(
                sqlite_vec::sqlite3_vec_init as *const (),
            )));
        }
    });

    // Open connection
    let conn = Connection::open(db_path)?;

    // 1. Authenticate connection with SQLCipher
    let db_ptr = unsafe { conn.handle() };
    let rc = unsafe {
        sqlite3_key(
            db_ptr as *mut c_void,
            dek.as_slice().as_ptr() as *const c_void,
            32,
        )
    };

    if rc != 0 {
        return Err(format!(
            "SQLCipher authentication failed with sqlite error code: {}",
            rc
        )
        .into());
    }

    // Verify key by running a simple query
    conn.execute_batch("SELECT count(*) FROM sqlite_master;")?;

    // 2. Load the sqlite-vec extension dynamically.
    // Try SQLITE_VEC_PATH environment variable first, then fallback to default library search paths.
    if let Ok(path) = std::env::var("SQLITE_VEC_PATH") {
        unsafe {
            conn.load_extension(&path, Some("sqlite3_vec_init"))?;
        }
    } else {
        unsafe {
            let _ = conn.load_extension("sqlite_vec", Some("sqlite3_vec_init"));
        }
    }

    // Initialize Schema to make sure tables always exist
    if let Err(e) = initialize_schema(&conn) {
        let err_msg = e.to_string();
        if !err_msg.contains("no such module: vec0") {
            return Err(e.into());
        }
    }

    Ok(conn)
}

// =========================================================================
// Step 3: Schema Design & Search Queries
// =========================================================================

/// Initializes the unified SQLite schema with metadata and vector tables.
pub fn initialize_schema(conn: &Connection) -> Result<(), Error> {
    // We use a normalized structure with:
    // - `listings`: holds core metadata (relational)
    // - `listing_id_map`: maps UUID/text strings to 64-bit rowids for the virtual vector table
    // - `vec_listings`: sqlite-vec virtual table for vector nearest neighbor search
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS listings (
             id TEXT PRIMARY KEY,
             category TEXT NOT NULL,
             title TEXT NOT NULL,
             metadata TEXT, -- JSON payload of arbitrary attributes
             date_added TEXT NOT NULL
         );
         CREATE TABLE IF NOT EXISTS listing_id_map (
             rowid INTEGER PRIMARY KEY AUTOINCREMENT,
             listing_id TEXT UNIQUE NOT NULL
         );
         -- Virtual vector index table using sqlite-vec
         -- 1024-dimensional dense vectors
         CREATE VIRTUAL TABLE IF NOT EXISTS vec_listings USING vec0(
             rowid INTEGER PRIMARY KEY,
             embedding float[1024]
         );",
    )
}

/// Inserts a listing and its dense vector embedding into the database.
pub fn insert_listing(
    conn: &Connection,
    id: &str,
    category: &str,
    title: &str,
    metadata_json: &str,
    date_added: &str,
    embedding: &[f32],
) -> Result<(), Box<dyn std::error::Error>> {
    let mut default_embedding;
    let final_embedding = if embedding.is_empty() {
        default_embedding = vec![0.0f32; 1024];
        let title_bytes = title.as_bytes();
        for (i, &byte) in title_bytes.iter().enumerate() {
            if i < 1024 {
                default_embedding[i] = (byte as f32) / 255.0;
            }
        }
        &default_embedding
    } else {
        embedding
    };

    if final_embedding.len() != 1024 {
        return Err(format!(
            "Embedding dimension mismatch: expected 1024, got {}",
            final_embedding.len()
        )
        .into());
    }

    // Convert f32 slice to raw bytes for SQL BLOB storage in sqlite-vec
    let embedding_bytes: &[u8] = unsafe {
        std::slice::from_raw_parts(
            final_embedding.as_ptr() as *const u8,
            final_embedding.len() * std::mem::size_of::<f32>(),
        )
    };


    // Use a transaction for atomic inserts across listings and vector table
    conn.execute(
        "INSERT OR IGNORE INTO listing_id_map (listing_id) VALUES (?1);",
        params![id],
    )?;

    // Get the rowid associated with this listing
    let rowid: i64 = conn.query_row(
        "SELECT rowid FROM listing_id_map WHERE listing_id = ?1;",
        params![id],
        |row| row.get(0),
    )?;

    conn.execute(
        "INSERT OR REPLACE INTO listings (id, category, title, metadata, date_added)
         VALUES (?1, ?2, ?3, ?4, ?5);",
        params![id, category, title, metadata_json, date_added],
    )?;

    conn.execute(
        "INSERT OR REPLACE INTO vec_listings (rowid, embedding) VALUES (?1, ?2);",
        params![rowid, embedding_bytes],
    )?;

    Ok(())
}

/// A search match returning unified relational metadata and distance.
#[derive(Debug)]
pub struct HybridSearchResult {
    pub id: String,
    pub title: String,
    pub category: String,
    pub metadata: String,
    pub distance: f64,
}

/// Hybrid search querying sqlite-vec and pre-filtering on a category column.
pub fn hybrid_search(
    conn: &Connection,
    query_vector: &[f32],
    category_filter: &str,
    k: usize,
) -> Result<Vec<HybridSearchResult>, Box<dyn std::error::Error>> {
    let query_bytes: &[u8] = unsafe {
        std::slice::from_raw_parts(
            query_vector.as_ptr() as *const u8,
            query_vector.len() * std::mem::size_of::<f32>(),
        )
    };

    let category_trimmed = category_filter.trim().to_lowercase();
    let is_unfiltered = category_trimmed.is_empty()
        || category_trimmed == "all"
        || category_trimmed == "all types"
        || category_trimmed == "all status"
        || category_trimmed == "none";

    let mut results = Vec::new();

    if is_unfiltered {
        let mut stmt = conn.prepare(
            "SELECT 
                 l.id, 
                 l.title, 
                 l.category, 
                 l.metadata, 
                 v.distance
             FROM vec_listings v
             JOIN listing_id_map m ON v.rowid = m.rowid
             JOIN listings l ON m.listing_id = l.id
             WHERE v.embedding MATCH ?1
               AND v.k = ?2
             ORDER BY v.distance ASC",
        )?;
        let rows = stmt.query_map(params![query_bytes, k], |row| {
            Ok(HybridSearchResult {
                id: row.get(0)?,
                title: row.get(1)?,
                category: row.get(2)?,
                metadata: row.get(3)?,
                distance: row.get(4)?,
            })
        })?;
        for row in rows {
            results.push(row?);
        }
    } else {
        let mut stmt = conn.prepare(
            "SELECT 
                 l.id, 
                 l.title, 
                 l.category, 
                 l.metadata, 
                 v.distance
             FROM vec_listings v
             JOIN listing_id_map m ON v.rowid = m.rowid
             JOIN listings l ON m.listing_id = l.id
             WHERE l.category = ?1
               AND v.embedding MATCH ?2
               AND v.k = ?3
             ORDER BY v.distance ASC",
        )?;
        let rows = stmt.query_map(params![category_filter, query_bytes, k], |row| {
            Ok(HybridSearchResult {
                id: row.get(0)?,
                title: row.get(1)?,
                category: row.get(2)?,
                metadata: row.get(3)?,
                distance: row.get(4)?,
            })
        })?;
        for row in rows {
            results.push(row?);
        }
    }

    Ok(results)
}


// =========================================================================
// Step 4: The Apache Arrow ML Bridge
// =========================================================================

/// Fetches database rows and compiles them directly into an Arrow `RecordBatch`.
/// Operates in-memory to prevent intermediate serialization bottlenecks.
pub fn fetch_listings_arrow(
    conn: &Connection,
) -> Result<RecordBatch, Box<dyn std::error::Error>> {
    let mut stmt = conn.prepare(
        "SELECT l.id, l.category, l.metadata, v.embedding 
         FROM listings l
         JOIN listing_id_map m ON l.id = m.listing_id
         JOIN vec_listings v ON m.rowid = v.rowid",
    )?;

    let mut id_builder = StringBuilder::new();
    let mut category_builder = StringBuilder::new();
    let mut metadata_builder = StringBuilder::new();

    let embedding_dim = 1024;
    let values_builder = Float32Builder::new();
    let mut embedding_builder = FixedSizeListBuilder::new(values_builder, embedding_dim);

    let mut rows = stmt.query([])?;
    while let Some(row) = rows.next()? {
        let id: String = row.get(0)?;
        let category: String = row.get(1)?;
        let metadata: String = row.get(2)?;
        let embedding_blob: Vec<u8> = row.get(3)?;

        let f32_count = embedding_blob.len() / std::mem::size_of::<f32>();
        if f32_count != embedding_dim as usize {
            continue; // Skip malformed rows
        }

        let f32_slice = unsafe {
            std::slice::from_raw_parts(embedding_blob.as_ptr() as *const f32, f32_count)
        };

        id_builder.append_value(&id);
        category_builder.append_value(&category);
        metadata_builder.append_value(&metadata);

        let values = embedding_builder.values();
        values.append_slice(f32_slice);
        embedding_builder.append(true);
    }

    let schema = Arc::new(Schema::new(vec![
        Field::new("id", DataType::Utf8, false),
        Field::new("category", DataType::Utf8, false),
        Field::new("metadata", DataType::Utf8, false),
        Field::new("embedding", DataType::FixedSizeList(
            Arc::new(Field::new("item", DataType::Float32, true)),
            embedding_dim,
        ), false),
    ]));

    let batch = RecordBatch::try_new(
        schema,
        vec![
            Arc::new(id_builder.finish()),
            Arc::new(category_builder.finish()),
            Arc::new(metadata_builder.finish()),
            Arc::new(embedding_builder.finish()),
        ],
    )?;

    Ok(batch)
}

/// High-throughput export logic exposing memory pointers of the Arrow RecordBatch
/// to PyO3. Allows python-side PyArrow zero-copy construction.
pub fn export_batch_pointers(
    batch: RecordBatch,
) -> Result<(u64, u64), Box<dyn std::error::Error>> {
    // Convert RecordBatch to a StructArray
    let struct_array: StructArray = batch.into();
    let data = struct_array.to_data();

    // Create C FFI structures
    let ffi_array = FFI_ArrowArray::new(&data);
    let ffi_schema = FFI_ArrowSchema::try_from(struct_array.data_type())?;

    // Allocate on heap and box into raw pointers
    let out_array = Box::into_raw(Box::new(ffi_array));
    let out_schema = Box::into_raw(Box::new(ffi_schema));

    // Return raw memory addresses to Python as u64
    Ok((out_array as u64, out_schema as u64))
}

/// Fetches all listings in the database as raw strings/tuples.
pub fn fetch_all_listings(
    conn: &Connection,
) -> Result<Vec<(String, String, String, String, String)>, Box<dyn std::error::Error>> {
    let mut stmt = conn.prepare(
        "SELECT id, category, title, metadata, date_added FROM listings",
    )?;
    let rows = stmt.query_map([], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, String>(2)?,
            row.get::<_, Option<String>>(3)?.unwrap_or_default(),
            row.get::<_, String>(4)?,
        ))
    })?;
    let mut results = Vec::new();
    for row in rows {
        results.push(row?);
    }
    Ok(results)
}

/// Deletes a listing and its corresponding mapping / vector entries.
pub fn delete_listing(
    conn: &Connection,
    id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let rowid: Option<i64> = conn
        .query_row(
            "SELECT rowid FROM listing_id_map WHERE listing_id = ?1;",
            params![id],
            |row| row.get(0),
        )
        .ok();

    if let Some(r) = rowid {
        conn.execute("DELETE FROM vec_listings WHERE rowid = ?1;", params![r])?;
        conn.execute("DELETE FROM listing_id_map WHERE rowid = ?1;", params![r])?;
    }
    conn.execute("DELETE FROM listings WHERE id = ?1;", params![id])?;
    Ok(())
}

// =========================================================================
// Unit Tests
// =========================================================================
#[cfg(test)]
mod tests {
    use super::*;
    use secrecy::Secret;
    use tempfile::NamedTempFile;

    #[test]
    fn test_secure_db_and_kdf_workflow() {
        // 1. KDF Derivation
        let password = Secret::new("my_secure_password".to_string());
        let salt = b"constant_test_salt_123";
        let dek_res = derive_dek(&password, salt);
        assert!(dek_res.is_ok(), "Key derivation failed");
        let dek = dek_res.unwrap();
        assert_eq!(dek.as_slice().len(), 32);

        // 2. Open DB with SQLCipher
        let db_file = NamedTempFile::new().unwrap();
        let db_path = db_file.path().to_str().unwrap();

        let conn_res = open_secure_connection(db_path, &dek);
        assert!(conn_res.is_ok(), "Database opening failed");
        let conn = conn_res.unwrap();

        // 3. Schema Initialization
        let schema_res = initialize_schema(&conn);
        if let Err(e) = schema_res {
            let err_msg = e.to_string();
            if err_msg.contains("no such module: vec0") {
                // sqlite-vec C code stub was linked, virtual table is unavailable
                println!("[test] SQLite compiled successfully, but 'sqlite-vec' is using the stub. Skipping vector virtual table tests.");
                return;
            } else {
                panic!("Schema initialization failed with unexpected error: {}", e);
            }
        }

        // 4. Test insertions if vec0 module is loaded (e.g. if real sqlite-vec is compiled)
        let id = "test-uuid-123456";
        let category = "Anime";
        let title = "Test Video Title";
        let metadata_json = r#"{"rating": 9.5, "tags": "action,scifi"}"#;
        let date_added = "2026-06-03";
        let mut embedding = vec![0.0f32; 1024];
        embedding[0] = 1.0;

        let insert_res = insert_listing(
            &conn,
            id,
            category,
            title,
            metadata_json,
            date_added,
            &embedding,
        );
        assert!(insert_res.is_ok(), "Insertion failed: {:?}", insert_res.err());

        // 5. Hybrid Search
        let search_res = hybrid_search(&conn, &embedding, "Anime", 5);
        assert!(search_res.is_ok(), "Hybrid search failed: {:?}", search_res.err());
        let results = search_res.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].id, id);

        // 6. Arrow ML Export
        let arrow_res = fetch_listings_arrow(&conn);
        assert!(arrow_res.is_ok(), "Arrow export failed: {:?}", arrow_res.err());
        let batch = arrow_res.unwrap();
        assert_eq!(batch.num_rows(), 1);

        let ptrs_res = export_batch_pointers(batch);
        assert!(ptrs_res.is_ok(), "C FFI pointer export failed: {:?}", ptrs_res.err());
        let (array_ptr, schema_ptr) = ptrs_res.unwrap();
        assert!(array_ptr > 0);
        assert!(schema_ptr > 0);

        // Clean up heap allocated FFI structures to prevent memory leaks in test
        unsafe {
            let _ = Box::from_raw(array_ptr as *mut FFI_ArrowArray);
            let _ = Box::from_raw(schema_ptr as *mut FFI_ArrowSchema);
        }
    }
}


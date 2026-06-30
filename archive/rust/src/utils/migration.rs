//! Legacy JSON to SQLCipher / sqlite-vec Migration Utility.
//!
//! Performs batch insertion under an encrypted transaction.

use secrecy::Secret;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::Read;

use crate::core::secure_vector_db::{
    derive_dek, initialize_schema, insert_listing, open_secure_connection,
};

/// Reads legacy listings JSON data and imports it into the secure local SQLCipher database.
pub fn run_migration(
    username: &str,
    password: &str,
    listings_json_path: &str,
    target_db_path: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    // 1. Initialize the derivation process targeting the specified user account and password
    let password = Secret::new(password.to_string());

    // Generate salt by hashing the username
    let mut hasher = Sha256::new();
    hasher.update(username.as_bytes());
    let salt = hasher.finalize();

    // Derive the 256-bit DEK securely
    let dek = derive_dek(&password, &salt).map_err(|e| format!("Argon2 KDF error: {}", e))?;

    // 2. Read and deserialize the legacy JSON listings file(s) into memory
    let mut file = File::open(listings_json_path)?;
    let mut contents = String::new();
    file.read_to_string(&mut contents)?;

    let listings: Vec<Value> = serde_json::from_str(&contents)?;
    println!(
        "[Migration] Deserialized {} legacy records.",
        listings.len()
    );

    // 3. Open the new SQLCipher database utilizing the derived DEK
    let conn = open_secure_connection(target_db_path, &dek)?;

    // Create target tables ( listings, listing_id_map, vec_listings )
    initialize_schema(&conn)?;

    // 4. Populate the unified tables using a transaction for speed and integrity
    conn.execute("BEGIN TRANSACTION;", [])?;

    for item in listings {
        let id = item
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or("Missing listing id")?;

        let category = item
            .get("type")
            .and_then(|v| v.as_str())
            .unwrap_or("Unknown");

        let title = item
            .get("title")
            .and_then(|v| v.as_str())
            .unwrap_or("Untitled");

        let date_added = item
            .get("date_added")
            .and_then(|v| v.as_str())
            .unwrap_or("1970-01-01");

        // Rest of the fields go to metadata JSON column
        let mut metadata_map = match item.clone() {
            Value::Object(map) => map,
            _ => serde_json::Map::new(),
        };
        metadata_map.remove("id");
        metadata_map.remove("type");
        metadata_map.remove("title");
        metadata_map.remove("date_added");

        let metadata_json = serde_json::to_string(&Value::Object(metadata_map))?;

        // 5. Format vector embeddings for sqlite-vec (1024 dimensions)
        // Since the raw JSON does not contain embeddings (which was in Qdrant),
        // we generate a default mock vector normalized from the title hash for demo purposes.
        let mut embedding = vec![0.0f32; 1024];
        let title_bytes = title.as_bytes();
        for (i, &byte) in title_bytes.iter().enumerate() {
            if i < 1024 {
                embedding[i] = (byte as f32) / 255.0;
            }
        }

        insert_listing(
            &conn,
            id,
            category,
            title,
            &metadata_json,
            date_added,
            &embedding,
        )?;
    }

    // 6. Commit the transaction and close the database connection
    conn.execute("COMMIT;", [])?;

    println!("[Migration] Successfully migrated all records to SQLCipher.");

    // Note: The `dek` out-of-scope drop triggers memory zeroing automatically
    Ok(())
}

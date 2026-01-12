use crate::db::{Db, DatabaseStats, ImageRecord, SearchQuery};
use tauri::State;

/// Search for images in the database
#[tauri::command]
pub async fn search_images(
    db: State<'_, Db>,
    query: SearchQuery,
) -> Result<Vec<ImageRecord>, String> {
    db.search_images(query)
        .await
        .map_err(|e| format!("Failed to search images: {}", e))
}

/// Get all tags from the database
#[tauri::command]
pub async fn get_all_tags(db: State<'_, Db>) -> Result<Vec<String>, String> {
    db.get_all_tags()
        .await
        .map_err(|e| format!("Failed to get tags: {}", e))
}

/// Get all groups from the database
#[tauri::command]
pub async fn get_all_groups(db: State<'_, Db>) -> Result<Vec<String>, String> {
    db.get_all_groups()
        .await
        .map_err(|e| format!("Failed to get groups: {}", e))
}

/// Get subgroups for a specific group
#[tauri::command]
pub async fn get_subgroups_for_group(
    db: State<'_, Db>,
    group_name: String,
) -> Result<Vec<String>, String> {
    db.get_subgroups_for_group(&group_name)
        .await
        .map_err(|e| format!("Failed to get subgroups: {}", e))
}

/// Add a new image to the database
#[tauri::command]
pub async fn add_image_to_database(
    db: State<'_, Db>,
    file_path: String,
    filename: String,
    width: Option<i32>,
    height: Option<i32>,
    group_name: Option<String>,
    subgroup_name: Option<String>,
    tags: Option<Vec<String>>,
) -> Result<i32, String> {
    db.add_image(
        &file_path,
        &filename,
        width,
        height,
        group_name.as_deref(),
        subgroup_name.as_deref(),
        tags,
    )
    .await
    .map_err(|e| format!("Failed to add image: {}", e))
}

/// Delete an image from the database
#[tauri::command]
pub async fn delete_image_from_database(db: State<'_, Db>, image_id: i32) -> Result<(), String> {
    db.delete_image(image_id)
        .await
        .map_err(|e| format!("Failed to delete image: {}", e))
}

/// Get database statistics
#[tauri::command]
pub async fn get_database_stats(db: State<'_, Db>) -> Result<DatabaseStats, String> {
    db.get_statistics()
        .await
        .map_err(|e| format!("Failed to get statistics: {}", e))
}

/// Test database connection
#[tauri::command]
pub async fn test_database_connection(db: State<'_, Db>) -> Result<bool, String> {
    db.test_connection()
        .await
        .map_err(|e| format!("Database connection failed: {}", e))
}

/// Batch add images to database
#[tauri::command]
pub async fn batch_add_images(
    db: State<'_, Db>,
    images: Vec<(String, String, Option<String>, Option<String>)>,
) -> Result<Vec<i32>, String> {
    let mut ids = Vec::new();

    for (file_path, filename, group_name, subgroup_name) in images {
        match db
            .add_image(
                &file_path,
                &filename,
                None,
                None,
                group_name.as_deref(),
                subgroup_name.as_deref(),
                None,
            )
            .await
        {
            Ok(id) => ids.push(id),
            Err(e) => {
                log::error!("Failed to add image {}: {}", file_path, e);
            }
        }
    }

    Ok(ids)
}

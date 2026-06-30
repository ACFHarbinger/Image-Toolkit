use std::collections::HashSet;
use walkdir::WalkDir;

#[tauri::command]
pub fn scan_files(
    directory: String,
    extensions: Option<Vec<String>>,
    recursive: Option<bool>,
) -> Result<Vec<String>, String> {
    let exts: Vec<String> = extensions
        .unwrap_or_else(|| {
            vec!["jpg", "jpeg", "png", "webp", "bmp"]
                .into_iter()
                .map(String::from)
                .collect()
        })
        .into_iter()
        .map(|e| e.trim_start_matches('.').to_lowercase())
        .collect();

    let rec = recursive.unwrap_or(true);

    // Simple file scanner implementation
    let mut set = HashSet::new();
    let walker = if rec {
        WalkDir::new(&directory)
    } else {
        WalkDir::new(&directory).max_depth(1)
    };

    for entry in walker.into_iter().filter_map(|e| e.ok()) {
        if entry.file_type().is_file() {
            if let Some(ext) = entry.path().extension().and_then(|s| s.to_str()) {
                let ext_lower = ext.to_lowercase();
                if exts.contains(&ext_lower) {
                    set.insert(entry.path().to_string_lossy().to_string());
                }
            }
        }
    }

    let mut out: Vec<String> = set.into_iter().collect();
    out.sort();
    Ok(out)
}

#[tauri::command]
pub async fn convert_image_batch(
    _pairs: Vec<(String, String)>,
    _output_format: String,
    _delete_original: Option<bool>,
    _aspect_ratio: Option<f32>,
    _ar_mode: Option<String>,
) -> Result<Vec<String>, String> {
    // TODO: Implement image conversion once base library is refactored
    log::warn!("Image conversion not yet implemented in Tauri backend");
    Err("Image conversion not yet implemented".to_string())
}

#[tauri::command]
pub fn delete_files(paths: Vec<String>) -> Result<usize, String> {
    let mut count = 0;
    for path in paths {
        if std::fs::remove_file(&path).is_ok() {
            count += 1;
        }
    }
    Ok(count)
}

#[tauri::command]
pub fn delete_directory(path: String) -> Result<bool, String> {
    std::fs::remove_dir_all(&path)
        .map(|_| true)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn merge_images(
    _image_paths: Vec<String>,
    _output_path: String,
    _config: serde_json::Value,
) -> Result<bool, String> {
    // TODO: Implement image merging once base library is refactored
    log::warn!("Image merging not yet implemented in Tauri backend");
    Err("Image merging not yet implemented".to_string())
}

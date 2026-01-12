use std::collections::HashSet;

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

    // Use a set to avoid duplicates when multiple extensions are provided
    let mut set = HashSet::new();
    for ext in exts {
        let files = base::core::file_system::get_files_by_extension_core(&directory, &ext, rec);
        for f in files {
            set.insert(f);
        }
    }

    let mut out: Vec<String> = set.into_iter().collect();
    out.sort();
    Ok(out)
}

#[tauri::command]
pub async fn convert_image_batch(
    pairs: Vec<(String, String)>,
    output_format: String,
    delete_original: Option<bool>,
    aspect_ratio: Option<f32>,
    ar_mode: Option<String>,
) -> Result<Vec<String>, String> {
    let delete = delete_original.unwrap_or(false);
    let mode = ar_mode.unwrap_or_else(|| "crop".to_string());

    // Offload blocking work to a separate thread
    let result = tauri::async_runtime::spawn_blocking(move || {
        base::core::image_converter::convert_image_batch_core(
            &pairs,
            &output_format,
            delete,
            aspect_ratio,
            &mode,
        )
    })
    .await
    .map_err(|e| format!("Task execution failed: {}", e))?;

    Ok(result)
}

#[tauri::command]
pub fn delete_files(paths: Vec<String>) -> Result<usize, String> {
    let mut count = 0;
    for path in paths {
        if base::core::file_system::delete_path_core(&path) {
            count += 1;
        }
    }
    Ok(count)
}

#[tauri::command]
pub fn delete_directory(path: String) -> Result<bool, String> {
    Ok(base::core::file_system::delete_path_core(&path))
}

#[tauri::command]
pub async fn merge_images(
    image_paths: Vec<String>,
    output_path: String,
    config: serde_json::Value,
) -> Result<bool, String> {
    // Config parsing - extract owned values before moving into closure
    let direction = config["direction"].as_str().unwrap_or("horizontal").to_string();
    let spacing = config["spacing"].as_u64().unwrap_or(0) as u32;
    let align_mode = config["alignMode"].as_str().unwrap_or("center").to_string();
    let rows = config["gridRows"].as_u64().unwrap_or(2) as u32;
    let cols = config["gridCols"].as_u64().unwrap_or(2) as u32;

    // Offload blocking work to a separate thread
    let result = tauri::async_runtime::spawn_blocking(move || match direction.as_str() {
        "horizontal" => base::core::image_merger::merge_images_horizontal_core(
            &image_paths,
            &output_path,
            spacing,
            &align_mode,
        )
        .map_err(|e| e.to_string()),
        "vertical" => base::core::image_merger::merge_images_vertical_core(
            &image_paths,
            &output_path,
            spacing,
            &align_mode,
        )
        .map_err(|e| e.to_string()),
        "grid" => base::core::image_merger::merge_images_grid_core(
            &image_paths,
            &output_path,
            rows,
            cols,
            spacing,
        )
        .map_err(|e| e.to_string()),
        _ => Err(format!("Unsupported direction: {}", direction)),
    })
    .await
    .map_err(|e| format!("Task execution failed: {}", e))??;

    Ok(result)
}

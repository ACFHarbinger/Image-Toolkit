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
pub fn convert_image_batch(
    pairs: Vec<(String, String)>,
    output_format: String,
    delete_original: Option<bool>,
    aspect_ratio: Option<f32>,
    ar_mode: Option<String>,
) -> Result<Vec<String>, String> {
    let delete = delete_original.unwrap_or(false);
    let mode = ar_mode.unwrap_or_else(|| "crop".to_string());

    let result = base::core::image_converter::convert_image_batch_core(
        &pairs,
        &output_format,
        delete,
        aspect_ratio,
        &mode,
    );
    Ok(result)
}

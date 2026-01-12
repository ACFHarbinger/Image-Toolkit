use base::core::wallpaper::{
    evaluate_kde_script_core, get_kde_desktops_core, set_wallpaper_gnome_core, KdeDesktop,
};
use std::collections::HashMap;
use std::path::Path;
use std::process::Command;

#[tauri::command]
pub fn set_wallpaper(
    path_map: HashMap<String, String>,
    _monitors: Vec<usize>, // Simplification: we'll derive monitors from system for now or just use path_map keys
    style: String,
) -> Result<(), String> {
    let qdbus = get_qdbus_path()?;

    // Check desktop environment (simplified check)
    let desktop_env = std::env::var("XDG_CURRENT_DESKTOP").unwrap_or_default();

    if desktop_env.contains("KDE") {
        set_wallpaper_kde(path_map, style, &qdbus)
    } else {
        // GNOME or fallback
        // Simplification: just pick the first image and set it globally for now if GNOME
        if let Some(path) = path_map.values().next() {
            set_wallpaper_gnome_core(
                &format!(
                    "file://{}",
                    Path::new(path)
                        .canonicalize()
                        .map_err(|e| e.to_string())?
                        .display()
                ),
                &style.to_lowercase(),
            )
            .map_err(|e| e.to_string())?;
        }
        Ok(())
    }
}

fn get_qdbus_path() -> Result<String, String> {
    // Try common names
    for bin in ["qdbus-qt6", "qdbus", "qdbus-qt5"] {
        if Command::new("which")
            .arg(bin)
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
        {
            return Ok(bin.to_string());
        }
    }
    // Fallback if not found via which, but might exist in path
    Ok("qdbus".to_string())
}

fn set_wallpaper_kde(
    path_map: HashMap<String, String>,
    style_name: String,
    qdbus: &str,
) -> Result<(), String> {
    let desktops = get_kde_desktops_core(qdbus)?;

    // Simple mapping: Map string keys "0", "1" to index.
    // In a real app we'd do the topological sort from Python.
    // For this prototype, we assume keys correspond to desktop indices if they parse to int.

    let mut script_parts = Vec::new();

    // Fill mode mapping
    // "Scaled, Keep Proportions" -> 2
    // "Scaled" -> 2
    // "Centered" -> 6
    // "Tiled" -> 3
    // "Stretched" -> 0
    // "Fill" -> 2 (default)
    let fill_mode = match style_name.as_str() {
        "Stretched" => 0,
        "Tiled" => 3,
        "Centered" => 6,
        _ => 2, // Default to Scaled/Fill
    };

    for (monitor_id, path) in path_map {
        if path.is_empty() {
            continue;
        }

        let file_uri = format!(
            "file://{}",
            Path::new(&path)
                .canonicalize()
                .map_err(|e| e.to_string())?
                .display()
        );

        // Try to parse monitor_id as index
        if let Ok(idx) = monitor_id.parse::<usize>() {
            script_parts.push(format!(
                r#"
                {{
                    var d = desktops()[{}];
                    if (d && d.screen >= 0) {{
                        d.wallpaperPlugin = "org.kde.image";
                        d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
                        d.writeConfig("Image", "{}");
                        d.writeConfig("FillMode", {});
                        d.reloadConfig();
                    }}
                }}
                "#,
                idx, file_uri, fill_mode
            ));
        }
    }

    if script_parts.is_empty() {
        return Ok(());
    }

    let full_script = script_parts.join("\n");
    evaluate_kde_script_core(qdbus, &full_script).map(|_| ())
}

use serde::Serialize;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::Manager;

#[derive(Serialize)]
pub struct MonitorInfo {
    pub name: String,
    pub width: u32,
    pub height: u32,
    pub x: i32,
    pub y: i32,
}

fn get_slideshow_config_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let config_dir = app
        .path()
        .app_config_dir()
        .map_err(|e| e.to_string())?;

    // Ensure the config directory exists
    std::fs::create_dir_all(&config_dir).map_err(|e| e.to_string())?;

    Ok(config_dir.join("slideshow_config.json"))
}

#[tauri::command]
pub fn get_monitors(app: tauri::AppHandle) -> Result<Vec<MonitorInfo>, String> {
    let monitors = app.available_monitors().map_err(|e| e.to_string())?;
    let mut info = Vec::new();
    for monitor in monitors {
        let size = monitor.size();
        let pos = monitor.position();
        info.push(MonitorInfo {
            name: monitor
                .name()
                .map(|s| s.to_string())
                .unwrap_or_else(|| "Unknown".to_string()),
            width: size.width,
            height: size.height,
            x: pos.x,
            y: pos.y,
        });
    }
    Ok(info)
}

#[tauri::command]
pub fn update_slideshow_config(
    app: tauri::AppHandle,
    config: serde_json::Value,
) -> Result<(), String> {
    let path = get_slideshow_config_path(&app)?;
    let content = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    std::fs::write(path, content).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn toggle_slideshow_daemon(app: tauri::AppHandle, running: bool) -> Result<(), String> {
    // 1. Update config file 'running' field
    let path = get_slideshow_config_path(&app)?;
    let mut config: serde_json::Value = if path.exists() {
        let content = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
        serde_json::from_str(&content).map_err(|e| e.to_string())?
    } else {
        serde_json::json!({})
    };
    config["running"] = serde_json::json!(running);
    let content = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    std::fs::write(&path, content).map_err(|e| e.to_string())?;

    // 2. Start process if running
    if running {
        // We assume 'python' is in path and we are in project root or can find main.py
        // In a real app, we'd use sidecars or properly bundled python.
        Command::new("python")
            .arg("main.py")
            .arg("slideshow")
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn set_wallpaper(
    path_map: HashMap<String, String>,
    _monitors: Vec<usize>,
    style: String,
) -> Result<(), String> {
    // TODO: Implement wallpaper setting once base library is refactored
    log::warn!("Wallpaper setting not yet fully implemented in Tauri backend");

    // Check desktop environment
    let desktop_env = std::env::var("XDG_CURRENT_DESKTOP").unwrap_or_default();

    if desktop_env.contains("GNOME") {
        // Try to set via gsettings for GNOME
        if let Some(path) = path_map.values().next() {
            let file_uri = format!(
                "file://{}",
                Path::new(path)
                    .canonicalize()
                    .map_err(|e| e.to_string())?
                    .display()
            );

            let _ = Command::new("gsettings")
                .args(&[
                    "set",
                    "org.gnome.desktop.background",
                    "picture-uri",
                    &file_uri,
                ])
                .output()
                .map_err(|e| e.to_string())?;

            let _ = Command::new("gsettings")
                .args(&[
                    "set",
                    "org.gnome.desktop.background",
                    "picture-uri-dark",
                    &file_uri,
                ])
                .output();

            return Ok(());
        }
    }

    Err("Wallpaper setting not fully implemented for this desktop environment".to_string())
}

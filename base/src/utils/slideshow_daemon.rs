use anyhow::{Context, Result};
use directories::UserDirs;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::thread;
use std::time::Duration;

// Internal modules access
// Since this is a bin in the same crate, it can't directly use 'base::...' unless 'base' is a dependency (which it is, implicitly or explicitly).
// Actually, a binary in the same crate can't easily access 'crate::core' if 'core' is just modules in lib.rs.
// It acts like an external user of the library.
use base::core::wallpaper;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Config {
    #[serde(default)]
    pub running: bool,
    #[serde(default = "default_interval")]
    pub interval_seconds: u64,
    #[serde(default = "default_style")]
    pub style: String,
    #[serde(default)]
    pub monitor_queues: HashMap<String, Vec<String>>,
    #[serde(default)]
    pub current_paths: HashMap<String, String>,
    #[serde(default)]
    pub monitor_geometries: HashMap<String, Geometry>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Geometry {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

pub fn default_interval() -> u64 {
    300
}
pub fn default_style() -> String {
    "Fill".to_string()
}

fn get_config_path() -> Result<PathBuf> {
    let user_dirs = UserDirs::new().context("Could not find user home directory")?;
    Ok(user_dirs.home_dir().join(".myapp_slideshow_config.json"))
}

fn load_config(path: &PathBuf) -> Result<Config> {
    if !path.exists() {
        return Ok(Config {
            running: false,
            interval_seconds: 300,
            style: "Fill".to_string(),
            monitor_queues: HashMap::new(),
            current_paths: HashMap::new(),
            monitor_geometries: HashMap::new(),
        });
    }
    let content = fs::read_to_string(path).context("Failed to read config file")?;
    let config: Config = serde_json::from_str(&content).context("Failed to parse config JSON")?;
    Ok(config)
}

fn save_config(path: &PathBuf, config: &Config) -> Result<()> {
    let content = serde_json::to_string_pretty(config).context("Failed to serialize config")?;
    fs::write(path, content).context("Failed to write config file")?;
    Ok(())
}

pub fn get_next_image(queue: &[String], current: Option<&String>) -> Option<String> {
    if queue.is_empty() {
        return None;
    }
    let idx = match current {
        Some(curr) => queue
            .iter()
            .position(|r| r == curr)
            .map(|i| (i + 1) % queue.len())
            .unwrap_or(0),
        None => 0,
    };
    Some(queue[idx].clone())
}

fn apply_wallpaper_kde(
    path_map: &HashMap<String, String>,
    style: &str,
    geometries: &HashMap<String, Geometry>,
) -> Result<()> {
    let mut script = String::new();

    let fill_mode = match style {
        "Scaled, Keep Proportions" => 1,
        "Scaled" => 2,
        "Scaled and Cropped (Zoom)" => 0,
        "Centered" => 6,
        "Tiled" => 3,
        "Center Tiled" => 4,
        "Span" => 5,
        _ => 2, // Default to Scaled
    };

    println!("Fetching KDE desktops for mapping...");
    let kde_desktops = match wallpaper::get_kde_desktops_core("qdbus") {
        Ok(ds) => ds,
        Err(e) => {
            eprintln!("Failed to get KDE desktops: {}", e);
            Vec::new()
        }
    };

    for (monitor_id, path) in path_map {
        let mut target_index: Option<u32> = None;

        // Try mapping by geometry
        if let Some(geom) = geometries.get(monitor_id) {
            if let Some(match_desktop) =
                kde_desktops.iter().find(|d| d.x == geom.x && d.y == geom.y)
            {
                target_index = Some(match_desktop.index);
            }
        }

        // Fallback to direct parse
        let i = target_index.unwrap_or_else(|| monitor_id.parse().unwrap_or(0));

        println!(
            "Monitor {} -> KDE Desktop {} (Path: {})",
            monitor_id, i, path
        );

        let file_uri = if path.starts_with("file://") {
            path.clone()
        } else {
            format!("file://{}", path)
        };

        script.push_str(&format!(
            "{{ var d = desktops()[{}]; if (d && d.screen >= 0) {{ d.wallpaperPlugin = \"org.kde.image\"; d.currentConfigGroup = Array(\"Wallpaper\", \"org.kde.image\", \"General\"); d.writeConfig(\"Image\", \"{}\"); d.writeConfig(\"FillMode\", {}); d.reloadConfig(); }} }}",
            i, file_uri, fill_mode
        ));
    }

    if script.is_empty() {
        return Ok(());
    }

    wallpaper::evaluate_kde_script_core("qdbus", &script)
        .map_err(|e| anyhow::anyhow!("KDE qdbus error: {}", e))?;

    Ok(())
}

fn apply_wallpaper_gnome(path_map: &HashMap<String, String>, style: &str) -> Result<()> {
    if let Some(path) = path_map.values().next() {
        let abs_path = fs::canonicalize(path).context("Invalid path")?;
        let file_uri = format!("file://{}", abs_path.to_string_lossy());
        let mode = match style.to_lowercase().as_str() {
            "none" | "wallpaper" | "centered" | "scaled" | "stretched" | "zoom" | "spanned" => {
                style.to_lowercase()
            }
            _ => "zoom".to_string(),
        };
        wallpaper::set_wallpaper_gnome_core(&file_uri, &mode)
            .map_err(|e| anyhow::anyhow!("GNOME error: {}", e))?;
    }
    Ok(())
}

fn main() -> Result<()> {
    eprintln!("Slideshow Daemon (Rust) Started.");
    let config_path = get_config_path()?;
    eprintln!("Config path: {:?}", config_path);

    let mut is_first_run = true;

    loop {
        let mut config = match load_config(&config_path) {
            Ok(c) => c,
            Err(e) => {
                eprintln!("Error: Failed to load config: {}. Waiting...", e);
                thread::sleep(Duration::from_secs(10));
                continue;
            }
        };

        if !config.running {
            eprintln!("Slideshow disabled in config. Exiting.");
            break;
        }

        let mut next_paths = HashMap::new();
        let mut changed = false;

        let mut monitor_ids: Vec<_> = config.monitor_queues.keys().cloned().collect();
        monitor_ids.sort_by_key(|a| a.parse::<u32>().unwrap_or(u32::MAX));

        for mid in monitor_ids {
            if let Some(queue) = config.monitor_queues.get(&mid) {
                let current = config.current_paths.get(&mid);
                if let Some(next) = get_next_image(queue, current) {
                    if is_first_run || current != Some(&next) {
                        next_paths.insert(mid.clone(), next.clone());
                        config.current_paths.insert(mid.clone(), next);
                        changed = true;
                    }
                }
            }
        }
        is_first_run = false;

        if changed {
            let desktop_env = std::env::var("XDG_CURRENT_DESKTOP")
                .or_else(|_| std::env::var("XDG_SESSION_DESKTOP"))
                .or_else(|_| std::env::var("DESKTOP_SESSION"))
                .unwrap_or_default()
                .to_lowercase();

            let res = if desktop_env.contains("kde") || desktop_env.contains("plasma") {
                apply_wallpaper_kde(&next_paths, &config.style, &config.monitor_geometries)
            } else if desktop_env.contains("gnome") || desktop_env.contains("unity") {
                apply_wallpaper_gnome(&next_paths, &config.style)
            } else {
                Err(anyhow::anyhow!(
                    "Unsupported or undetected desktop environment: '{}'. Please ensure XDG_CURRENT_DESKTOP is set.",
                    desktop_env
                ))
            };

            if let Err(e) = res {
                eprintln!("Error applying wallpaper: {}", e);
            } else {
                if let Err(e) = save_config(&config_path, &config) {
                    eprintln!("Error saving config state: {}", e);
                }
            }
        }

        thread::sleep(Duration::from_secs(config.interval_seconds));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_defaults() {
        let json = r#"{}"#;
        let config: Config = serde_json::from_str(json).unwrap();
        assert_eq!(config.running, false);
        assert_eq!(config.interval_seconds, 300);
        assert_eq!(config.style, "Fill");
        assert!(config.monitor_queues.is_empty());
    }

    #[test]
    fn test_config_parsing() {
        let json = r#"{
            "running": true,
            "interval_seconds": 60,
            "style": "Fit",
            "monitor_queues": {
                "0": ["/path/a.jpg", "/path/b.jpg"]
            }
        }"#;
        let config: Config = serde_json::from_str(json).unwrap();
        assert!(config.running);
        assert_eq!(config.interval_seconds, 60);
        assert_eq!(config.style, "Fit");
        assert_eq!(config.monitor_queues["0"].len(), 2);
    }

    #[test]
    fn test_get_next_image_logic() {
        let queue = vec![
            "img1.jpg".to_string(),
            "img2.jpg".to_string(),
            "img3.jpg".to_string(),
        ];

        // Initial -> first
        let next = get_next_image(&queue, None);
        assert_eq!(next, Some("img1.jpg".to_string()));

        // From img1 -> img2
        let next = get_next_image(&queue, Some(&"img1.jpg".to_string()));
        assert_eq!(next, Some("img2.jpg".to_string()));

        // From img2 -> img3
        let next = get_next_image(&queue, Some(&"img2.jpg".to_string()));
        assert_eq!(next, Some("img3.jpg".to_string()));

        // From img3 -> img1 (cycle)
        let next = get_next_image(&queue, Some(&"img3.jpg".to_string()));
        assert_eq!(next, Some("img1.jpg".to_string()));

        // Unknown current -> first
        let next = get_next_image(&queue, Some(&"imgX.jpg".to_string()));
        assert_eq!(next, Some("img1.jpg".to_string()));
    }
}

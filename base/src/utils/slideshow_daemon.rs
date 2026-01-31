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

fn get_best_video_plugin() -> String {
    let reborn_plugin = "luisbocanegra.smart.video.wallpaper.reborn";
    let zren_plugin = "com.github.zren.smartvideowallpaper";
    let smarter_plugin = "smartervideowallpaper";

    let home = UserDirs::new()
        .map(|u| u.home_dir().to_path_buf())
        .unwrap_or_else(|| PathBuf::from("/"));
    let search_paths = vec![
        home.join(".local/share/plasma/wallpapers"),
        PathBuf::from("/usr/share/plasma/wallpapers"),
    ];

    for base_path in &search_paths {
        if base_path.join(reborn_plugin).exists() {
            return reborn_plugin.to_string();
        }
    }
    for base_path in &search_paths {
        if base_path.join(smarter_plugin).exists() {
            return smarter_plugin.to_string();
        }
    }
    for base_path in &search_paths {
        if base_path.join(zren_plugin).exists() {
            return zren_plugin.to_string();
        }
    }

    reborn_plugin.to_string()
}

fn find_qdbus_binary() -> String {
    let candidates = ["qdbus", "qdbus-qt5", "qdbus-qt6", "qdbus6"];
    for bin in candidates {
        if which::which(bin).is_ok() {
            return bin.to_string();
        }
    }
    "qdbus".to_string() // Fallback
}

fn apply_wallpaper_kde(
    path_map: &HashMap<String, String>,
    style: &str,
    geometries: &HashMap<String, Geometry>,
) -> Result<()> {
    let mut script = String::new();
    let qdbus_bin = find_qdbus_binary();

    let mut video_mode_active = false;
    let mut base_style_name = style;
    let mut video_fill_mode = 2; // Default Scaled

    if style.starts_with("SmartVideoWallpaper") && style.contains("::") {
        video_mode_active = true;
        let parts: Vec<&str> = style.split("::").collect();
        if parts.len() > 1 {
            let v_style = parts[1];
            video_fill_mode = match v_style {
                "Keep Proportions" => 1,
                "Scaled and Cropped" => 2,
                "Stretch" => 0,
                _ => 2,
            };
            // Fallback for image part of the logic
            base_style_name = "Fill";
        }
    }

    let fill_mode = match base_style_name {
        "Scaled, Keep Proportions" => 1,
        "Scaled" => 2,
        "Scaled and Cropped (Zoom)" => 0,
        "Centered" => 6,
        "Tiled" => 3,
        "Center Tiled" => 4,
        "Span" => 5,
        "Fill" => 2,
        _ => 2,
    };

    println!("Fetching KDE desktops for mapping...");
    let mut kde_desktops = match wallpaper::get_kde_desktops_core(&qdbus_bin) {
        Ok(ds) => ds,
        Err(e) => {
            eprintln!("Failed to get KDE desktops: {}", e);
            Vec::new()
        }
    };

    // Topological Sort Mapping
    // 1. Sort KDE Desktops by (Y, X)
    kde_desktops.sort_by(|a, b| a.y.cmp(&b.y).then(a.x.cmp(&b.x)));

    // 2. Sort Monitor Geometries by (Y, X)
    let mut monitor_list: Vec<(&String, &Geometry)> = geometries.iter().collect();
    monitor_list.sort_by(|a, b| a.1.y.cmp(&b.1.y).then(a.1.x.cmp(&b.1.x)));

    // 3. Create Mapping: MonitorID -> KdeDesktopIndex
    let mut monitor_to_kde: HashMap<String, u32> = HashMap::new();
    for (idx, (monitor_id, _)) in monitor_list.iter().enumerate() {
        if idx < kde_desktops.len() {
            monitor_to_kde.insert(monitor_id.to_string(), kde_desktops[idx].index);
        }
    }

    let target_plugin = get_best_video_plugin();
    let video_extensions = vec![".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv"];

    for (monitor_id, path) in path_map {
        // Use mapping or fallback to integer parsing
        let i = if let Some(kde_idx) = monitor_to_kde.get(monitor_id) {
            *kde_idx
        } else {
            monitor_id.parse().unwrap_or(0)
        };

        println!(
            "Monitor {} -> KDE Desktop {} (Path: {})",
            monitor_id, i, path
        );

        // KDE Plasma 6 (and some 5 versions) prefers raw paths for org.kde.image
        // We remove the file:// prefix if present, rather than adding it.
        let file_uri = if path.starts_with("file://") {
            path.replace("file://", "")
        } else {
            path.clone()
        };

        let ext = PathBuf::from(path)
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
            .to_lowercase();
        let dot_ext = format!(".{}", ext);

        let is_video = video_extensions.contains(&dot_ext.as_str());

        if is_video && video_mode_active {
            let is_smarter = target_plugin == "smartervideowallpaper";
            let video_key = if is_smarter {
                "VideoWallpaperBackgroundVideo"
            } else {
                "VideoUrls"
            };
            let override_pause = if is_smarter {
                "d.writeConfig('overridePause', true);"
            } else {
                ""
            };

            script.push_str(&format!(
                "{{ 
                    var d = desktops()[{}]; 
                    if (d && d.screen >= 0) {{ 
                        if (d.wallpaperPlugin !== \"{}\") d.wallpaperPlugin = \"{}\"; 
                        d.currentConfigGroup = Array(\"Wallpaper\", d.wallpaperPlugin, \"General\"); 
                        d.writeConfig(\"{}\", \"{}\"); 
                        d.writeConfig(\"FillMode\", {}); 
                        {}
                        d.currentConfigGroup = Array(\"Wallpaper\", \"org.kde.image\", \"General\");
                        d.writeConfig(\"FillMode\", 2);
                        d.writeConfig(\"Color\", \"#00000000\");
                        d.reloadConfig(); 
                    }} 
                }}",
                i, target_plugin, target_plugin, video_key, file_uri, video_fill_mode, override_pause
            ));
        } else {
            script.push_str(&format!(
                "{{ var d = desktops()[{}]; if (d && d.screen >= 0) {{ d.wallpaperPlugin = \"org.kde.image\"; d.currentConfigGroup = Array(\"Wallpaper\", \"org.kde.image\", \"General\"); d.writeConfig(\"Image\", \"{}\"); d.writeConfig(\"FillMode\", {}); d.reloadConfig(); }} }}",
                i, file_uri, fill_mode
            ));
        }
    }

    if script.is_empty() {
        return Ok(());
    }

    wallpaper::evaluate_kde_script_core(&qdbus_bin, &script)
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

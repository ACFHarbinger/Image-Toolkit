use anyhow::{Context, Result};
use base::core::wallpaper;
use directories::UserDirs;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::panic;
use std::path::{Path, PathBuf};
use std::thread;
use std::time::Duration;

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
    #[serde(default)]
    pub last_change_timestamp: u64,
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

fn normalize_path(path: &str) -> String {
    path.trim_start_matches("file://")
        .trim_start_matches("file:/")
        .to_string()
}

fn get_config_path() -> Result<PathBuf> {
    let user_dirs = UserDirs::new().context("Could not find user home directory")?;
    let config_dir = user_dirs.home_dir().join(".image-toolkit");
    if !config_dir.exists() {
        fs::create_dir_all(&config_dir)?;
    }
    Ok(config_dir.join(".myapp_slideshow_config.json"))
}

fn get_pid_path() -> Result<PathBuf> {
    let user_dirs = UserDirs::new().context("Could not find user home directory")?;
    let config_dir = user_dirs.home_dir().join(".image-toolkit");
    if !config_dir.exists() {
        fs::create_dir_all(&config_dir)?;
    }
    Ok(config_dir.join(".myapp_slideshow.pid"))
}

struct PidGuard(PathBuf);
impl PidGuard {
    fn new(path: PathBuf) -> Result<Self> {
        if path.exists() {
            let content = fs::read_to_string(&path).unwrap_or_default();
            if let Ok(old_pid) = content.trim().parse::<u32>() {
                if PathBuf::from(format!("/proc/{}", old_pid)).exists() {
                    let cmdline = fs::read_to_string(format!("/proc/{}/cmdline", old_pid))
                        .unwrap_or_default();
                    if cmdline.contains("slideshow_daemon") || cmdline.contains("python") {
                        anyhow::bail!(
                            "Slideshow daemon is already running (PID: {}). Exiting.",
                            old_pid
                        );
                    }
                }
            }
        }
        fs::write(&path, std::process::id().to_string())?;
        Ok(Self(path))
    }
}
impl Drop for PidGuard {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}

fn load_config(path: &Path) -> Result<Config> {
    if !path.exists() {
        return Ok(Config {
            running: false,
            interval_seconds: 300,
            style: "Fill".to_string(),
            monitor_queues: HashMap::new(),
            current_paths: HashMap::new(),
            monitor_geometries: HashMap::new(),
            last_change_timestamp: 0,
        });
    }
    let content = fs::read_to_string(path).context("Failed to read config file")?;
    let config: Config = serde_json::from_str(&content).context("Failed to parse config JSON")?;
    Ok(config)
}

fn save_config(path: &Path, config: &Config) -> Result<()> {
    let content = serde_json::to_string_pretty(config).context("Failed to serialize config")?;
    fs::write(path, content).context("Failed to write config file")?;
    Ok(())
}

fn select_next_wallpapers(config: &mut Config, increment: bool) -> HashMap<String, String> {
    eprintln!(
        "Selecting next wallpapers for {} monitors... (increment={})",
        config.monitor_queues.len(),
        increment
    );
    let mut selected = HashMap::new();
    let mut monitor_ids: Vec<&String> = config.monitor_queues.keys().collect();
    monitor_ids.sort();

    for monitor_id in monitor_ids {
        let queue = config.monitor_queues.get(monitor_id).unwrap();
        if queue.is_empty() {
            eprintln!("Queue for monitor {} is empty.", monitor_id);
            continue;
        }

        let current_path = config.current_paths.get(monitor_id);
        let mut idx = 0;
        let mut found = false;

        if let Some(path) = current_path {
            let norm_path = normalize_path(path);
            eprintln!(
                "Monitor {} current path normalized: {}",
                monitor_id, norm_path
            );
            for (i, p) in queue.iter().enumerate() {
                let queue_norm_path = normalize_path(p);
                eprintln!("  Comparing with queue item {}: {}", i, queue_norm_path);
                if queue_norm_path == norm_path {
                    idx = i;
                    found = true;
                    eprintln!("  Match found at index {}", i);
                    break;
                }
            }

            if found {
                eprintln!("Monitor {} found current at index {}", monitor_id, idx);
                if increment {
                    idx = (idx + 1) % queue.len();
                    eprintln!("Monitor {} incremented to index {}", monitor_id, idx);
                }
            } else {
                eprintln!(
                    "Monitor {} current path not found in queue. Starting at index 0.",
                    monitor_id
                );
                idx = 0;
            }
        } else {
            eprintln!(
                "Monitor {} has no current path. Starting at index 0.",
                monitor_id
            );
            idx = 0;
        }

        let next_path = queue[idx].clone();
        eprintln!(
            "Monitor {} -> Next path (index {}): {}",
            monitor_id, idx, next_path
        );
        selected.insert(monitor_id.clone(), next_path.clone());
        config.current_paths.insert(monitor_id.clone(), next_path);
    }
    selected
}

fn find_qdbus_binary() -> String {
    let candidates = ["qdbus", "qdbus-qt5", "qdbus-qt6", "qdbus6"];
    for bin in candidates {
        if which::which(bin).is_ok() {
            return bin.to_string();
        }
    }
    "qdbus".to_string()
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

    for base_path in search_paths {
        if base_path.join(reborn_plugin).exists() {
            return reborn_plugin.to_string();
        }
        if base_path.join(zren_plugin).exists() {
            return zren_plugin.to_string();
        }
        if base_path.join(smarter_plugin).exists() {
            return smarter_plugin.to_string();
        }
    }

    reborn_plugin.to_string()
}

fn apply_wallpaper_kde(
    path_map: &HashMap<String, String>,
    style: &str,
    geometries: &HashMap<String, Geometry>,
) -> Result<()> {
    let mut script = String::new();
    let qdbus_bin = find_qdbus_binary();
    eprintln!("Using qdbus binary: {}", qdbus_bin);

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

    kde_desktops.sort_by(|a, b| a.y.cmp(&b.y).then(a.x.cmp(&b.x)));
    let mut monitor_list: Vec<(&String, &Geometry)> = geometries.iter().collect();
    monitor_list.sort_by(|a, b| a.1.y.cmp(&b.1.y).then(a.1.x.cmp(&b.1.x)));

    let mut monitor_to_kde = HashMap::new();
    println!("Monitoring configurations (sorted by geometry):");
    for (monitor_id, g) in &monitor_list {
        eprintln!(
            "  Monitor {}: x={}, y={}, w={}, h={}",
            monitor_id, g.x, g.y, g.width, g.height
        );
    }

    eprintln!("KDE Desktops found: {}", kde_desktops.len());
    for d in &kde_desktops {
        eprintln!(
            "  Desktop {}: screen={}, x={}, y={}",
            d.index, d.screen, d.x, d.y
        );
    }

    for (i, (monitor_id, _)) in monitor_list.iter().enumerate() {
        if i < kde_desktops.len() {
            monitor_to_kde.insert(monitor_id.to_string(), kde_desktops[i].index);
        }
    }

    let video_extensions = vec![".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv"];
    let target_plugin = get_best_video_plugin();

    for (monitor_id, path) in path_map {
        let i = monitor_to_kde
            .get(monitor_id)
            .cloned()
            .unwrap_or_else(|| monitor_id.parse().unwrap_or(0));

        eprintln!(
            "Monitor {} -> KDE Desktop {} (Path: {})",
            monitor_id, i, path
        );

        let file_uri = if !path.starts_with("file://") {
            format!("file://{}", path)
        } else {
            path.clone()
        };
        let raw_path = if path.starts_with("file://") {
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
                        d.wallpaperPlugin = \"{}\"; 
                        d.currentConfigGroup = Array(\"Wallpaper\", \"{}\", \"General\"); 
                        d.writeConfig(\"{}\", \"{}\"); 
                        d.writeConfig(\"FillMode\", {}); 
                        {}
                        d.reloadConfig(); 
                        d.currentConfigGroup = Array(\"Wallpaper\", \"org.kde.image\", \"General\");
                        d.writeConfig(\"FillMode\", 2);
                        d.writeConfig(\"Color\", \"#00000000\");
                    }} 
                }}",
                i,
                target_plugin,
                target_plugin,
                video_key,
                file_uri,
                video_fill_mode,
                override_pause
            ));
        } else {
            script.push_str(&format!(
                "{{ var d = desktops()[{}]; if (d && d.screen >= 0) {{ d.wallpaperPlugin = \"org.kde.image\"; d.currentConfigGroup = Array(\"Wallpaper\", \"org.kde.image\", \"General\"); d.writeConfig(\"Image\", \"{}\"); d.writeConfig(\"FillMode\", {}); d.reloadConfig(); }} }}",
                i, raw_path, fill_mode
            ));
        }
    }

    if !script.is_empty() {
        wallpaper::evaluate_kde_script_core(&qdbus_bin, &script)
            .map_err(|e| anyhow::anyhow!("KDE qdbus error: {}", e))?;
        println!("Successfully applied KDE wallpaper script.");
    }
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
        eprintln!("Successfully applied GNOME wallpaper: {}", file_uri);
    }
    Ok(())
}

#[cfg(target_os = "windows")]
fn apply_wallpaper_windows(path_map: &HashMap<String, String>, style: &str) -> Result<()> {
    if let Some(path) = path_map.values().next() {
        let abs_path = fs::canonicalize(path).context("Invalid path")?;
        let mode = match style.to_lowercase().as_str() {
            "fill" => wallpaper::windows::WallpaperStyle::Fill,
            "fit" => wallpaper::windows::WallpaperStyle::Fit,
            "stretch" => wallpaper::windows::WallpaperStyle::Stretch,
            "tile" => wallpaper::windows::WallpaperStyle::Tile,
            "center" => wallpaper::windows::WallpaperStyle::Center,
            "span" => wallpaper::windows::WallpaperStyle::Span,
            _ => wallpaper::windows::WallpaperStyle::Fill,
        };
        wallpaper::set_wallpaper_windows_core(&abs_path.to_string_lossy(), mode)
            .map_err(|e| anyhow::anyhow!("Windows error: {}", e))?;
    }
    Ok(())
}

fn main() -> Result<()> {
    panic::set_hook(Box::new(|panic_info| {
        let msg = if let Some(s) = panic_info.payload().downcast_ref::<&str>() {
            s.to_string()
        } else if let Some(s) = panic_info.payload().downcast_ref::<String>() {
            s.clone()
        } else {
            "Unknown panic".to_string()
        };
        let location = panic_info
            .location()
            .map(|l| format!(" at {}:{}", l.file(), l.line()))
            .unwrap_or_default();
        eprintln!("PANIC: {}{}", msg, location);
    }));

    if let Err(e) = run() {
        eprintln!("TERMINAL ERROR: {}", e);
        return Err(e);
    }
    Ok(())
}

fn run() -> Result<()> {
    println!("Slideshow Daemon (Rust) Started.");
    let pid_path = get_pid_path()?;
    let _guard = PidGuard::new(pid_path)?;

    let config_path = get_config_path()?;
    eprintln!("Config path: {:?}", config_path);

    let desktop_env = std::env::var("XDG_CURRENT_DESKTOP")
        .or_else(|_| std::env::var("XDG_SESSION_DESKTOP"))
        .or_else(|_| std::env::var("DESKTOP_SESSION"))
        .unwrap_or_default()
        .to_lowercase();
    eprintln!("Detected desktop environment: '{}'", desktop_env);

    let mut first_run = true;
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
            println!("Slideshow disabled in config. Exiting.");
            break;
        }

        if first_run {
            config.current_paths.clear();
        }

        let next_paths = select_next_wallpapers(&mut config, !first_run);
        first_run = false;

        if !next_paths.is_empty() {
            let res = if desktop_env.contains("kde") || desktop_env.contains("plasma") {
                apply_wallpaper_kde(&next_paths, &config.style, &config.monitor_geometries)
            } else if desktop_env.contains("gnome") || desktop_env.contains("ubuntu") {
                apply_wallpaper_gnome(&next_paths, &config.style)
            } else if cfg!(target_os = "windows") {
                #[cfg(target_os = "windows")]
                {
                    apply_wallpaper_windows(&next_paths, &config.style)
                }
                #[cfg(not(target_os = "windows"))]
                {
                    Err(anyhow::anyhow!("Windows support not compiled in"))
                }
            } else {
                Err(anyhow::anyhow!("Unsupported desktop: '{}'", desktop_env))
            };

            if let Err(e) = res {
                eprintln!("Error applying wallpaper: {}", e);
            } else {
                config.last_change_timestamp = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs();
                let _ = save_config(&config_path, &config);
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
        assert_eq!(config.style, "Fill".to_string());
    }
}

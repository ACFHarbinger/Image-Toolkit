use anyhow::{Context, Result};
use base::core::wallpaper;
use directories::UserDirs;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::io::Write;
use std::panic;
use std::path::{Path, PathBuf};
use std::thread;
use std::time::Duration;
use std::env;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Config {
    pub running: bool,
    #[serde(default = "default_interval")]
    pub interval_seconds: u64,
    pub style: String,
    pub monitor_queues: HashMap<String, Vec<String>>,
    pub current_paths: HashMap<String, String>,
    pub monitor_geometries: HashMap<String, Geometry>,
    pub playback_order: String,
    pub last_change_timestamp: u64,
    #[serde(default)]
    pub last_error: Option<String>,
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
pub fn default_order() -> String {
    "Sequential".to_string()
}

fn normalize_path(path: &str) -> String {
    path.trim_start_matches("file://")
        .trim_start_matches("file:/")
        .to_string()
}

fn get_config_dir() -> Result<PathBuf> {
    let user_dirs = UserDirs::new().context("Could not find user home directory")?;
    let config_dir = user_dirs.home_dir().join(".image-toolkit");
    if !config_dir.exists() {
        fs::create_dir_all(&config_dir)?;
    }
    Ok(config_dir)
}

fn get_config_path() -> Result<PathBuf> {
    Ok(get_config_dir()?.join(".myapp_slideshow_config.json"))
}

fn get_pid_path() -> Result<PathBuf> {
    Ok(get_config_dir()?.join(".myapp_slideshow.pid"))
}

struct PidGuard(PathBuf);
impl PidGuard {
    fn new(path: PathBuf) -> Result<Self> {
        if path.exists() {
            if let Ok(old_pid_content) = fs::read_to_string(&path) {
                if let Ok(old_pid) = old_pid_content.trim().parse::<u32>() {
                    if PathBuf::from(format!("/proc/{}", old_pid)).exists() {
                        let cmdline = fs::read_to_string(format!("/proc/{}/cmdline", old_pid))
                            .unwrap_or_default();
                        let is_daemon = cmdline.contains("slideshow_daemon") 
                            && (cmdline.contains("bin") || cmdline.contains("target"));
                        let is_wrapper = cmdline.contains("python") && cmdline.contains("slideshow_daemon.py");
                        if is_daemon || is_wrapper {
                            anyhow::bail!(
                                "Slideshow daemon is already running (PID: {}). Exiting.",
                                old_pid
                            );
                        }
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
            playback_order: "Sequential".to_string(),
            last_change_timestamp: 0,
            last_error: None,
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
    let mut selected = HashMap::new();
    let mut monitor_ids: Vec<&String> = config.monitor_queues.keys().collect();
    monitor_ids.sort();
    for monitor_id in monitor_ids {
        let queue = config.monitor_queues.get(monitor_id).unwrap();
        if queue.is_empty() { continue; }
        let current_path = config.current_paths.get(monitor_id);
        let mut idx = 0;
        let mut found = false;
        if let Some(path) = current_path {
            let norm_path = normalize_path(path);
            for (i, p) in queue.iter().enumerate() {
                if normalize_path(p) == norm_path {
                    idx = i;
                    found = true;
                    break;
                }
            }
        }
        if increment {
            match config.playback_order.as_str() {
                "Random" => {
                    use rand::Rng;
                    idx = rand::thread_rng().gen_range(0..queue.len());
                }
                "Reverse Sequential" => {
                    if found {
                        idx = if idx == 0 { queue.len() - 1 } else { idx - 1 };
                    } else {
                        idx = queue.len() - 1;
                    }
                }
                _ => {
                    idx = if found { (idx + 1) % queue.len() } else { 0 };
                }
            }
        } else if !found {
            match config.playback_order.as_str() {
                "Random" => {
                    use rand::Rng;
                    idx = rand::thread_rng().gen_range(0..queue.len());
                }
                "Reverse Sequential" => idx = queue.len() - 1,
                _ => idx = 0,
            }
        }
        let next_path = queue[idx].clone();
        selected.insert(monitor_id.clone(), next_path.clone());
        config.current_paths.insert(monitor_id.clone(), next_path);
    }
    selected
}

fn find_qdbus_binary() -> String {
    let candidates = ["qdbus6", "qdbus-qt6", "qdbus-qt5", "qdbus"];
    for bin in candidates {
        if let Ok(path) = which::which(bin) {
            let status = std::process::Command::new(&path)
                .arg("--version")
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .status();
            if status.is_ok() && status.unwrap().success() {
                return bin.to_string();
            }
        }
    }
    "qdbus".to_string()
}

fn get_best_video_plugin() -> String {
    let reborn_plugin = "luisbocanegra.smart.video.wallpaper.reborn";
    let zren_plugin = "com.github.zren.smartvideowallpaper";
    let smarter_plugin = "smartervideowallpaper";
    let home = UserDirs::new().map(|u| u.home_dir().to_path_buf()).unwrap_or_else(|| PathBuf::from("/"));
    let search_paths = vec![home.join(".local/share/plasma/wallpapers"), PathBuf::from("/usr/share/plasma/wallpapers")];
    for base_path in search_paths {
        if base_path.join(reborn_plugin).exists() { return reborn_plugin.to_string(); }
        if base_path.join(zren_plugin).exists() { return zren_plugin.to_string(); }
        if base_path.join(smarter_plugin).exists() { return smarter_plugin.to_string(); }
    }
    reborn_plugin.to_string()
}

fn apply_wallpaper_kde(
    path_map: &HashMap<String, String>,
    style: &str,
    geometries: &HashMap<String, Geometry>,
    log_path: &Option<PathBuf>,
) -> Result<()> {
    macro_rules! log {
        ($($arg:tt)*) => {{
            let msg = format!($($arg)*);
            let now = chrono::Local::now().format("[%H:%M:%S]");
            if let Some(ref lp) = log_path {
                if let Ok(mut f) = fs::OpenOptions::new().append(true).open(lp) {
                    let _ = writeln!(f, "{} {}", now, msg);
                }
            }
        }};
    }
    let qdbus_bin = find_qdbus_binary();
    log!("Using qdbus binary: {}", qdbus_bin);
    let mut video_mode_active = false;
    let mut base_style_name = style;
    let mut video_fill_mode = 2;
    if style.starts_with("SmartVideoWallpaper") && style.contains("::") {
        video_mode_active = true;
        let parts: Vec<&str> = style.split("::").collect();
        if parts.len() > 1 {
            let v_style = parts[1].trim().to_lowercase();
            video_fill_mode = if v_style.contains("keep proportions") {
                1
            } else if v_style.contains("scaled and cropped") {
                2
            } else if v_style.contains("stretch") {
                0
            } else {
                2
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
    log!("Fetching KDE desktops for mapping...");
    let mut kde_desktops = match wallpaper::get_kde_desktops_core(&qdbus_bin) {
        Ok(d) => d,
        Err(e) => {
            log!("Failed to get KDE desktops: {}", e);
            return Err(anyhow::anyhow!("KDE retrieval failed: {}", e));
        }
    };
    log!("Monitoring configurations (sorted by geometry):");
    let mut monitor_list: Vec<(&String, &Geometry)> = geometries.iter().collect();
    monitor_list.sort_by(|a, b| a.1.y.cmp(&b.1.y).then(a.1.x.cmp(&b.1.x)));
    for (id, geo) in &monitor_list {
        log!("  Monitor {}: x={}, y={}, w={}, h={}", id, geo.x, geo.y, geo.width, geo.height);
    }
    kde_desktops.sort_by(|a, b| a.y.cmp(&b.y).then(a.x.cmp(&b.x)));
    log!("KDE Desktops found: {}", kde_desktops.len());
    for d in &kde_desktops {
        log!("  Desktop {}: screen={}, x={}, y={}", d.index, d.screen, d.x, d.y);
    }
    let mut monitor_to_kde = HashMap::new();
    for ((monitor_id, _), d) in monitor_list.iter().zip(kde_desktops.iter()) {
        monitor_to_kde.insert(monitor_id.to_string(), d.index);
    }
    let mut script = String::new();
    let video_extensions = vec![".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv"];
    let target_plugin = get_best_video_plugin();
    for (monitor_id, path) in path_map {
        let i = monitor_to_kde.get(monitor_id).cloned().unwrap_or_else(|| monitor_id.parse().unwrap_or(0));
        log!("Monitor {} -> KDE Desktop {} (Path: {})", monitor_id, i, path);
        let file_uri = if !path.starts_with("file://") { format!("file://{}", path) } else { path.clone() };
        let raw_path = if path.starts_with("file://") { path.replace("file://", "") } else { path.clone() };
        let ext = PathBuf::from(path).extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase();
        let dot_ext = format!(".{}", ext);
        if video_extensions.contains(&dot_ext.as_str()) && video_mode_active {
            let is_smarter = target_plugin == "smartervideowallpaper";
            let video_key = if is_smarter { "VideoWallpaperBackgroundVideo" } else { "VideoUrls" };
            let override_pause = if is_smarter { "d.writeConfig('overridePause', true);" } else { "" };
            
            log!("Setting video wallpaper: mode={}, key={}, plugin={}", video_fill_mode, video_key, target_plugin);
            
            // Sync image_fill_mode based on video_fill_mode mapping
            // Plasma 6 uses the same Qt AspectRatioMode for org.kde.image (0=Stretch, 2=Crop)
            let image_fill_mode = video_fill_mode;

            script.push_str(&format!(
                "{{ \
                    var d = desktops()[{}]; \
                    if (d && d.screen >= 0) {{ \
                        if (d.wallpaperPlugin !== \"{}\") d.wallpaperPlugin = \"{}\"; \
                        d.currentConfigGroup = Array(\"Wallpaper\", d.wallpaperPlugin, \"General\"); \
                        \
                        d.writeConfig(\"FillMode\", {}); \
                        d.writeConfig(\"fillMode\", {}); \
                        {} \
                        \
                        d.writeConfig(\"{}\", \"{}\"); \
                        \
                        d.currentConfigGroup = Array(\"Wallpaper\", \"org.kde.image\", \"General\"); \
                        d.writeConfig(\"FillMode\", {}); \
                        d.writeConfig(\"Color\", \"#00000000\"); \
                        d.currentConfigGroup = Array(\"Wallpaper\", d.wallpaperPlugin, \"General\"); \
                        d.reloadConfig(); \
                    }} \
                }}", 
                i, target_plugin, target_plugin, video_fill_mode, video_fill_mode, override_pause, video_key, file_uri, image_fill_mode
            ));
        } else {
            script.push_str(&format!("{{ var d = desktops()[{}]; if (d && d.screen >= 0) {{ d.wallpaperPlugin = \"org.kde.image\"; d.currentConfigGroup = Array(\"Wallpaper\", \"org.kde.image\", \"General\"); d.writeConfig(\"Image\", \"{}\"); d.writeConfig(\"FillMode\", {}); d.reloadConfig(); }} }}", i, raw_path, fill_mode));
        }
    }
    if !script.is_empty() {
        wallpaper::evaluate_kde_script_core(&qdbus_bin, &script).map_err(|e| anyhow::anyhow!("KDE qdbus error: {}", e))?;
    }
    Ok(())
}

fn apply_wallpaper_gnome(path_map: &HashMap<String, String>, style: &str) -> Result<()> {
    if let Some(path) = path_map.values().next() {
        let abs_path = fs::canonicalize(path).context("Invalid path")?;
        let file_uri = format!("file://{}", abs_path.to_string_lossy());
        let mode = match style.to_lowercase().as_str() {
            "none" | "wallpaper" | "centered" | "scaled" | "stretched" | "zoom" | "spanned" => style.to_lowercase(),
            _ => "zoom".to_string(),
        };
        wallpaper::set_wallpaper_gnome_core(&file_uri, &mode).map_err(|e| anyhow::anyhow!("GNOME error: {}", e))?;
    }
    Ok(())
}

#[derive(Debug)]
enum DesktopEnvironment { Kde, Gnome, Unknown }
fn detect_desktop_environment() -> DesktopEnvironment {
    let env = std::env::var("XDG_CURRENT_DESKTOP").unwrap_or_default().to_lowercase();
    if env.contains("kde") || env.contains("plasma") { DesktopEnvironment::Kde }
    else if env.contains("gnome") || env.contains("ubuntu") { DesktopEnvironment::Gnome }
    else { DesktopEnvironment::Unknown }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let debug = args.contains(&"--debug".to_string());
    let log_path = match get_config_dir() {
        Ok(d) => Some(d.join("slideshow_daemon.log")),
        Err(_) => None,
    };
    if let Some(ref lp) = log_path {
        if let Ok(mut f) = fs::OpenOptions::new().create(true).append(true).open(lp) {
            let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
            let _ = writeln!(f, "\n--- SESSION START: {} ---", now);
        }
    }
    macro_rules! log {
        ($($arg:tt)*) => {{
            let msg = format!($($arg)*);
            let now = chrono::Local::now().format("[%H:%M:%S]");
            eprintln!("{} {}", now, msg);
            if let Some(ref lp) = log_path {
                if let Ok(mut f) = fs::OpenOptions::new().append(true).open(lp) {
                    let _ = writeln!(f, "{} {}", now, msg);
                }
            }
        }};
    }
    log!("Slideshow Daemon (Rust) Started.");
    if debug { log!("Debug mode enabled."); }
    if let Err(e) = run(&log_path) {
        log!("TERMINAL ERROR: {}", e);
        std::process::exit(1);
    }
}

fn run(log_path: &Option<PathBuf>) -> Result<()> {
    macro_rules! log {
        ($($arg:tt)*) => {{
            let msg = format!($($arg)*);
            let now = chrono::Local::now().format("[%H:%M:%S]");
            eprintln!("{} {}", now, msg);
            if let Some(ref lp) = log_path {
                if let Ok(mut f) = fs::OpenOptions::new().append(true).open(lp) {
                    let _ = writeln!(f, "{} {}", now, msg);
                }
            }
        }};
    }
    let config_path = get_config_path()?;
    log!("Config path: {:?}", config_path);
    let pid_path = get_pid_path()?;
    let _guard = PidGuard::new(pid_path)?;
    let de = detect_desktop_environment();
    log!("Detected desktop environment: {:?}", de);
    let mut first_run = true;
    loop {
        // Retry logic for reading JSON to avoid race conditions with Python's write
        let mut config_result = None;
        for i in 0..5 {
            if let Ok(content) = fs::read_to_string(&config_path) {
                if let Ok(cfg) = serde_json::from_str::<Config>(&content) {
                    config_result = Some(cfg);
                    break;
                }
            }
            if i < 4 {
                std::thread::sleep(std::time::Duration::from_millis(50 * (i + 1)));
            }
        }

        let mut config = match config_result {
            Some(c) => c,
            None => {
                log!("Failed to parse config JSON after retries, skipping this cycle.");
                std::thread::sleep(std::time::Duration::from_secs(5));
                continue;
            }
        };
        if !config.running {
            log!("Slideshow disabled in config. Exiting.");
            break;
        }
        let next_paths = select_next_wallpapers(&mut config, !first_run);
        if first_run {
            log!("Initial run. Current paths: {}", config.current_paths.len());
        }
        if !next_paths.is_empty() {
            log!("Applying wallpaper with style: {}", config.style);
            let res = match de {
                DesktopEnvironment::Kde => apply_wallpaper_kde(&next_paths, &config.style, &config.monitor_geometries, log_path),
                DesktopEnvironment::Gnome => apply_wallpaper_gnome(&next_paths, &config.style),
                _ => { log!("Unsupported desktop environment."); Ok(()) }
            };
            if let Err(e) = res {
                let err_msg = format!("Error applying wallpaper: {}", e);
                log!("{}", err_msg);
                config.last_error = Some(err_msg);
                let _ = save_config(&config_path, &config);
            } else {
                config.last_change_timestamp = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_secs();
                config.last_error = None;
                let _ = save_config(&config_path, &config);
                if !first_run { log!("Successfully cycled wallpapers."); }
            }
        }
        first_run = false;
        thread::sleep(Duration::from_secs(config.interval_seconds.max(1)));
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

    #[test]
    fn test_selection_logic() {
        let mut config = Config {
            running: true,
            interval_seconds: 300,
            style: "Fill".to_string(),
            monitor_queues: HashMap::from([("0".to_string(), vec!["a".to_string(), "b".to_string(), "c".to_string()])]),
            current_paths: HashMap::from([("0".to_string(), "a".to_string())]),
            monitor_geometries: HashMap::new(),
            last_change_timestamp: 0,
            playback_order: "Sequential".to_string(),
        };

        // Sequential: a -> b
        let selected = select_next_wallpapers(&mut config, true);
        assert_eq!(selected.get("0").unwrap(), "b");

        // Sequential: b -> c
        let selected = select_next_wallpapers(&mut config, true);
        assert_eq!(selected.get("0").unwrap(), "c");

        // Sequential: c -> a (loop)
        let selected = select_next_wallpapers(&mut config, true);
        assert_eq!(selected.get("0").unwrap(), "a");

        // Reverse Sequential: a -> c
        config.playback_order = "Reverse Sequential".to_string();
        let selected = select_next_wallpapers(&mut config, true);
        assert_eq!(selected.get("0").unwrap(), "c");

        // Reverse Sequential: c -> b
        let selected = select_next_wallpapers(&mut config, true);
        assert_eq!(selected.get("0").unwrap(), "b");

        // Random: Should return some valid path
        config.playback_order = "Random".to_string();
        let selected = select_next_wallpapers(&mut config, true);
        let path = selected.get("0").unwrap();
        assert!(vec!["a", "b", "c"].contains(&path.as_str()));
    }
}

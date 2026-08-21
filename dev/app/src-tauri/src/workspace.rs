//! Workspace selection + last-workspace restore (#407, D53, Grok lock #13).
//!
//! State file format is shared with the Python CLI/TUI
//! (`dev/tool/host/workspace.py::save_last_workspace`/`load_last_workspace`):
//! `~/.config/devtool/state.json` holding `{"last_workspace": "<path>"}`. Both
//! surfaces must agree on the same last-opened workspace (D48: TUI stays a
//! fallback alongside the Tauri shell).

use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

const STATE_FILENAME: &str = "state.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceInfo {
    pub root: String,
    pub name: String,
    pub has_devtool_toml: bool,
}

#[derive(Debug, Serialize, Deserialize, Default)]
struct StateFile {
    last_workspace: Option<String>,
}

fn config_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".config")
        .join("devtool")
}

fn state_path() -> PathBuf {
    config_dir().join(STATE_FILENAME)
}

fn workspace_info(root: &Path) -> WorkspaceInfo {
    WorkspaceInfo {
        root: root.to_string_lossy().to_string(),
        name: root
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default(),
        has_devtool_toml: root.join("devtool.toml").is_file(),
    }
}

/// Read the last-selected workspace, if any and if it still exists on disk.
pub fn load_last_workspace() -> Option<WorkspaceInfo> {
    let raw = fs::read_to_string(state_path()).ok()?;
    let state: StateFile = serde_json::from_str(&raw).ok()?;
    let root = PathBuf::from(state.last_workspace?);
    if root.is_dir() {
        Some(workspace_info(&root))
    } else {
        None
    }
}

/// Persist *root* as the last-selected workspace (lock #13).
pub fn save_last_workspace(root: &Path) -> anyhow::Result<WorkspaceInfo> {
    let dir = config_dir();
    fs::create_dir_all(&dir)?;
    let state = StateFile {
        last_workspace: Some(root.to_string_lossy().to_string()),
    };
    fs::write(state_path(), serde_json::to_string_pretty(&state)?)?;
    Ok(workspace_info(root))
}

#[tauri::command]
pub fn get_last_workspace() -> Option<WorkspaceInfo> {
    load_last_workspace()
}

#[tauri::command]
pub fn select_workspace(path: String) -> Result<WorkspaceInfo, String> {
    let root = PathBuf::from(&path);
    if !root.is_dir() {
        return Err(format!("not a directory: {path}"));
    }
    save_last_workspace(&root).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn workspace_info_detects_devtool_toml() {
        let dir = std::env::temp_dir().join(format!("devtool-app-test-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        fs::write(dir.join("devtool.toml"), "[workspace]\n").unwrap();
        let info = workspace_info(&dir);
        assert!(info.has_devtool_toml);
        fs::remove_dir_all(&dir).ok();
    }
}

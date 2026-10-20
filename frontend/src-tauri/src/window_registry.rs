//! WindowManager role map: labels, hide-all, pop-out (W0-09 / #873).
//!
//! JS does not construct `WebviewWindow`s. Extra native windows stay off
//! this map until a later issue (#893 slideshow) creates them.

use serde::Deserialize;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::{AppHandle, Manager, Window, WindowEvent};

const ROLES_JSON: &str = include_str!("../windows/roles.json");

#[derive(Debug, Clone, Deserialize)]
pub struct WindowRole {
    pub id: String,
    pub role: String,
    pub kind: String,
    #[serde(default)]
    pub panel_of: Option<String>,
    #[serde(default)]
    pub hide_on_close: bool,
}

#[derive(Debug, Deserialize)]
struct RoleFile {
    windows: Vec<WindowRole>,
}

#[derive(Default)]
pub struct TrayHidden(pub Mutex<Vec<String>>);

fn all_roles() -> Vec<WindowRole> {
    serde_json::from_str::<RoleFile>(ROLES_JSON)
        .expect("windows/roles.json")
        .windows
}

pub fn hide_on_close_labels() -> Vec<String> {
    all_roles()
        .into_iter()
        .filter(|role| role.kind == "webview" && role.hide_on_close)
        .map(|role| role.id)
        .collect()
}

fn find_role(label: &str) -> Option<WindowRole> {
    all_roles().into_iter().find(|role| role.id == label)
}

pub fn data_dir() -> PathBuf {
    if let Ok(path) = std::env::var("IMAGE_TOOLKIT_DIR") {
        return PathBuf::from(path);
    }
    let home = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE"));
    PathBuf::from(home.unwrap_or_else(|| ".".into())).join(".image-toolkit")
}

pub fn hide_all(app: &AppHandle) -> Result<(), String> {
    let mut hidden = Vec::new();
    for label in hide_on_close_labels() {
        let Some(window) = app.get_webview_window(&label) else {
            continue;
        };
        if window.is_visible().unwrap_or(false) {
            hidden.push(label);
        }
        let _ = window.hide();
        let _ = window.set_skip_taskbar(true);
    }
    if let Some(state) = app.try_state::<TrayHidden>() {
        *state.0.lock().map_err(|err| err.to_string())? = hidden;
    }
    Ok(())
}

pub fn restore(app: &AppHandle) -> Result<(), String> {
    let mut labels = if let Some(state) = app.try_state::<TrayHidden>() {
        std::mem::take(&mut *state.0.lock().map_err(|err| err.to_string())?)
    } else {
        Vec::new()
    };
    if !labels.iter().any(|label| label == "main") {
        labels.push("main".to_string());
    }
    for label in &labels {
        let Some(window) = app.get_webview_window(label) else {
            continue;
        };
        let _ = window.set_skip_taskbar(false);
        let _ = window.show();
        let _ = window.unminimize();
    }
    if let Some(main) = app.get_webview_window("main") {
        let _ = main.set_focus();
    }
    Ok(())
}

pub fn popout(app: &AppHandle, role: &str) -> Result<(), String> {
    let spec = find_role(role).ok_or_else(|| format!("unknown window role {role}"))?;
    if spec.role != "popout" || spec.kind != "webview" {
        return Err(format!("{role} is not a labeled pop-out"));
    }
    let window = app
        .get_webview_window(role)
        .ok_or_else(|| format!("window {role} is not declared"))?;
    window
        .set_skip_taskbar(false)
        .map_err(|err| err.to_string())?;
    window.show().map_err(|err| err.to_string())?;
    let _ = window.unminimize();
    window.set_focus().map_err(|err| err.to_string())
}

pub fn focus(app: &AppHandle, role: &str) -> Result<(), String> {
    let window = app
        .get_webview_window(role)
        .ok_or_else(|| format!("window {role} is not declared"))?;
    window
        .set_skip_taskbar(false)
        .map_err(|err| err.to_string())?;
    window.show().map_err(|err| err.to_string())?;
    let _ = window.unminimize();
    window.set_focus().map_err(|err| err.to_string())
}

pub fn on_window_event(window: &Window, event: &WindowEvent) {
    let WindowEvent::CloseRequested { api, .. } = event else {
        return;
    };
    let Some(spec) = find_role(window.label()) else {
        return;
    };
    if spec.kind != "webview" || !spec.hide_on_close {
        return;
    }
    api.prevent_close();
    if spec.id == "main" {
        let _ = hide_all(window.app_handle());
    } else {
        let _ = window.hide();
        let _ = window.set_skip_taskbar(true);
    }
}

#[tauri::command]
pub fn window_popout(app: AppHandle, role: String) -> Result<(), String> {
    popout(&app, &role)
}

#[tauri::command]
pub fn window_hide_all(app: AppHandle) -> Result<(), String> {
    hide_all(&app)
}

#[tauri::command]
pub fn window_restore(app: AppHandle) -> Result<(), String> {
    restore(&app)
}

#[tauri::command]
pub fn window_focus(app: AppHandle, role: String) -> Result<(), String> {
    focus(&app, &role)
}

#[cfg(test)]
mod tests {
    #[test]
    fn hide_on_close_covers_main_and_popout() {
        let labels = super::hide_on_close_labels();
        assert!(labels.contains(&"main".to_string()));
        assert!(labels.contains(&"cloud.jobs".to_string()));
        assert!(!labels.iter().any(|id| id == "tray" || id == "slideshow"));
    }

    #[test]
    fn cloud_jobs_is_a_main_popout() {
        let spec = super::find_role("cloud.jobs").expect("cloud.jobs");
        assert_eq!(spec.role, "popout");
        assert_eq!(spec.panel_of.as_deref(), Some("main"));
        assert!(spec.hide_on_close);
    }
}

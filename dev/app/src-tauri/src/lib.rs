//! Development Tool v2 — Tauri host skeleton (#407).
//!
//! Scope of this slice, per D41-D64 and the Team Review Notes: window +
//! workspace lifecycle only. It does NOT discover/render plugin artifacts and
//! does not implement any 2D/3D view (Gemini's #415-#419 models land
//! separately and get wired to a real view once the sidecar RPC is up). What
//! it does provide: a single window, a workspace picker that reads/writes the
//! same `~/.config/devtool/state.json` the Python CLI/TUI use (D48), and the
//! #408 host wiring: the bundled Python sidecar is spawned on window open,
//! handshaken over `--stdio` JSON-RPC, monitored with the restart policy
//! (locks #3/#4/#12), and killed on window close.

mod sidecar;
mod workspace;

use std::path::Path;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::{Manager, State, WindowEvent};

type SidecarState = Arc<Mutex<sidecar::SidecarHandle>>;

/// #409 wiring: `devtool.record`s for the current workspace, read through
/// the running sidecar's `list_records` method (lock 9).
#[tauri::command]
fn list_records(state: State<'_, SidecarState>) -> Result<serde_json::Value, String> {
    state.lock().unwrap().list_records().map_err(|e| e.to_string())
}

/// The discovered plugin registry, read through the sidecar's
/// `list_artifacts` method (#410 shape).
#[tauri::command]
fn list_artifacts(state: State<'_, SidecarState>) -> Result<serde_json::Value, String> {
    state.lock().unwrap().list_artifacts().map_err(|e| e.to_string())
}

#[tauri::command]
fn get_meta_graph(state: State<'_, SidecarState>) -> Result<serde_json::Value, String> {
    state.lock().unwrap().get_meta_graph().map_err(|e| e.to_string())
}

#[tauri::command]
fn get_flame_graph(state: State<'_, SidecarState>) -> Result<serde_json::Value, String> {
    state.lock().unwrap().get_flame_graph().map_err(|e| e.to_string())
}

#[tauri::command]
fn get_metrics_timeline(state: State<'_, SidecarState>) -> Result<serde_json::Value, String> {
    state.lock().unwrap().get_metrics_timeline().map_err(|e| e.to_string())
}

#[tauri::command]
fn get_pipeline_scrubber(
    t_ms: Option<f64>,
    state: State<'_, SidecarState>,
) -> Result<serde_json::Value, String> {
    state.lock().unwrap().get_pipeline_scrubber(t_ms).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_world_state(state: State<'_, SidecarState>) -> Result<serde_json::Value, String> {
    state.lock().unwrap().get_world_state().map_err(|e| e.to_string())
}

#[tauri::command]
fn save_world_state(
    world_state: serde_json::Value,
    state: State<'_, SidecarState>,
) -> Result<serde_json::Value, String> {
    state.lock().unwrap().save_world_state(world_state).map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let repo_root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let sidecar = Arc::new(Mutex::new(sidecar::SidecarHandle::new(
        sidecar::SidecarCommand::for_repo_root(&repo_root),
    )));

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(sidecar)
        .invoke_handler(tauri::generate_handler![
            workspace::get_last_workspace,
            workspace::select_workspace,
            list_records,
            list_artifacts,
            get_meta_graph,
            get_flame_graph,
            get_metrics_timeline,
            get_pipeline_scrubber,
            get_world_state,
            save_world_state,
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            // #408 host wiring, lock #3: the window is open, so spawn the
            // bundled Python sidecar and perform the `--stdio` initialize
            // handshake.
            let state = app.state::<Arc<Mutex<sidecar::SidecarHandle>>>();
            if let Err(err) = state.lock().unwrap().start() {
                log::error!("sidecar start failed: {err:#}");
            } else {
                // Crash monitor (locks #4/#12): poll the child; restart
                // exactly once after a successful initialize, then hard
                // fail. Exits when the handle is stopped on close.
                let watcher = state.inner().clone();
                std::thread::spawn(move || loop {
                    let keep = { watcher.lock().unwrap().poll_crash() };
                    if !keep {
                        break;
                    }
                    std::thread::sleep(Duration::from_millis(200));
                });
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. } | WindowEvent::Destroyed) {
                // Lock #3: lifetime is the window — kill the sidecar on close.
                window
                    .state::<Arc<Mutex<sidecar::SidecarHandle>>>()
                    .lock()
                    .unwrap()
                    .stop();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running devtool-app");
}
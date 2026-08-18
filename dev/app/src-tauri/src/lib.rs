//! Development Tool v2 — Tauri host skeleton (#407).
//!
//! Scope of this slice, per D41-D64 and the Team Review Notes: window +
//! workspace lifecycle only. It does NOT spawn the sidecar (#408 host
//! wiring, owned by opencode), does not discover/render plugin artifacts,
//! and does not implement any 2D/3D view (Gemini's #415-#419 models land
//! separately and get wired to a real view once the sidecar RPC is up).
//! What it does provide: a single window, a workspace picker that reads/
//! writes the same `~/.config/devtool/state.json` the Python CLI/TUI use
//! (D48), and the extension points (`sidecar` module, `close-requested`
//! handler below) the rest of the host stack lands in.

mod sidecar;
mod workspace;

use tauri::WindowEvent;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(sidecar::SidecarHandle::default())
        .invoke_handler(tauri::generate_handler![
            workspace::get_last_workspace,
            workspace::select_workspace,
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            // Lifetime is the window (lock #3): this is where #408 kills the
            // sidecar child once spawn wiring lands. No process to kill yet.
            if let WindowEvent::CloseRequested { .. } = event {
                log::info!("window '{}' close requested; sidecar teardown lands with #408", window.label());
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running devtool-app");
}

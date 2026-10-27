use serde_json::{json, Value};
use tauri::Manager;

use crate::python_json::run_module;

/// Codec re-encode, resample, or sheet cut. `action` is codec, resample, or image_cut.
///
/// The Python process blocks until ffmpeg finishes, so it runs off the UI thread.
#[tauri::command]
pub async fn media_subtab(
    app: tauri::AppHandle,
    action: String,
    params: Value,
) -> Result<Value, String> {
    let resource_dir = app.path().resource_dir().ok();
    tauri::async_runtime::spawn_blocking(move || {
        let mut payload = params;
        if !payload.is_object() {
            payload = json!({});
        }
        payload["action"] = json!(action);
        run_module("middleware.src.services.media.subtabs", &payload, resource_dir)
    })
    .await
    .map_err(|error| format!("media task failed: {error}"))?
}

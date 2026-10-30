use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Read, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use tauri::{Emitter, Manager};

use crate::bridge_commands::{resolve_runtime, RuntimeProbe};

/// Codec re-encode, resample, or sheet cut. `action` is codec, resample, or image_cut.
///
/// The Python process blocks until the job finishes, so it runs off the UI thread.
/// Stderr lines `IT_PROGRESS\tstage\tdone\ttotal` are emitted as `media-progress` while it runs.
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
        run_media(&app, &payload, resource_dir)
    })
    .await
    .map_err(|error| format!("media task failed: {error}"))?
}

fn redact(detail: &str, payload: &Value) -> String {
    let Some(password) = payload.get("password").and_then(|item| item.as_str()) else {
        return detail.to_string();
    };
    if password.is_empty() {
        return detail.to_string();
    }
    detail.replace(password, "********")
}

fn media_progress(line: &str) -> Option<Value> {
    let mut parts = line.trim_end_matches('\r').split('\t');
    if parts.next() != Some("IT_PROGRESS") {
        return None;
    }
    let stage = parts.next()?.to_string();
    let done: i64 = parts.next()?.trim().parse().ok()?;
    let total: i64 = parts.next()?.trim().parse().ok()?;
    Some(json!({ "stage": stage, "done": done, "total": total }))
}

/// Same interpreter lookup as `run_module`, but stderr is read while Python is still running.
fn run_media(
    app: &tauri::AppHandle,
    payload: &Value,
    resource_dir: Option<PathBuf>,
) -> Result<Value, String> {
    let runtime = resolve_runtime(&RuntimeProbe {
        env_runtime: std::env::var_os("IMAGE_TOOLKIT_RUNTIME").map(PathBuf::from),
        resource_dir,
        executable: std::env::current_exe().unwrap_or_else(|_| PathBuf::from("image-toolkit")),
    })?;
    let body = serde_json::to_vec(payload).map_err(|err| err.to_string())?;
    let mut child = Command::new(&runtime.python)
        .arg("-m")
        .arg("middleware.src.services.media.subtabs")
        .current_dir(&runtime.root)
        .env("PYTHONPATH", &runtime.root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|err| format!("Failed to start Python: {err}"))?;
    {
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(|| "Python stdin was not piped".to_string())?;
        stdin
            .write_all(&body)
            .map_err(|err| format!("Failed to send the request: {err}"))?;
    }
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "Python stdout was not piped".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "Python stderr was not piped".to_string())?;
    let emitter = app.clone();
    let stderr_task = std::thread::spawn(move || {
        let mut extra = String::new();
        for line in BufReader::new(stderr).lines() {
            let Ok(line) = line else { break };
            if let Some(progress) = media_progress(&line) {
                let _ = emitter.emit("media-progress", &progress);
            } else if !line.is_empty() {
                extra.push_str(&line);
                extra.push('\n');
            }
        }
        extra
    });
    let stdout_task = std::thread::spawn(move || {
        let mut buf = Vec::new();
        let _ = BufReader::new(stdout).read_to_end(&mut buf);
        buf
    });
    let status = child
        .wait()
        .map_err(|err| format!("Python did not finish: {err}"))?;
    let stdout_bytes = stdout_task
        .join()
        .map_err(|_| "stdout reader failed".to_string())?;
    let stderr_text = stderr_task
        .join()
        .map_err(|_| "stderr reader failed".to_string())?;
    if !status.success() {
        let detail = redact(stderr_text.trim(), payload);
        if detail.is_empty() {
            return Err(format!("Python exited with {status}"));
        }
        return Err(detail);
    }
    serde_json::from_slice(&stdout_bytes).map_err(|err| {
        format!(
            "Python returned invalid JSON ({err}): {}",
            String::from_utf8_lossy(&stdout_bytes)
        )
    })
}

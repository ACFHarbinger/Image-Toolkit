//! Run a checkout Python module with one JSON object on stdin and one on stdout.
//! Secrets stay in the payload, not in argv.
//!
//! The interpreter is the packaged sidecar runtime (`python/bin/python3` or the
//! checkout `.venv`), the same lookup `bridge_commands` uses.

use crate::bridge_commands::{resolve_runtime, RuntimeProbe};
use serde_json::Value;
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};

fn redact(detail: &str, payload: &Value) -> String {
    let Some(password) = payload.get("password").and_then(|item| item.as_str()) else {
        return detail.to_string();
    };
    if password.is_empty() {
        return detail.to_string();
    }
    detail.replace(password, "********")
}

pub fn run_module(
    module: &str,
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
        .arg(module)
        .current_dir(&runtime.root)
        .env("PYTHONPATH", &runtime.root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|err| format!("Failed to start Python: {err}"))?;
    if let Some(stdin) = child.stdin.as_mut() {
        stdin
            .write_all(&body)
            .map_err(|err| format!("Failed to send the request: {err}"))?;
    }
    let output = child
        .wait_with_output()
        .map_err(|err| format!("Python did not finish: {err}"))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let detail = redact(stderr.trim(), payload);
        if detail.is_empty() {
            return Err(format!("Python exited with {}", output.status));
        }
        return Err(detail);
    }
    serde_json::from_slice(&output.stdout).map_err(|err| {
        format!(
            "Python returned invalid JSON ({err}): {}",
            String::from_utf8_lossy(&output.stdout)
        )
    })
}

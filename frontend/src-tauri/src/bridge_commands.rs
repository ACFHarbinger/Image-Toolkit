//! Long-lived Python sidecar for `bridge_request`.
//!
//! HostClient speaks one JSON-RPC process. A fresh process per invoke would
//! forget the handshake, so the shell keeps a single child for the app lifetime.

use serde_json::Value;
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{self, Sender};
use std::sync::Mutex;
use std::time::Duration;

struct Session {
    stdin: ChildStdin,
    pending: std::sync::Arc<Mutex<HashMap<String, Sender<Value>>>>,
    _child: Child,
}

static SESSION: Mutex<Option<Session>> = Mutex::new(None);

fn id_key(id: &Value) -> String {
    id.to_string()
}

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn python_executable() -> String {
    std::env::var("IMAGE_TOOLKIT_PYTHON").unwrap_or_else(|_| "python3".to_string())
}

fn spawn_session() -> Result<Session, String> {
    let root = repo_root();
    let mut child = Command::new(python_executable())
        .arg("-m")
        .arg("middleware.src.sidecar")
        .current_dir(&root)
        .env("PYTHONPATH", &root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("failed to start the convert sidecar: {error}"))?;
    let stdin = child
        .stdin
        .take()
        .ok_or_else(|| "sidecar stdin was not piped".to_string())?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "sidecar stdout was not piped".to_string())?;
    let stderr = child.stderr.take();
    let pending = std::sync::Arc::new(Mutex::new(HashMap::<String, Sender<Value>>::new()));
    let reader_pending = pending.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            let Ok(line) = line else { break };
            let Ok(frame) = serde_json::from_str::<Value>(&line) else {
                continue;
            };
            if frame.get("jsonrpc").is_none() {
                continue;
            }
            let Some(id) = frame.get("id") else { continue };
            if let Some(sender) = reader_pending
                .lock()
                .expect("pending map")
                .remove(&id_key(id))
            {
                let _ = sender.send(frame);
            }
        }
    });
    if let Some(stderr) = stderr {
        std::thread::spawn(move || {
            let _ = std::io::copy(&mut BufReader::new(stderr), &mut std::io::sink());
        });
    }
    Ok(Session {
        stdin,
        pending,
        _child: child,
    })
}

fn exchange(request: Value) -> Result<Value, String> {
    let id = request
        .get("id")
        .cloned()
        .ok_or_else(|| "bridge request is missing id".to_string())?;
    let line = serde_json::to_string(&request).map_err(|error| error.to_string())?;
    let (sender, receiver) = mpsc::channel();
    {
        let mut slot = SESSION
            .lock()
            .map_err(|_| "sidecar session lock poisoned".to_string())?;
        if slot.is_none() {
            *slot = Some(spawn_session()?);
        }
        let session = slot.as_mut().expect("session was just stored");
        session
            .pending
            .lock()
            .expect("pending map")
            .insert(id_key(&id), sender);
        if let Err(error) = writeln!(session.stdin, "{line}").and_then(|()| session.stdin.flush()) {
            session
                .pending
                .lock()
                .expect("pending map")
                .remove(&id_key(&id));
            return Err(format!("failed to write to the sidecar: {error}"));
        }
    }
    receiver
        .recv_timeout(Duration::from_secs(120))
        .map_err(|_| "sidecar did not answer within 120s".to_string())
}

#[tauri::command]
pub async fn bridge_request(request: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || exchange(request))
        .await
        .map_err(|error| format!("bridge request task failed: {error}"))?
}

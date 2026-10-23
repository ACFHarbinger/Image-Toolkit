//! Long-lived Python sidecar for `bridge_request`.
//!
//! HostClient speaks one JSON-RPC process. The interpreter and middleware
//! come from the installed runtime (packaged resources, `IMAGE_TOOLKIT_RUNTIME`,
//! or a checkout discovered from the running executable). The compile-time
//! source directory is not embedded. A dead child is dropped, its waiters
//! fail immediately, and the next request starts a new process and handshake.

use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::{self, Sender};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{Emitter, Manager};

struct Session {
    stdin: ChildStdin,
    pending: std::sync::Arc<Mutex<HashMap<String, Sender<Result<Value, String>>>>>,
    child: Child,
    alive: std::sync::Arc<AtomicBool>,
    handshaken: AtomicBool,
}

struct Launch {
    program: String,
    args: Vec<String>,
    cwd: Option<PathBuf>,
    pythonpath: Option<PathBuf>,
}

#[derive(Debug)]
struct Runtime {
    root: PathBuf,
    python: PathBuf,
}

struct RuntimeProbe {
    env_runtime: Option<PathBuf>,
    resource_dir: Option<PathBuf>,
    executable: PathBuf,
}

static SESSION: Mutex<Option<Session>> = Mutex::new(None);
static LAUNCH_OVERRIDE: Mutex<Option<Launch>> = Mutex::new(None);
static HANDSHAKE_IDS: AtomicU64 = AtomicU64::new(1);

fn id_key(id: &Value) -> String {
    id.to_string()
}

fn is_executable(path: &Path) -> bool {
    if !path.is_file() {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        return path
            .metadata()
            .map(|meta| meta.permissions().mode() & 0o111 != 0)
            .unwrap_or(false);
    }
    #[cfg(not(unix))]
    {
        true
    }
}

fn python_in(root: &Path) -> Option<PathBuf> {
    for relative in [
        "python/bin/python3",
        "python/python.exe",
        ".venv/bin/python",
        ".venv/bin/python3",
        "bin/python3",
        "bin/python",
    ] {
        let path = root.join(relative);
        if is_executable(&path) {
            return Some(path);
        }
    }
    None
}

fn runtime_at(root: &Path) -> Option<Runtime> {
    let python = python_in(root)?;
    if root.join("middleware/src/sidecar/__main__.py").is_file() {
        Some(Runtime {
            root: root.to_path_buf(),
            python,
        })
    } else {
        None
    }
}

fn walk_executable(executable: &Path) -> Option<Runtime> {
    let mut dir = executable.parent()?.to_path_buf();
    for _ in 0..8 {
        if let Some(runtime) = runtime_at(&dir) {
            return Some(runtime);
        }
        if !dir.pop() {
            break;
        }
    }
    None
}

fn resolve_runtime(probe: &RuntimeProbe) -> Result<Runtime, String> {
    if let Some(root) = &probe.env_runtime {
        return runtime_at(root).ok_or_else(|| {
            format!(
                "IMAGE_TOOLKIT_RUNTIME is not a sidecar runtime: {}",
                root.display()
            )
        });
    }
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Some(resource_dir) = &probe.resource_dir {
        candidates.push(resource_dir.join("sidecar-runtime"));
        candidates.push(resource_dir.clone());
    }
    if let Some(exe_dir) = probe.executable.parent() {
        candidates.push(exe_dir.join("sidecar-runtime"));
        candidates.push(exe_dir.join("../lib/image-toolkit/sidecar-runtime"));
        candidates.push(exe_dir.join("../share/image-toolkit/sidecar-runtime"));
    }
    for candidate in candidates {
        if let Some(runtime) = runtime_at(&candidate) {
            return Ok(runtime);
        }
    }
    walk_executable(&probe.executable).ok_or_else(|| {
        "Image Toolkit sidecar runtime is not installed. Expected sidecar-runtime beside the app or IMAGE_TOOLKIT_RUNTIME.".to_string()
    })
}

fn production_launch(resource_dir: Option<PathBuf>) -> Result<Launch, String> {
    let runtime = resolve_runtime(&RuntimeProbe {
        env_runtime: std::env::var_os("IMAGE_TOOLKIT_RUNTIME").map(PathBuf::from),
        resource_dir,
        executable: std::env::current_exe().unwrap_or_else(|_| PathBuf::from("image-toolkit")),
    })?;
    Ok(Launch {
        program: runtime.python.to_string_lossy().into_owned(),
        args: vec!["-m".to_string(), "middleware.src.sidecar".to_string()],
        cwd: Some(runtime.root.clone()),
        pythonpath: Some(runtime.root),
    })
}

fn launch_for(resource_dir: Option<PathBuf>) -> Result<Launch, String> {
    if let Some(launch) = LAUNCH_OVERRIDE.lock().ok().and_then(|slot| slot.clone()) {
        return Ok(launch);
    }
    production_launch(resource_dir)
}

impl Clone for Launch {
    fn clone(&self) -> Self {
        Self {
            program: self.program.clone(),
            args: self.args.clone(),
            cwd: self.cwd.clone(),
            pythonpath: self.pythonpath.clone(),
        }
    }
}

fn fail_pending(pending: &Mutex<HashMap<String, Sender<Result<Value, String>>>>, message: &str) {
    if let Ok(mut waiters) = pending.lock() {
        for (_, sender) in waiters.drain() {
            let _ = sender.send(Err(message.to_string()));
        }
    }
}

fn is_event(frame: &Value) -> bool {
    frame.get("channel").and_then(Value::as_str).is_some()
        && frame.get("seq").and_then(Value::as_u64).is_some()
        && frame.get("payload").is_some()
}

fn spawn_session(
    resource_dir: Option<PathBuf>,
    app: Option<tauri::AppHandle>,
) -> Result<Session, String> {
    let launch = launch_for(resource_dir)?;
    let mut command = Command::new(&launch.program);
    command.args(&launch.args);
    if let Some(cwd) = &launch.cwd {
        command.current_dir(cwd);
    }
    if let Some(pythonpath) = &launch.pythonpath {
        command.env("PYTHONPATH", pythonpath);
        if pythonpath.join(".venv").is_dir() {
            command.env("VIRTUAL_ENV", pythonpath.join(".venv"));
        } else {
            command.env_remove("VIRTUAL_ENV");
        }
    }
    command.env_remove("PYTHONHOME");
    command.env("PYTHONNOUSERSITE", "1");
    let mut child = command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("failed to start the sidecar runtime: {error}"))?;
    let stdin = child
        .stdin
        .take()
        .ok_or_else(|| "sidecar stdin was not piped".to_string())?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "sidecar stdout was not piped".to_string())?;
    let stderr = child.stderr.take();
    let pending = std::sync::Arc::new(Mutex::new(
        HashMap::<String, Sender<Result<Value, String>>>::new(),
    ));
    let alive = std::sync::Arc::new(AtomicBool::new(true));
    let reader_pending = pending.clone();
    let reader_alive = alive.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            let Ok(line) = line else { break };
            let Ok(frame) = serde_json::from_str::<Value>(&line) else {
                continue;
            };
            if frame.get("jsonrpc").is_none() {
                if is_event(&frame) {
                    if let Some(app) = &app {
                        let _ = app.emit("bridge-event", &frame);
                    }
                }
                continue;
            }
            let Some(id) = frame.get("id") else { continue };
            if let Some(sender) = reader_pending
                .lock()
                .expect("pending map")
                .remove(&id_key(id))
            {
                let _ = sender.send(Ok(frame));
            }
        }
        reader_alive.store(false, Ordering::SeqCst);
        fail_pending(&reader_pending, "sidecar exited");
    });
    if let Some(stderr) = stderr {
        std::thread::spawn(move || {
            let _ = std::io::copy(&mut BufReader::new(stderr), &mut std::io::sink());
        });
    }
    Ok(Session {
        stdin,
        pending,
        child,
        alive,
        handshaken: AtomicBool::new(false),
    })
}

fn session_live(session: &mut Session) -> bool {
    if !session.alive.load(Ordering::SeqCst) {
        return false;
    }
    match session.child.try_wait() {
        Ok(None) => true,
        _ => {
            session.alive.store(false, Ordering::SeqCst);
            false
        }
    }
}

fn retire(mut session: Session) {
    session.alive.store(false, Ordering::SeqCst);
    let _ = session.child.kill();
    let _ = session.child.wait();
    fail_pending(&session.pending, "sidecar session closed");
}

fn invalidate_session() {
    if let Ok(mut slot) = SESSION.lock() {
        if let Some(session) = slot.take() {
            retire(session);
        }
    }
}

fn handshake_request(id: &str) -> Value {
    json!({
        "jsonrpc": "2.0",
        "id": id,
        "method": "system.handshake",
        "params": {
            "protocol": "image-toolkit-bridge",
            "client": {"name": "tauri-shell", "version": "1.0.0"}
        }
    })
}

fn roundtrip(request: Value) -> Result<Value, String> {
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
        let session = slot
            .as_mut()
            .ok_or_else(|| "sidecar session is not running".to_string())?;
        if !session_live(session) {
            return Err("sidecar session is not running".to_string());
        }
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
            if let Some(dead) = slot.take() {
                drop(slot);
                retire(dead);
            }
            return Err(format!("failed to write to the sidecar: {error}"));
        }
    }
    match receiver.recv_timeout(Duration::from_secs(120)) {
        Ok(Ok(frame)) => Ok(frame),
        Ok(Err(error)) => {
            invalidate_session();
            Err(error)
        }
        Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
            if let Ok(slot) = SESSION.lock() {
                if let Some(session) = slot.as_ref() {
                    session
                        .pending
                        .lock()
                        .expect("pending map")
                        .remove(&id_key(&id));
                }
            }
            Err("sidecar did not answer within 120s".to_string())
        }
        Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
            invalidate_session();
            Err("sidecar exited".to_string())
        }
    }
}

fn mark_handshaken() {
    if let Ok(slot) = SESSION.lock() {
        if let Some(session) = slot.as_ref() {
            session.handshaken.store(true, Ordering::SeqCst);
        }
    }
}

fn ensure_ready(
    method: &str,
    resource_dir: Option<PathBuf>,
    app: Option<tauri::AppHandle>,
) -> Result<(), String> {
    let handshake_id = {
        let mut slot = SESSION
            .lock()
            .map_err(|_| "sidecar session lock poisoned".to_string())?;
        let live = match slot.as_mut() {
            Some(session) => session_live(session),
            None => false,
        };
        if !live {
            if let Some(old) = slot.take() {
                retire(old);
            }
            *slot = Some(spawn_session(resource_dir, app)?);
        }
        let session = slot.as_ref().expect("session was just stored");
        if session.handshaken.load(Ordering::SeqCst) || method == "system.handshake" {
            None
        } else {
            Some(format!(
                "sidecar-hs-{}",
                HANDSHAKE_IDS.fetch_add(1, Ordering::Relaxed)
            ))
        }
    };
    if let Some(id) = handshake_id {
        let response = roundtrip(handshake_request(&id))?;
        if response.get("result").is_none() {
            invalidate_session();
            return Err("sidecar handshake failed".to_string());
        }
        mark_handshaken();
    }
    Ok(())
}

fn transport_lost(error: &str) -> bool {
    error.contains("exited") || error.contains("not running") || error.contains("failed to write")
}

fn exchange_with_events(
    request: Value,
    resource_dir: Option<PathBuf>,
    app: Option<tauri::AppHandle>,
) -> Result<Value, String> {
    let method = request
        .get("method")
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .to_string();
    let mut last_error = "sidecar exited".to_string();
    for attempt in 0..2 {
        if let Err(error) = ensure_ready(&method, resource_dir.clone(), app.clone()) {
            last_error = error;
            if attempt == 0 && transport_lost(&last_error) {
                invalidate_session();
                continue;
            }
            return Err(last_error);
        }
        match roundtrip(request.clone()) {
            Ok(response) => {
                if method == "system.handshake" && response.get("result").is_some() {
                    mark_handshaken();
                }
                return Ok(response);
            }
            Err(error) if attempt == 0 && transport_lost(&error) => {
                last_error = error;
                invalidate_session();
            }
            Err(error) => return Err(error),
        }
    }
    Err(last_error)
}

#[tauri::command]
pub async fn bridge_request(app: tauri::AppHandle, request: Value) -> Result<Value, String> {
    let resource_dir = app.path().resource_dir().ok();
    tauri::async_runtime::spawn_blocking(move || {
        exchange_with_events(request, resource_dir, Some(app))
    })
    .await
    .map_err(|error| format!("bridge request task failed: {error}"))?
}

#[cfg(test)]
fn exchange(request: Value, resource_dir: Option<PathBuf>) -> Result<Value, String> {
    exchange_with_events(request, resource_dir, None)
}

#[cfg(test)]
mod tests;

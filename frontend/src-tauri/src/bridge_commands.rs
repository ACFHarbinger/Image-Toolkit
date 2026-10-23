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
use tauri::Manager;

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

fn spawn_session(resource_dir: Option<PathBuf>) -> Result<Session, String> {
    let launch = launch_for(resource_dir)?;
    let mut command = Command::new(&launch.program);
    command.args(&launch.args);
    if let Some(cwd) = &launch.cwd {
        command.current_dir(cwd);
    }
    if let Some(pythonpath) = &launch.pythonpath {
        command.env("PYTHONPATH", pythonpath);
        command.env("VIRTUAL_ENV", pythonpath.join(".venv"));
    }
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

fn ensure_ready(method: &str, resource_dir: Option<PathBuf>) -> Result<(), String> {
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
            *slot = Some(spawn_session(resource_dir)?);
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

fn exchange(request: Value, resource_dir: Option<PathBuf>) -> Result<Value, String> {
    let method = request
        .get("method")
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .to_string();
    let mut last_error = "sidecar exited".to_string();
    for attempt in 0..2 {
        if let Err(error) = ensure_ready(&method, resource_dir.clone()) {
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
    tauri::async_runtime::spawn_blocking(move || exchange(request, resource_dir))
        .await
        .map_err(|error| format!("bridge request task failed: {error}"))?
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::Instant;

    fn reset() {
        invalidate_session();
        if let Ok(mut slot) = LAUNCH_OVERRIDE.lock() {
            *slot = None;
        }
    }

    fn touch_runtime(root: &Path) {
        let python = root.join(".venv/bin/python");
        fs::create_dir_all(python.parent().unwrap()).unwrap();
        fs::write(&python, b"#!/bin/sh\nexit 0\n").unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut permissions = fs::metadata(&python).unwrap().permissions();
            permissions.set_mode(0o755);
            fs::set_permissions(&python, permissions).unwrap();
        }
        let marker = root.join("middleware/src/sidecar/__main__.py");
        fs::create_dir_all(marker.parent().unwrap()).unwrap();
        fs::write(marker, b"").unwrap();
    }

    #[test]
    fn packaged_resource_wins_over_a_nearby_checkout() {
        let temp = std::env::temp_dir().join(format!("itk-runtime-{}-pkg", std::process::id()));
        let _ = fs::remove_dir_all(&temp);
        let resource = temp.join("resources");
        let checkout = temp.join("checkout");
        touch_runtime(&resource.join("sidecar-runtime"));
        touch_runtime(&checkout);
        let found = resolve_runtime(&RuntimeProbe {
            env_runtime: None,
            resource_dir: Some(resource.clone()),
            executable: checkout.join("target/debug/app"),
        })
        .unwrap();
        assert_eq!(found.root, resource.join("sidecar-runtime"));
        let _ = fs::remove_dir_all(&temp);
    }

    #[test]
    fn executable_walk_finds_a_checkout_without_a_compiled_path() {
        let temp = std::env::temp_dir().join(format!("itk-runtime-{}-walk", std::process::id()));
        let _ = fs::remove_dir_all(&temp);
        touch_runtime(&temp);
        let found = resolve_runtime(&RuntimeProbe {
            env_runtime: None,
            resource_dir: Some(temp.join("missing")),
            executable: temp.join("target/debug/app"),
        })
        .unwrap();
        assert_eq!(found.root, temp);
        let _ = fs::remove_dir_all(&temp);
    }

    #[test]
    fn missing_runtime_does_not_invent_a_source_directory() {
        let temp = std::env::temp_dir().join(format!("itk-runtime-{}-missing", std::process::id()));
        let _ = fs::remove_dir_all(&temp);
        fs::create_dir_all(temp.join("bin")).unwrap();
        let error = resolve_runtime(&RuntimeProbe {
            env_runtime: None,
            resource_dir: Some(temp.join("resources")),
            executable: temp.join("bin/app"),
        })
        .unwrap_err();
        assert!(!error.contains("CARGO_MANIFEST_DIR"));
        assert!(error.contains("not installed"));
        let _ = fs::remove_dir_all(&temp);
    }

    fn install_python(script: &str) {
        if let Ok(mut slot) = LAUNCH_OVERRIDE.lock() {
            *slot = Some(Launch {
                program: "python3".to_string(),
                args: vec!["-c".to_string(), script.to_string()],
                cwd: None,
                pythonpath: None,
            });
        }
    }

    #[test]
    fn dead_sidecar_fails_fast_and_the_next_request_handshakes_again() {
        reset();
        install_python(
            r#"
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    req = json.loads(line)
    method = req.get("method")
    if method == "system.handshake":
        result = {"protocol": "image-toolkit-bridge", "version": "1.0.0", "compatibility": {"min": "1.0.0", "max": "1.0.0"}, "capabilities": ["system"]}
    elif method == "die":
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": {"ok": True}}) + "\n")
        sys.stdout.flush()
        raise SystemExit(0)
    else:
        result = {"ok": True, "method": method}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}) + "\n")
    sys.stdout.flush()
"#,
        );
        let started = Instant::now();
        let first = exchange(
            json!({"jsonrpc": "2.0", "id": "ping-1", "method": "system.ping", "params": {}}),
            None,
        )
        .unwrap();
        assert_eq!(first["result"]["method"], "system.ping");
        exchange(
            json!({"jsonrpc": "2.0", "id": "die-1", "method": "die", "params": {}}),
            None,
        )
        .unwrap();
        let restarted = Instant::now();
        let second = exchange(
            json!({"jsonrpc": "2.0", "id": "ping-2", "method": "system.ping", "params": {}}),
            None,
        )
        .unwrap();
        assert_eq!(second["result"]["method"], "system.ping");
        assert!(restarted.elapsed() < Duration::from_secs(5));
        assert!(started.elapsed() < Duration::from_secs(5));

        invalidate_session();
        install_python("import sys; sys.exit(1)");
        let crashed = Instant::now();
        let error = exchange(
            json!({"jsonrpc": "2.0", "id": "ping-3", "method": "system.ping", "params": {}}),
            None,
        )
        .unwrap_err();
        assert!(crashed.elapsed() < Duration::from_secs(5), "{error}");
        assert!(
            error.contains("exited")
                || error.contains("handshake")
                || error.contains("write")
                || error.contains("not running")
        );
        reset();
    }
}

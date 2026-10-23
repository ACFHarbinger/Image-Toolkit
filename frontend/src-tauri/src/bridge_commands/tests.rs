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
fn recognizes_job_events_without_response_ids() {
    assert!(is_event(
        &json!({"channel": "jobs", "seq": 1, "payload": {"state": "done"}})
    ));
    assert!(!is_event(&json!({"jsonrpc": "2.0", "id": 1, "result": {}})));
    assert!(!is_event(
        &json!({"channel": "jobs", "seq": -1, "payload": {}})
    ));
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

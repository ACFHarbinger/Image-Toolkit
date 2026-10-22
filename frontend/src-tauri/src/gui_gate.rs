//! Single-instance gate for installed and checkout builds (#873 / #877).
//!
//! Same protocol as `middleware.src.supervisor.gui_gate.GuiInstance`: an
//! exclusive `flock` on `{data_dir}/gui.lock` (what `filelock.FileLock`
//! takes on Unix) and a mode `0600` socket at `{data_dir}/gui.focus.sock`.
//! A second process sends `{"op":"focus"}` and exits so the owner can
//! restore its windows. The lock lives in this process, so a packaged
//! build does not need a checkout or a system Python.

use std::fs::File;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;
use tauri::AppHandle;

const FOCUS_OP: &str = "focus";
const FOCUS_LINE: &[u8] = b"{\"op\":\"focus\"}\n";
const LOCK_NAME: &str = "gui.lock";
const SOCK_NAME: &str = "gui.focus.sock";

enum Claim {
    Acquired(OwnedGate),
    FocusedOther,
}

struct OwnedGate {
    /// Held open so the exclusive flock stays owned by this process.
    _lock: File,
    listener: std::os::unix::net::UnixListener,
    sock_path: PathBuf,
    stop: Arc<AtomicBool>,
}

pub fn start(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    match claim(&crate::window_registry::data_dir()).map_err(std::io::Error::other)? {
        Claim::FocusedOther => {
            app.exit(0);
            Ok(())
        }
        Claim::Acquired(gate) => {
            let handle = app.clone();
            thread::spawn(move || {
                serve(gate, move || {
                    let _ = crate::window_registry::restore(&handle);
                });
            });
            Ok(())
        }
    }
}

fn claim(data_dir: &Path) -> Result<Claim, String> {
    std::fs::create_dir_all(data_dir).map_err(|err| err.to_string())?;
    let lock_path = data_dir.join(LOCK_NAME);
    let sock_path = data_dir.join(SOCK_NAME);
    let file = open_lock(&lock_path)?;
    if !try_lock_exclusive(&file)? {
        drop(file);
        let _ = request_focus(&sock_path);
        return Ok(Claim::FocusedOther);
    }
    let listener = match bind_focus_socket(&sock_path) {
        Ok(listener) => listener,
        Err(err) => {
            drop(file);
            return Err(err);
        }
    };
    Ok(Claim::Acquired(OwnedGate {
        _lock: file,
        listener,
        sock_path,
        stop: Arc::new(AtomicBool::new(false)),
    }))
}

fn open_lock(path: &Path) -> Result<File, String> {
    use std::os::unix::ffi::OsStrExt;
    use std::os::unix::io::FromRawFd;
    let bytes = path.as_os_str().as_bytes();
    if bytes.contains(&0) {
        return Err("gui lock path contains NUL".into());
    }
    let mut buf = Vec::with_capacity(bytes.len() + 1);
    buf.extend_from_slice(bytes);
    buf.push(0);
    // O_NOFOLLOW matches filelock: a symlink must not redirect the lock.
    // O_CREAT | O_NOFOLLOW creates a regular file and fails if the final
    // component is already a symlink. Skip O_TRUNC so we don't wipe the
    // inode another holder has flocked; the lock is the flock, not the bytes.
    let flags = libc::O_RDWR | libc::O_CLOEXEC | libc::O_NOFOLLOW | libc::O_CREAT;
    let fd = unsafe { libc::open(buf.as_ptr().cast::<libc::c_char>(), flags, 0o644) };
    if fd < 0 {
        return Err(std::io::Error::last_os_error().to_string());
    }
    Ok(unsafe { File::from_raw_fd(fd) })
}

fn try_lock_exclusive(file: &File) -> Result<bool, String> {
    use std::os::unix::io::AsRawFd;
    let rc = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) };
    if rc == 0 {
        return Ok(true);
    }
    let err = std::io::Error::last_os_error();
    match err.raw_os_error() {
        Some(code) if code == libc::EAGAIN || code == libc::EWOULDBLOCK => Ok(false),
        _ => Err(err.to_string()),
    }
}

fn bind_focus_socket(path: &Path) -> Result<std::os::unix::net::UnixListener, String> {
    use std::os::unix::fs::PermissionsExt;
    if path.symlink_metadata().is_ok() {
        std::fs::remove_file(path).map_err(|err| err.to_string())?;
    }
    let listener = std::os::unix::net::UnixListener::bind(path).map_err(|err| err.to_string())?;
    let mut perms = std::fs::metadata(path)
        .map_err(|err| err.to_string())?
        .permissions();
    perms.set_mode(0o600);
    std::fs::set_permissions(path, perms).map_err(|err| err.to_string())?;
    Ok(listener)
}

fn request_focus(sock_path: &Path) -> bool {
    let mut sock = match std::os::unix::net::UnixStream::connect(sock_path) {
        Ok(sock) => sock,
        Err(_) => return false,
    };
    let timeout = Duration::from_secs(1);
    let _ = sock.set_read_timeout(Some(timeout));
    let _ = sock.set_write_timeout(Some(timeout));
    if sock.write_all(FOCUS_LINE).is_err() {
        return false;
    }
    let mut buf = [0u8; 64];
    let Ok(n) = sock.read(&mut buf) else {
        return false;
    };
    buf[..n].windows(2).any(|window| window == b"ok")
}

fn serve(gate: OwnedGate, mut on_focus: impl FnMut()) {
    loop {
        if gate.stop.load(Ordering::Relaxed) {
            break;
        }
        let mut conn = match gate.listener.accept() {
            Ok((conn, _)) => conn,
            Err(_) => break,
        };
        if gate.stop.load(Ordering::Relaxed) {
            break;
        }
        handle_conn(&mut conn, &mut on_focus);
    }
}

fn handle_conn(conn: &mut std::os::unix::net::UnixStream, on_focus: &mut impl FnMut()) {
    let _ = conn.set_read_timeout(Some(Duration::from_secs(1)));
    let mut buf = [0u8; 256];
    let Ok(n) = conn.read(&mut buf) else {
        return;
    };
    if n == 0 {
        return;
    }
    let line = buf[..n]
        .split(|byte| *byte == b'\n')
        .next()
        .unwrap_or(&buf[..n]);
    let Ok(value) = serde_json::from_slice::<serde_json::Value>(line) else {
        return;
    };
    if !value.is_object() {
        return;
    }
    if value.get("op").and_then(|op| op.as_str()) == Some(FOCUS_OP) {
        on_focus();
    }
    let _ = conn.write_all(b"ok\n");
}

#[cfg(test)]
mod tests {
    use super::{claim, serve, Claim};
    use std::fs;
    use std::sync::mpsc;
    use std::thread;
    use std::time::{Duration, SystemTime, UNIX_EPOCH};

    fn scratch_dir() -> std::path::PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("itk-gui-gate-{}-{nanos}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        dir
    }

    #[test]
    fn second_claim_focuses_the_owner_and_does_not_take_the_lock() {
        let dir = scratch_dir();
        let Claim::Acquired(gate) = claim(&dir).expect("owner") else {
            panic!("first claim should own the gate");
        };
        let stop = gate.stop.clone();
        let sock = gate.sock_path.clone();
        let (tx, rx) = mpsc::channel();
        let worker = thread::spawn(move || serve(gate, move || tx.send(()).expect("focus")));
        let second = claim(&dir).expect("second claim");
        assert!(matches!(second, Claim::FocusedOther));
        rx.recv_timeout(Duration::from_secs(2))
            .expect("owner saw focus");
        stop.store(true, std::sync::atomic::Ordering::Relaxed);
        let _ = std::os::unix::net::UnixStream::connect(&sock);
        worker.join().expect("serve thread");
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn released_lock_allows_a_new_owner() {
        let dir = scratch_dir();
        let Claim::Acquired(gate) = claim(&dir).expect("owner") else {
            panic!("first claim should own the gate");
        };
        drop(gate);
        let Claim::Acquired(gate) = claim(&dir).expect("reacquire") else {
            panic!("lock should be free after the owner drops it");
        };
        drop(gate);
        let _ = fs::remove_dir_all(&dir);
    }
}

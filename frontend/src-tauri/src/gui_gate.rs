//! Single-instance gate for installed and checkout builds (#873 / #877).
//!
//! Same protocol as `middleware.src.supervisor.gui_gate.GuiInstance`: an
//! exclusive lock on `{data_dir}/gui.lock` (`flock` on Unix, a 1-byte
//! `LockFileEx` on Windows — what `filelock.FileLock` takes) and a socket
//! at `{data_dir}/gui.focus.sock`. A second process sends `{"op":"focus"}`
//! and exits so the owner can restore its windows. The lock lives in this
//! process, so a packaged build does not need a checkout or a system Python.

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
    /// Held open so the exclusive lock stays owned by this process.
    _lock: File,
    listener: FocusListener,
    sock_path: PathBuf,
    stop: Arc<AtomicBool>,
}

#[cfg(unix)]
type FocusListener = std::os::unix::net::UnixListener;

#[cfg(windows)]
struct FocusListener {
    socket: std::os::windows::io::OwnedSocket,
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

fn dispatch_focus(buf: &[u8], on_focus: &mut impl FnMut()) -> bool {
    if buf.is_empty() {
        return false;
    }
    let line = buf.split(|byte| *byte == b'\n').next().unwrap_or(buf);
    let Ok(value) = serde_json::from_slice::<serde_json::Value>(line) else {
        return false;
    };
    if !value.is_object() {
        return false;
    }
    if value.get("op").and_then(|op| op.as_str()) == Some(FOCUS_OP) {
        on_focus();
    }
    true
}

#[cfg(unix)]
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

#[cfg(unix)]
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

#[cfg(unix)]
fn bind_focus_socket(path: &Path) -> Result<FocusListener, String> {
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

#[cfg(unix)]
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
        match accept_client(&gate.listener) {
            Ok(mut conn) => {
                if gate.stop.load(Ordering::Relaxed) {
                    break;
                }
                handle_conn(&mut conn, &mut on_focus);
            }
            // A transient accept error (ECONNABORTED, EMFILE, ...) must not
            // kill the listener: a dead listener makes later instances
            // exit after a failed focus request, with no window restored.
            // Back off and keep serving while the gate is held.
            Err(err) => {
                log::warn!("gui gate accept error: {err}");
                thread::sleep(Duration::from_millis(50));
            }
        }
    }
}

#[cfg(unix)]
fn accept_client(listener: &FocusListener) -> std::io::Result<std::os::unix::net::UnixStream> {
    listener.accept().map(|(conn, _)| conn)
}

#[cfg(unix)]
fn handle_conn(conn: &mut std::os::unix::net::UnixStream, on_focus: &mut impl FnMut()) {
    let _ = conn.set_read_timeout(Some(Duration::from_secs(1)));
    let mut buf = [0u8; 256];
    let Ok(n) = conn.read(&mut buf) else {
        return;
    };
    if dispatch_focus(&buf[..n], on_focus) {
        let _ = conn.write_all(b"ok\n");
    }
}

#[cfg(windows)]
mod win {
    use super::{dispatch_focus, FocusListener, FOCUS_LINE};
    use std::fs::File;
    use std::os::windows::fs::OpenOptionsExt;
    use std::os::windows::io::{AsRawHandle, AsRawSocket, FromRawSocket, OwnedSocket, RawSocket};
    use std::path::Path;
    use std::time::Duration;

    const FILE_SHARE_READ: u32 = 0x00000001;
    const FILE_SHARE_WRITE: u32 = 0x00000002;
    const FILE_SHARE_DELETE: u32 = 0x00000004;
    const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x00000400;
    const INVALID_FILE_ATTRIBUTES: u32 = 0xFFFFFFFF;
    const ERROR_FILE_NOT_FOUND: u32 = 2;
    const ERROR_PATH_NOT_FOUND: u32 = 3;
    const ERROR_SHARING_VIOLATION: u32 = 32;
    const ERROR_LOCK_VIOLATION: u32 = 33;
    const LOCKFILE_FAIL_IMMEDIATELY: u32 = 0x00000001;
    const LOCKFILE_EXCLUSIVE_LOCK: u32 = 0x00000002;
    const AF_UNIX: i32 = 1;
    const SOCK_STREAM: i32 = 1;
    const SOL_SOCKET: i32 = 0xffff;
    const SO_RCVTIMEO: i32 = 0x1006;
    const SO_SNDTIMEO: i32 = 0x1005;
    const INVALID_SOCKET: RawSocket = !0;
    const UNIX_PATH_MAX: usize = 108;

    #[repr(C)]
    struct Overlapped {
        internal: usize,
        internal_high: usize,
        offset: u32,
        offset_high: u32,
        h_event: *mut std::ffi::c_void,
    }

    #[repr(C)]
    struct SockAddrUn {
        family: u16,
        path: [u8; UNIX_PATH_MAX],
    }

    #[repr(C)]
    struct WsaData {
        w_version: u16,
        w_high_version: u16,
        description: [u8; 257],
        system_status: [u8; 129],
        max_sockets: u16,
        max_udp_dg: u16,
        vendor_info: *mut u8,
    }

    #[link(name = "kernel32")]
    extern "system" {
        fn GetFileAttributesW(path: *const u16) -> u32;
        fn GetLastError() -> u32;
        fn LockFileEx(
            file: *mut std::ffi::c_void,
            flags: u32,
            reserved: u32,
            bytes_low: u32,
            bytes_high: u32,
            overlapped: *mut Overlapped,
        ) -> i32;
    }

    #[link(name = "ws2_32")]
    extern "system" {
        fn WSAStartup(version: u16, data: *mut WsaData) -> i32;
        fn WSAGetLastError() -> i32;
        fn socket(af: i32, kind: i32, protocol: i32) -> RawSocket;
        fn bind(sock: RawSocket, addr: *const SockAddrUn, len: i32) -> i32;
        fn listen(sock: RawSocket, backlog: i32) -> i32;
        fn accept(sock: RawSocket, addr: *mut u8, len: *mut i32) -> RawSocket;
        fn connect(sock: RawSocket, addr: *const SockAddrUn, len: i32) -> i32;
        fn send(sock: RawSocket, buf: *const u8, len: i32, flags: i32) -> i32;
        fn recv(sock: RawSocket, buf: *mut u8, len: i32, flags: i32) -> i32;
        fn setsockopt(sock: RawSocket, level: i32, name: i32, value: *const u8, len: i32) -> i32;
    }

    fn wsa_error() -> i32 {
        unsafe { WSAGetLastError() }
    }

    fn startup() -> Result<(), String> {
        use std::sync::OnceLock;
        static STARTED: OnceLock<Result<(), i32>> = OnceLock::new();
        let result = STARTED.get_or_init(|| {
            // Winsock is process-wide and refcounted. Tauri may have started
            // it already; a second WSAStartup is the supported way to join.
            let mut data = std::mem::MaybeUninit::<WsaData>::zeroed();
            let rc = unsafe { WSAStartup(0x0202, data.as_mut_ptr()) };
            if rc == 0 {
                Ok(())
            } else {
                Err(rc)
            }
        });
        match *result {
            Ok(()) => Ok(()),
            Err(code) => Err(format!("WSAStartup failed: {code}")),
        }
    }

    fn is_reparse_point(path: &Path) -> Result<bool, String> {
        use std::os::windows::ffi::OsStrExt;
        let mut wide: Vec<u16> = path.as_os_str().encode_wide().collect();
        wide.push(0);
        let attrs = unsafe { GetFileAttributesW(wide.as_ptr()) };
        if attrs == INVALID_FILE_ATTRIBUTES {
            let err = unsafe { GetLastError() };
            if err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND {
                return Ok(false);
            }
            return Err(format!("gui lock attributes: {err}"));
        }
        Ok(attrs & FILE_ATTRIBUTE_REPARSE_POINT != 0)
    }

    pub(super) fn open_lock(path: &Path) -> Result<File, String> {
        use std::fs::OpenOptions;
        if is_reparse_point(path)? {
            return Err(format!("gui lock is a reparse point: {}", path.display()));
        }
        OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .share_mode(FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE)
            .open(path)
            .map_err(|err| err.to_string())
    }

    pub(super) fn try_lock_exclusive(file: &File) -> Result<bool, String> {
        let mut overlapped = unsafe { std::mem::zeroed::<Overlapped>() };
        // filelock's Windows lock is msvcrt.locking of 1 byte at offset 0.
        let held = unsafe {
            LockFileEx(
                file.as_raw_handle(),
                LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY,
                0,
                1,
                0,
                &mut overlapped,
            )
        };
        if held != 0 {
            return Ok(true);
        }
        let err = unsafe { GetLastError() };
        if err == ERROR_LOCK_VIOLATION || err == ERROR_SHARING_VIOLATION {
            return Ok(false);
        }
        Err(format!("LockFileEx failed: {err}"))
    }

    fn socket_addr(path: &Path) -> Result<SockAddrUn, String> {
        let text = path
            .to_str()
            .ok_or_else(|| format!("focus socket path is not utf-8: {}", path.display()))?;
        let bytes = text.as_bytes();
        if bytes.is_empty() || bytes.len() >= UNIX_PATH_MAX || bytes.contains(&0) {
            return Err(format!(
                "focus socket path must fit in {} bytes: {}",
                UNIX_PATH_MAX - 1,
                path.display()
            ));
        }
        let mut addr = SockAddrUn {
            family: AF_UNIX as u16,
            path: [0; UNIX_PATH_MAX],
        };
        addr.path[..bytes.len()].copy_from_slice(bytes);
        Ok(addr)
    }

    fn win_socket() -> Result<OwnedSocket, String> {
        startup()?;
        let raw = unsafe { socket(AF_UNIX, SOCK_STREAM, 0) };
        if raw == INVALID_SOCKET {
            return Err(format!("AF_UNIX socket: {}", wsa_error()));
        }
        Ok(unsafe { OwnedSocket::from_raw_socket(raw) })
    }

    pub(super) fn bind_focus_socket(path: &Path) -> Result<FocusListener, String> {
        if path.symlink_metadata().is_ok() {
            std::fs::remove_file(path).map_err(|err| err.to_string())?;
        }
        let owned = win_socket()?;
        let addr = socket_addr(path)?;
        let len = std::mem::size_of::<SockAddrUn>() as i32;
        let rc = unsafe { bind(owned.as_raw_socket(), &addr, len) };
        if rc != 0 {
            return Err(format!("bind focus socket: {}", wsa_error()));
        }
        let rc = unsafe { listen(owned.as_raw_socket(), 4) };
        if rc != 0 {
            return Err(format!("listen focus socket: {}", wsa_error()));
        }
        Ok(FocusListener { socket: owned })
    }

    fn set_timeout(sock: RawSocket, millis: u32) {
        let bytes = millis.to_ne_bytes();
        unsafe {
            setsockopt(
                sock,
                SOL_SOCKET,
                SO_RCVTIMEO,
                bytes.as_ptr(),
                bytes.len() as i32,
            );
            setsockopt(
                sock,
                SOL_SOCKET,
                SO_SNDTIMEO,
                bytes.as_ptr(),
                bytes.len() as i32,
            );
        }
    }

    fn send_all(sock: RawSocket, mut buf: &[u8]) -> bool {
        while !buf.is_empty() {
            let sent = unsafe { send(sock, buf.as_ptr(), buf.len() as i32, 0) };
            if sent <= 0 {
                return false;
            }
            buf = &buf[sent as usize..];
        }
        true
    }

    pub(super) fn request_focus(sock_path: &Path) -> bool {
        let Ok(addr) = socket_addr(sock_path) else {
            return false;
        };
        let Ok(owned) = win_socket() else {
            return false;
        };
        let len = std::mem::size_of::<SockAddrUn>() as i32;
        if unsafe { connect(owned.as_raw_socket(), &addr, len) } != 0 {
            return false;
        }
        set_timeout(owned.as_raw_socket(), 1000);
        if !send_all(owned.as_raw_socket(), FOCUS_LINE) {
            return false;
        }
        let mut buf = [0u8; 64];
        let n = unsafe { recv(owned.as_raw_socket(), buf.as_mut_ptr(), buf.len() as i32, 0) };
        n > 0 && buf[..n as usize].windows(2).any(|window| window == b"ok")
    }

    pub(super) fn accept_client(listener: &FocusListener) -> std::io::Result<OwnedSocket> {
        let raw = unsafe {
            accept(
                listener.socket.as_raw_socket(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
            )
        };
        if raw == INVALID_SOCKET {
            return Err(std::io::Error::from_raw_os_error(wsa_error()));
        }
        Ok(unsafe { OwnedSocket::from_raw_socket(raw) })
    }

    pub(super) fn handle_conn(conn: &mut OwnedSocket, on_focus: &mut impl FnMut()) {
        set_timeout(
            conn.as_raw_socket(),
            Duration::from_secs(1).as_millis() as u32,
        );
        let mut buf = [0u8; 256];
        let n = unsafe { recv(conn.as_raw_socket(), buf.as_mut_ptr(), buf.len() as i32, 0) };
        if n <= 0 || !dispatch_focus(&buf[..n as usize], on_focus) {
            return;
        }
        send_all(conn.as_raw_socket(), b"ok\n");
    }
}

#[cfg(windows)]
use win::{
    accept_client, bind_focus_socket, handle_conn, open_lock, request_focus, try_lock_exclusive,
};

#[cfg(all(test, unix))]
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

#[cfg(test)]
mod protocol_tests {
    #[test]
    fn focus_payload_reaches_the_owner_and_other_objects_still_ack() {
        let mut focused = false;
        assert!(super::dispatch_focus(b"{\"op\":\"focus\"}\n", &mut || {
            focused = true
        }));
        assert!(focused);
        let mut focused = false;
        assert!(super::dispatch_focus(b"{\"op\": \"focus\"}\n", &mut || {
            focused = true
        }));
        assert!(focused);
        assert!(!super::dispatch_focus(b"not-json\n", &mut || {}));
        assert!(super::dispatch_focus(b"{\"op\":\"other\"}\n", &mut || {}));
    }
}

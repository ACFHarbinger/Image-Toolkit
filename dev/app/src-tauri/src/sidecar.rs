//! Sidecar restart policy (locks #3, #4, #12) — Rust port of the Python
//! reference implementation at `dev/tool/sidecar/policy.py::SidecarRestartPolicy`,
//! which was written specifically so this port could be one-to-one. Actual
//! process spawn/kill wiring (window-open -> spawn, window-close -> kill,
//! `--stdio` JSON-RPC handshake) is #408 host-wiring, owned by opencode; this
//! module only ports the pure decision logic so that work has a home to land
//! in without re-deriving the rules.
//!
//! Rules:
//! - Lifetime is the window (lock #3): spawn on window open, kill on close.
//! - A crash BEFORE a successful `initialize` is a visible hard failure with
//!   NO restart (lock #12).
//! - After a successful `initialize`, exactly ONE automatic restart is
//!   allowed (lock #4). No loop-restart, ever.
//! - A clean exit (window closed) never restarts, regardless of initialize
//!   state.

use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{self, Receiver};
use std::time::Duration;

use anyhow::{bail, Context, Result};
use serde_json::Value;

pub const MAX_AUTO_RESTARTS: u32 = 1;

/// How long the host waits for the sidecar's `initialize` response before
/// declaring the handshake failed (visible hard failure path).
pub const HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(15);

/// How long the host waits for a reply to a request made after the
/// handshake (`list_records`, `list_artifacts`, ...). The sidecar is a
/// local process on the same machine, so a generous fixed timeout is
/// sufficient for this skeleton; a wedged sidecar past this point is
/// treated as a request failure, not (yet) fed back into the restart
/// policy (#409/#407 scope stops at "the call returns or errors").
pub const RPC_TIMEOUT: Duration = Duration::from_secs(10);

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RestartDecision {
    pub restart: bool,
    pub reason: &'static str,
}

#[derive(Debug, Default)]
pub struct SidecarRestartPolicy {
    initialized: bool,
    restarts: u32,
}

impl SidecarRestartPolicy {
    pub fn new() -> Self {
        Self::default()
    }

    #[allow(dead_code)] // part of the Python->Rust reference port; used by tests
    pub fn initialized(&self) -> bool {
        self.initialized
    }

    #[allow(dead_code)] // part of the Python->Rust reference port; used by tests
    pub fn restarts_used(&self) -> u32 {
        self.restarts
    }

    pub fn on_initialize_success(&mut self) {
        self.initialized = true;
    }

    pub fn on_initialize_failure(&mut self) {
        self.initialized = false;
    }

    /// Decide what the host should do when the sidecar process exits.
    pub fn on_exit(&mut self, clean: bool) -> RestartDecision {
        if clean {
            return RestartDecision {
                restart: false,
                reason: "clean exit (window closed); no restart",
            };
        }
        if !self.initialized {
            return RestartDecision {
                restart: false,
                reason: "crash before successful initialize: visible hard failure, no restart (lock 12)",
            };
        }
        if self.restarts >= MAX_AUTO_RESTARTS {
            return RestartDecision {
                restart: false,
                reason: "crashed after the one allowed restart: visible hard failure, no loop (lock 4)",
            };
        }
        self.restarts += 1;
        RestartDecision {
            restart: true,
            reason: "crash after successful initialize: one automatic restart (lock 4)",
        }
    }
}

/// The argv the host uses to spawn the sidecar.
///
/// #408 host-wiring: the sidecar runs the devtool host's *own* Python (the
/// bundled, isolated interpreter per lock #5) and the host's `dev/` package —
/// never the workspace's python or packages. In the source-built first Linux
/// release (lock #1) that is `<repo-root>/.venv/bin/python dev sidecar
/// --stdio` (lock #8: the host appends `--stdio`). Workspace-python
/// resolution (lock #10) is for *command plugins* (deepseek #412), not the
/// sidecar.
#[derive(Debug, Clone)]
pub struct SidecarCommand {
    pub argv: Vec<String>,
    pub cwd: PathBuf,
}

impl SidecarCommand {
    /// `<repo_root>/.venv/bin/python <repo_root>/dev sidecar --stdio`.
    pub fn for_repo_root(repo_root: &Path) -> Self {
        SidecarCommand {
            argv: vec![
                repo_root.join(".venv").join("bin").join("python").to_string_lossy().into_owned(),
                repo_root.join("dev").to_string_lossy().into_owned(),
                "sidecar".into(),
                "--stdio".into(),
            ],
            cwd: repo_root.to_path_buf(),
        }
    }
}

/// A live sidecar child process plus its piped stdin and a background
/// reader thread draining stdout line-by-line onto `stdout_rx` (ChildStdout
/// has no read timeout, so a dedicated thread is how a `recv_timeout` bound
/// is possible on each reply). One request in flight at a time — every
/// caller here is synchronous, so replies are consumed in request order.
pub struct SidecarProcess {
    child: Child,
    stdin: ChildStdin,
    stdout_rx: Receiver<String>,
    next_id: u64,
}

impl SidecarProcess {
    pub fn spawn(command: &SidecarCommand) -> Result<Self> {
        let mut child = Command::new(&command.argv[0])
            .args(&command.argv[1..])
            .current_dir(&command.cwd)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .with_context(|| format!("spawn sidecar: {:?}", command.argv))?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| anyhow::anyhow!("sidecar stdin not piped"))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| anyhow::anyhow!("sidecar stdout not piped"))?;

        let (tx, rx) = mpsc::channel::<String>();
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            let mut line = String::new();
            loop {
                line.clear();
                match reader.read_line(&mut line) {
                    Ok(0) => break, // EOF: sidecar exited
                    Ok(_) => {
                        if tx.send(std::mem::take(&mut line)).is_err() {
                            break; // SidecarProcess dropped
                        }
                    }
                    Err(_) => break,
                }
            }
        });

        Ok(SidecarProcess {
            child,
            stdin,
            stdout_rx: rx,
            next_id: 1,
        })
    }

    /// Send one JSON-RPC 2.0 request with optional params and wait up to `timeout` for its reply.
    /// Returns the `result` value; a JSON-RPC `error` reply becomes an Err.
    fn request(&mut self, method: &str, timeout: Duration) -> Result<Value> {
        self.request_with_params(method, None, timeout)
    }

    fn request_with_params(
        &mut self,
        method: &str,
        params: Option<Value>,
        timeout: Duration,
    ) -> Result<Value> {
        let id = self.next_id;
        self.next_id += 1;
        let mut payload = serde_json::json!({"jsonrpc": "2.0", "id": id, "method": method});
        if let Some(p) = params {
            payload["params"] = p;
        }
        self.stdin.write_all(serde_json::to_string(&payload)?.as_bytes())?;
        self.stdin.write_all(b"\n")?;
        self.stdin.flush()?;

        let line = self
            .stdout_rx
            .recv_timeout(timeout)
            .map_err(|_| anyhow::anyhow!("sidecar '{method}' timed out after {timeout:?}"))?;
        let value: Value = serde_json::from_str(&line)
            .with_context(|| format!("sidecar '{method}': non-JSON response: {line:?}"))?;
        if let Some(error) = value.get("error") {
            bail!("sidecar '{method}' error: {error}");
        }
        Ok(value["result"].clone())
    }

    /// JSON-RPC 2.0 `initialize` handshake over stdio (lock #8, D52 frozen
    /// contract): checks the reply names the sidecar server at the expected
    /// protocol version.
    pub fn initialize_handshake(&mut self, timeout: Duration) -> Result<()> {
        let result = self.request("initialize", timeout)?;
        if result["serverInfo"]["name"] != "devtool-sidecar" {
            bail!("sidecar handshake: unexpected serverInfo: {result}");
        }
        if result["protocolVersion"] != "1" {
            bail!("sidecar handshake: unexpected protocolVersion: {result}");
        }
        Ok(())
    }

    /// `list_records` (#409, lock 9): every `devtool.record` in the
    /// workspace, adapted from telemetry by the Python side.
    pub fn list_records(&mut self, timeout: Duration) -> Result<Value> {
        Ok(self.request("list_records", timeout)?["records"].clone())
    }

    /// `list_artifacts` (#410 shape): the discovered plugin registry.
    pub fn list_artifacts(&mut self, timeout: Duration) -> Result<Value> {
        Ok(self.request("list_artifacts", timeout)?["artifacts"].clone())
    }

    /// `get_meta_graph` (#415): 3D Tiered Galaxy meta-graph topology and nodes.
    pub fn get_meta_graph(&mut self, timeout: Duration) -> Result<Value> {
        self.request("get_meta_graph", timeout)
    }

    /// `get_flame_graph` (#416): Hierarchical 2D call tree and spans.
    pub fn get_flame_graph(&mut self, timeout: Duration) -> Result<Value> {
        self.request("get_flame_graph", timeout)
    }

    /// `get_metrics_timeline` (#416): Memory RSS progression and benchmark trends.
    pub fn get_metrics_timeline(&mut self, timeout: Duration) -> Result<Value> {
        self.request("get_metrics_timeline", timeout)
    }

    /// `get_pipeline_scrubber` (#418): 4D pipeline stage timeline and evaluation.
    pub fn get_pipeline_scrubber(&mut self, t_ms: Option<f64>, timeout: Duration) -> Result<Value> {
        self.request_with_params("get_pipeline_scrubber", Some(serde_json::json!({"t_ms": t_ms})), timeout)
    }

    /// `get_world_state` (#419): Persistent world state, camera bookmarks, and filters.
    pub fn get_world_state(&mut self, timeout: Duration) -> Result<Value> {
        self.request("get_world_state", timeout)
    }

    /// `save_world_state` (#419): Save world state to disk (.devtool/world_state.json).
    pub fn save_world_state(&mut self, world_state: Value, timeout: Duration) -> Result<Value> {
        self.request_with_params("save_world_state", Some(serde_json::json!({"world_state": world_state})), timeout)
    }

    /// Non-blocking: has the child exited?
    pub fn try_exited(&mut self) -> Option<std::process::ExitStatus> {
        self.child.try_wait().ok().flatten()
    }

    /// Kill the child and reap it (window close; never restarts).
    pub fn kill(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// Owns the sidecar child process for one window's lifetime.
///
/// #408 host-wiring: `start` spawns + handshakes + arms the crash monitor,
/// `stop` kills cleanly on window close, and `poll_crash` drives the restart
/// policy (lock #4/#12) when the child dies unexpectedly.
pub struct SidecarHandle {
    pub policy: SidecarRestartPolicy,
    pub command: SidecarCommand,
    pub process: Option<SidecarProcess>,
    pub running: bool,
}

impl SidecarHandle {
    pub fn new(command: SidecarCommand) -> Self {
        SidecarHandle {
            policy: SidecarRestartPolicy::new(),
            command,
            process: None,
            running: false,
        }
    }

    /// Spawn + `initialize` handshake. On success the policy is marked
    /// initialized and the crash monitor loop can begin.
    pub fn start(&mut self) -> Result<()> {
        if self.running || self.process.is_some() {
            return Ok(());
        }
        let mut process = SidecarProcess::spawn(&self.command)?;
        match process.initialize_handshake(HANDSHAKE_TIMEOUT) {
            Ok(()) => {
                self.policy.on_initialize_success();
                self.process = Some(process);
                self.running = true;
                Ok(())
            }
            Err(err) => {
                self.policy.on_initialize_failure();
                process.kill();
                // Lock #12: crash-before-handshake is a visible hard failure.
                bail!("sidecar initialize handshake failed: {err:#}");
            }
        }
    }

    /// #409 wiring: `devtool.record`s for the current workspace, via the
    /// running sidecar. Errs if the sidecar isn't up (not yet started, or
    /// down after a hard failure — locks #4/#12).
    pub fn list_records(&mut self) -> Result<Value> {
        match &mut self.process {
            Some(process) => process.list_records(RPC_TIMEOUT),
            None => bail!("sidecar is not running"),
        }
    }

    /// The discovered plugin registry, via the running sidecar.
    pub fn list_artifacts(&mut self) -> Result<Value> {
        match &mut self.process {
            Some(process) => process.list_artifacts(RPC_TIMEOUT),
            None => bail!("sidecar is not running"),
        }
    }

    pub fn get_meta_graph(&mut self) -> Result<Value> {
        match &mut self.process {
            Some(process) => process.get_meta_graph(RPC_TIMEOUT),
            None => bail!("sidecar is not running"),
        }
    }

    pub fn get_flame_graph(&mut self) -> Result<Value> {
        match &mut self.process {
            Some(process) => process.get_flame_graph(RPC_TIMEOUT),
            None => bail!("sidecar is not running"),
        }
    }

    pub fn get_metrics_timeline(&mut self) -> Result<Value> {
        match &mut self.process {
            Some(process) => process.get_metrics_timeline(RPC_TIMEOUT),
            None => bail!("sidecar is not running"),
        }
    }

    pub fn get_pipeline_scrubber(&mut self, t_ms: Option<f64>) -> Result<Value> {
        match &mut self.process {
            Some(process) => process.get_pipeline_scrubber(t_ms, RPC_TIMEOUT),
            None => bail!("sidecar is not running"),
        }
    }

    pub fn get_world_state(&mut self) -> Result<Value> {
        match &mut self.process {
            Some(process) => process.get_world_state(RPC_TIMEOUT),
            None => bail!("sidecar is not running"),
        }
    }

    pub fn save_world_state(&mut self, world_state: Value) -> Result<Value> {
        match &mut self.process {
            Some(process) => process.save_world_state(world_state, RPC_TIMEOUT),
            None => bail!("sidecar is not running"),
        }
    }

    /// Clean shutdown (window closed). Kills the child; never restarts.
    pub fn stop(&mut self) {
        self.running = false;
        if let Some(mut process) = self.process.take() {
            process.kill();
        }
    }

    /// Poll the child once. If it has exited:
    /// - clean stop (not running) -> nothing to do, monitor should exit.
    /// - unexpected exit -> drive `policy.on_exit(clean=false)`; if the
    ///   decision is to restart, respawn + re-handshake (a crash-before-
    ///   handshake on the *restart* is a hard failure, no second restart).
    ///
    /// Returns true while the monitor should keep polling.
    pub fn poll_crash(&mut self) -> bool {
        if !self.running {
            return false;
        }
        let exited = match &mut self.process {
            Some(process) => match process.try_exited() {
                Some(status) => {
                    log::warn!("sidecar exited unexpectedly: {status}");
                    Some(status)
                }
                None => return true,
            },
            None => return true,
        };
        let _ = exited;
        let decision = self.policy.on_exit(false);
        self.process = None;
        if !decision.restart {
            self.running = false;
            log::error!("sidecar hard failure: {}", decision.reason);
            return false;
        }
        log::info!("sidecar restart: {}", decision.reason);
        match self.start() {
            Ok(()) => true,
            Err(err) => {
                // Lock #4/#12: the one allowed restart must initialize or it
                // is a hard, visible error — no second restart.
                self.running = false;
                log::error!("sidecar restart failed (hard failure): {err:#}");
                false
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clean_exit_never_restarts() {
        let mut policy = SidecarRestartPolicy::new();
        policy.on_initialize_success();
        assert!(!policy.on_exit(true).restart);
    }

    #[test]
    fn crash_before_initialize_does_not_restart() {
        let mut policy = SidecarRestartPolicy::new();
        assert!(!policy.on_exit(false).restart);
    }

    #[test]
    fn one_restart_allowed_after_initialize_then_hard_fail() {
        let mut policy = SidecarRestartPolicy::new();
        policy.on_initialize_success();
        let first = policy.on_exit(false);
        assert!(first.restart);
        assert_eq!(policy.restarts_used(), 1);
        let second = policy.on_exit(false);
        assert!(!second.restart);
    }

    #[test]
    fn command_for_repo_root_appends_stdio() {
        let command = SidecarCommand::for_repo_root(Path::new("/repo"));
        assert_eq!(
            command.argv,
            vec![
                "/repo/.venv/bin/python".to_string(),
                "/repo/dev".to_string(),
                "sidecar".to_string(),
                "--stdio".to_string(),
            ]
        );
    }

    #[test]
    fn start_spawns_real_sidecar_and_handshakes() {
        // Use the real `python dev/ sidecar --stdio` in this checkout — the
        // same invocation the host uses in the source-built release.
        // CARGO_MANIFEST_DIR is .../dev/app/src-tauri; repo root is three
        // levels up. (A `../..` typo here previously made this test always
        // silently skip instead of exercising the real sidecar — the same
        // bug that broke `just devtool-app` in production; see AGENT_BUS.md
        // 2026-08-18.)
        let repo_root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..");
        let command = SidecarCommand::for_repo_root(&repo_root);
        let python = Path::new(&command.argv[0]);
        let dev = Path::new(&command.argv[1]);
        if !python.exists() || !dev.exists() {
            // A checkout without `.venv` (fresh clone, no `just setup` yet)
            // is the only expected reason to skip; print loudly so a wrong
            // repo_root computation can't hide behind a quiet skip again.
            eprintln!("SKIPPING start_spawns_real_sidecar_and_handshakes: sidecar python/dev not present at {repo_root:?} — run `just setup` first");
            return;
        }
        let mut handle = SidecarHandle::new(command);
        handle.start().expect("spawn + initialize handshake");
        assert!(handle.policy.initialized());

        // #409 wiring: both RPC methods must round-trip through the same
        // persistent-reader plumbing the handshake used.
        let records = handle.list_records().expect("list_records");
        assert!(records.is_array());
        let artifacts = handle.list_artifacts().expect("list_artifacts");
        assert!(artifacts.is_array());

        handle.stop();
        assert!(!handle.running);
    }

    #[test]
    fn rpc_call_before_start_errs() {
        let command = SidecarCommand::for_repo_root(Path::new("/repo"));
        let mut handle = SidecarHandle::new(command);
        assert!(handle.list_records().unwrap_err().to_string().contains("not running"));
    }

    #[test]
    fn crash_drives_restart_policy() {
        // A command that dies instantly (nonzero exit) cannot handshake, so
        // the policy never sees a successful initialize and start() fails
        // with a hard error (lock #12) — no restart.
        let command = SidecarCommand {
            argv: vec!["/bin/sh".into(), "-c".into(), "exit 7".into()],
            cwd: PathBuf::from("/"),
        };
        let mut handle = SidecarHandle::new(command);
        let err = handle.start().unwrap_err();
        assert!(!handle.policy.initialized());
        assert!(!handle.running);
        assert!(err.to_string().contains("handshake failed"));
    }
}
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

#![allow(dead_code)] // consumed by #408 host wiring, not yet called from lib.rs

pub const MAX_AUTO_RESTARTS: u32 = 1;

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

    pub fn initialized(&self) -> bool {
        self.initialized
    }

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

/// Owns the sidecar child process for one window's lifetime.
///
/// TODO(#408, opencode): wire actual `--stdio` process spawn (workspace
/// Python resolution per lock #10, `Command::spawn`) on window "created"/
/// "focused" and kill-on-"close-requested"; drive `SidecarRestartPolicy`
/// from the child's exit status via `on_exit`. This struct is intentionally
/// inert (no process yet) so #407 doesn't block on that wiring.
#[derive(Default)]
pub struct SidecarHandle {
    pub policy: SidecarRestartPolicy,
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
}

# #879 supervisor binding plan and spike proposals

Status: planning only; this branch contains no implementation or test results.

## Remaining #879 work

`VaultManager.handoff_daemon_lease` currently accepts zero PID/TTL and an empty supervisor session. Native unseal checks bindings when supplied. Transit keys are stored in owner-only files, which remain readable to other processes under the same OS account.

The production handoff must reject missing PID, non-positive TTL and empty session before minting. Enforcement must cover every production mint entry point; an optional Python flag alone does not establish that boundary. Keep compatibility-only unbound APIs separate from the production path.

The current supervisor spawns fake child roles and has no production lease transport. Implement a readiness handshake that keeps a new child from opening its store before the parent knows its PID, mints a bound lease, and delivers it over a private channel. Pass the expected supervisor session before spawn; do not put leases or raw keys in process arguments, logs or heartbeat files. A mint or delivery failure must prevent that child from becoming ready and clean up the failed spawn.

Define lease renewal before choosing a TTL. Restarted children need leases for their new PID. Reattached durable children need an authenticated renewal/session transition; generating a new session UUID and silently reusing their old lease is insufficient. Retain the existing daemon key reuse contract across multiple stores and document retirement/cleanup. Unlinking keys must not break later store opens or renewal; FD-based handoff is a separate design option.

Acceptance: targeted rejection, spawn/handoff failure, restart, renewal, reattachment, cross-store and genuine child-process tests. Same-account file access remains a documented limitation rather than process isolation.

Merging these notes does not complete #879, establish Gate A PASS or open Gate B. Gate transitions require the coordinator's recorded acceptance evidence.

## Spike proposals for Harbinger

These are proposals, not measured OS signoffs or go/no-go decisions:

- #889 tray: conditional candidate; verify startup, focus, hide/restore, packaging and tray visibility per OS, including Wayland.
- #890 ComfyUI: evaluate an isolated view and external-browser fallback against the existing capabilities/CSP.
- #892 video: carry forward the measured still-frame scope; measure codec/playback/scrubbing behavior before promising support.
- #893 wallpaper/presenter: evaluate presenter behavior and platform-native per-monitor integration. Verify durable slideshow lifecycle separately.

Harbinger decides go/no-go. Any retained PySide6 exception must follow the migration ledger and approval process.

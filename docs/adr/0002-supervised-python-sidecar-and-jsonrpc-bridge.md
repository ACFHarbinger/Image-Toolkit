# ADR-0002: Supervised Python Sidecar, JSON-RPC Bridge, and Single `HostClient`

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#875](https://github.com/ACFHarbinger/Image-Toolkit/issues/875), [#876](https://github.com/ACFHarbinger/Image-Toolkit/issues/876)

## Context

The Tauri frontend needs access to Python ML pipelines (PyTorch, ComfyUI, LoRA, ASP, CSG, CRE) and the C++ `backend` extension (`pybind11`), while remote web and mobile clients access the same capabilities through Django (`api/`). Early Tauri prototypes duplicated database and conversion logic directly inside Rust (`db.rs`, `core_commands.rs`, `video_commands.rs`, `auth_commands.rs`), including a stale `postgresql://localhost` default.

## Decision

1. **Versioned JSON-RPC over stdio sidecar:** A supervised Python sidecar speaks framed, versioned JSON-RPC over `stdio`. `stdout` carries exclusively framed protocol messages; `stderr` carries redacted diagnostics.
2. **Tested version-pair handshake:** The desktop UI and sidecar ship as a tested version pair verified by a startup handshake. Django (`api/`) exposes the same services remotely within a documented compatibility range.
3. **Single `HostClient` with transport adapters:** The frontend routes all capability calls through one `HostClient` backed by pluggable transport adapters (`sidecar`, `django`, `native-rust`) driven by `contracts/methods.toml`. Retiring duplicate Rust commands (`db.rs`, `core_commands.rs`, `video_commands.rs`, `auth_commands.rs`) becomes a routing-table update verified by a transport conformance suite.
4. **Restart contract (`bridge.down` / `bridge.ready`):** When the sidecar restarts, the supervisor emits `bridge.down` and `bridge.ready`. In-flight session requests fail deterministically with the structured error envelope, durable jobs reattach automatically, and the current UI route and ephemeral state survive (verified by a `SIGKILL` smoke test in CI).

## Consequences

- Business logic is written once in `middleware/src/services/<feature>/` and consumed identically by the Tauri sidecar, Django REST API, and legacy Qt worker shims.
- Duplicate Rust command modules and the legacy `postgresql://localhost` fallback in `db.rs` are systematically retired as capabilities migrate.

# Architecture Decision Records (ADRs)

This directory records the locked architectural decisions governing the **Tauri Migration & Architecture Refactor** ([`docs/moon/roadmaps/tauri_migration.md`](../moon/roadmaps/tauri_migration.md), tracking issue [#864](https://github.com/ACFHarbinger/Image-Toolkit/issues/864)) and the **Cloud Jobs Service** ([`docs/moon/roadmaps/cloud_jobs.md`](../moon/roadmaps/cloud_jobs.md), tracking issue [#824](https://github.com/ACFHarbinger/Image-Toolkit/issues/824)).

All decisions below were locked on **2026-10-19** by Harbinger and the engineering agent team unless noted otherwise.

## Index of Decisions

| ADR | Title | Domain | Status |
|---|---|---|---|
| [ADR-0001](0001-tauri-single-desktop-ui-and-pyside-freeze.md) | Tauri 2 as Sole Target Desktop UI and PySide6 Freeze | Desktop / Migration | Accepted |
| [ADR-0002](0002-supervised-python-sidecar-and-jsonrpc-bridge.md) | Supervised Python Sidecar, JSON-RPC Bridge, and Single `HostClient` | Bridge / IPC | Accepted |
| [ADR-0003](0003-json-schema-contracts-and-eventhub.md) | JSON Schema Contract Spine, Error/Cancel Envelopes, and Generated EventHub | Contracts / State | Accepted |
| [ADR-0004](0004-process-supervisor-and-sibling-daemons.md) | External Process Supervisor, Sibling Daemons, and Single-Instance Gate | Processes / Lifecycle | Accepted |
| [ADR-0005](0005-cpp-vault-and-sealed-per-store-leases.md) | C++ Core Vault Ownership and Sealed Per-Store Credential Leases | Security / Crypto | Accepted |
| [ADR-0006](0006-unified-settings-and-additive-schema-migrations.md) | Shared Scoped Settings Service and Additive-Only Schema Migrations | Data / Settings | Accepted |
| [ADR-0007](0007-vite-platform-csp-and-catalog-shell.md) | Vite Build, Default-Deny Tauri Capabilities, Catalog Shell, and Design Tokens | Frontend / Security | Accepted |
| [ADR-0008](0008-cpp-thumbnail-service-and-webgl-canvas-host.md) | Zero-Copy C++ Thumbnail Streaming (`asset://`) and Shared WebGL2/WebGPU Canvas Host | Media / Rendering | Accepted |
| [ADR-0009](0009-command-handler-services-and-enforced-boundaries.md) | Command/Handler Service Layer and Tool-Enforced Module Boundaries | Architecture / SOLID | Accepted |
| [ADR-0010](0010-package-renames-and-submodule-absorption.md) | Package Renames (`middleware/`, `backend/`) and Submodule Absorption into One CMake Build | Repository / Build | Accepted |
| [ADR-0011](0011-migration-ledger-parity-and-coexistence-packaging.md) | Capability Migration Ledger, Differential Parity Oracle, and Coexistence Packaging | Migration / QA | Accepted |
| [ADR-0012](0012-cloud-jobs-sqlcipher-store-and-sharded-reconciler.md) | Cloud Jobs Dedicated SQLCipher Store (`cloud_jobs.db`), Sharded `JobSpec`, and Pure Reconciler | Cloud Jobs / Core | Accepted |
| [ADR-0013](0013-cloud-jobs-preflight-risk-rules-and-cost-caps.md) | Cloud Jobs Preflight Pipeline, Editable Risk Rules, Cost Calibration, and Leak Protection | Cloud Jobs / Safety | Accepted |
| [ADR-0014](0014-cloud-jobs-daemon-watchdog-relay-and-data-plane.md) | Cloud Jobs Local Daemon, Cloud Watchdog/Relay, Content-Addressed Data Plane, and Digest-Pinned Workers | Cloud Jobs / Runtime | Accepted |

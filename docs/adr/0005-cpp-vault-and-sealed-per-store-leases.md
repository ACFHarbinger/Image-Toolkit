# ADR-0005: C++ Core Vault Ownership and Sealed Per-Store Credential Leases

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#879](https://github.com/ACFHarbinger/Image-Toolkit/issues/879), [#835](https://github.com/ACFHarbinger/Image-Toolkit/issues/835), [#918](https://github.com/ACFHarbinger/Image-Toolkit/issues/918)

## Context

Passing plaintext vault keys or SQLCipher database passphrases through Python strings, Rust IPC payloads, or the webview increases the surface area for memory dumps, crash logs, and accidental serialization. Earlier Cloud Jobs drafts (#827) considered passing the `cloud_jobs.db` store secret over local IPC.

## Decision

1. **C++ core holds vault unlock and database keys (`backend::vault`):** Master keys and SQLCipher store keys reside exclusively in `mlock`-pinned C++ memory (`LockedSecret` in `backend/src/vault/vault.cpp`).
2. **Opaque session handle for the webview:** Unlocking the vault returns an opaque session handle to Python/Rust/webview callers; no plaintext key crosses the boundary.
3. **Sealed per-store leases for sibling daemons:** Daemons (such as the Cloud Jobs daemon) receive cryptographically **sealed per-store leases** bound to the target store, expiry timestamp, and supervisor session (`issue_sealed_lease` / `unseal_lease`). Only the C++ core can unseal a lease to open the encrypted SQLCipher store directly.

## Consequences

- Plaintext keys never traverse Python, Rust, or JSON-RPC stdio channels.
- Retires `auth_commands.rs` (#918) and replaces IPC key handoff in Cloud Jobs Gate B (#834–#835).

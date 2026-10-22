// Operation manifest: the routing table HostClient dispatches from
// (W0-12, #876; OpenCode §4).
//
// One row per operation: which transport serves it and whether the
// operation is cancelable. Bridge rows mirror `contracts/methods.toml`
// semantics (method name + cancelable flag); native rows name the Tauri
// command directly.
//
// RETIRING A RUST DUPLICATE = moving its row from `rust` to `sidecar`
// (fixing `method` to the contract name). No call site changes — the
// conformance suite must pass against the new transport, then the Rust
// body is deleted.

export type TransportKind = "sidecar" | "django" | "rust";

export interface OperationRow {
  readonly operation: string;
  readonly method: string;
  readonly transport: TransportKind;
  readonly cancelable: boolean;
}

export const OPERATION_MANIFEST: readonly OperationRow[] = [
  // Bridge operations (contracts/methods.toml; all currently cancelable=false).
  { operation: "ping", method: "system.ping", transport: "sidecar", cancelable: false },
  { operation: "submitJob", method: "jobs.submit", transport: "sidecar", cancelable: false },
  { operation: "cancelJob", method: "jobs.cancel", transport: "sidecar", cancelable: false },
  { operation: "jobStatus", method: "jobs.status", transport: "sidecar", cancelable: false },
  { operation: "listJobs", method: "jobs.list", transport: "sidecar", cancelable: false },
  // Native-only operations: dialogs, tray, notifications, OS. No business
  // methods may be added here (roadmap §1 — Rust owns native capabilities,
  // not a second implementation).
  { operation: "pickFiles", method: "pick_files", transport: "rust", cancelable: false },
  { operation: "notify", method: "notify", transport: "rust", cancelable: false },
  { operation: "setTrayState", method: "set_tray_state", transport: "rust", cancelable: false },
];

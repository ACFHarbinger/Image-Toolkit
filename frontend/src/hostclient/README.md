# HostClient (W0-12, #876)

One webview-facing client over the bridge transports:

- `SidecarTransport` — newline-framed JSON-RPC/stdio frames supplied by the
  native sidecar connection;
- `DjangoTransport` — the same bridge request over HTTP for remote/mobile;
- `RustTransport` — the native-only seam for Rust-owned commands.

`HostClient` owns readiness (`system.handshake` before commands), version
compatibility, bounded reconnects, typed jobs helpers and error-envelope
mapping. The frame shape is the shared W0-11 contract (`jsonrpc`, `id`,
`method`, `params`; `result` XOR `error`); no second JSON-RPC envelope or
parallel routing table is introduced.

The adapter conformance suite lives in `__tests__/` and runs the same checks
against all three transports with in-memory fakes. The sidecar server for the
stdio adapter is `middleware.src.sidecar`.

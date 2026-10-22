# HostClient (W0-12, #876)

One frontend entry point over three transport adapters. Frontend code calls
`hostClient.<operation>()` exclusively; the operation manifest routes each
operation to a transport. Retiring a duplicate Rust command is a manifest
edit, not a rewrite (OpenCode §4, roadmap §1).

## Architecture

```
hostClient.<operation>() ─▶ manifest.ts (operation → transport + cancelable)
                          ├─ SidecarTransport  JSON-RPC/stdio to the Python sidecar (#876)
                          ├─ HttpTransport     the same methods over Django `api/` (remote/mobile)
                          └─ RustTransport     native-only: dialogs, tray, notifications, OS
```

- `SidecarTransport` speaks ndjson framing over an injected channel
  (`{send(line), onLine(cb)}`); the Tauri Rust shell binds real child stdio
  to that seam later. Attach performs the `system.handshake` `{min, max}`
  version negotiation (the UI and sidecar ship as one tested pair, Codex
  R6); in-flight requests are tracked by id, event frames (`channel` key)
  go to `onEvent`.
- `HttpTransport` posts to `{baseUrl}/bridge/<method>`; non-200 responses
  carry the wire error envelope as JSON. `baseUrl`/`fetch` are injectable.
- `RustTransport` passes native ops to an injected Tauri `invoke`. No
  business methods may route here.
- Wire errors decode into `HostClientError` carrying
  `{code, retryable, message_key, details}` — the envelope from
  `contracts/schemas/envelope/error.json`. No tracebacks cross the bridge.

## Manifest edit recipe (retiring a Rust duplicate)

1. Move the operation's row in `manifest.ts` from `rust` to `sidecar` and
   set `method` to the contract name from `contracts/methods.toml`.
2. Run the conformance suite against the new transport:
   `npx vitest run src/hostclient` (TS) and
   `pytest middleware/test/sidecar/` (live Python sidecar).
3. Delete the Rust command body. No call site changes.

## Adapter contract

A `Transport` is `request(method, params): Promise<unknown>` + `close()`.
Errors reject with `HostClientError`. The shared conformance scenarios
(`__tests__/fixtures/conformance.json`) are consumed by both the TS suite
(loopback responder) and the Python suite (live sidecar subprocess) —
extend the fixtures, not per-adapter copies.

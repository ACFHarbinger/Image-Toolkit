# Shared bridge package (W0-11, #875)

Runtime enforcement for the wire contract in `contracts/` (W0-10, #874).
The generated TS/Python/Rust types are typing-only; this package validates
frames at the boundary and owns framing, the version handshake, the error
envelope and cancel semantics. Consumers: #876 (HostClient routes from
`methods.toml` over this transport), #877 (supervisor emits
`bridge.down`/`bridge.ready` through `events.bridge_state_event`), #878
(EventHub's `frontend/src/eventhub/transport.ts` seam receives frames
validated by `events.validate_event`).

## Layout

- `schema.py` — stdlib JSON-Schema subset validator (the keywords the
  contract files use; fails loud on an unknown keyword so a schema that
  outgrows the subset breaks at load time, not silently).
- `catalog.py` — locates `contracts/` (env `IMAGE_TOOLKIT_CONTRACTS_DIR`,
  else walk up from this package), loads `methods.toml` routing and
  validates against the envelope/method/channel schemas.
- `framing.py` — one JSON object per newline over stdio; stdout carries
  only framed protocol messages.
- `envelope.py` — request/response build+decode, `result` XOR `error`,
  `jsonrpc: "2.0"` / `ok: true` const enforcement, the application error
  envelope `{code, retryable, message_key, details}` in the JSON-RPC
  error `data`, and the no-traceback exception mapping.
- `handshake.py` — `system.handshake` / `system.ping` frames, protocol
  constants, compatibility-range negotiation.
- `cancel.py` — idempotent `jobs.cancel`: cooperative tokens, escalation
  hook after the grace period, terminal jobs are a no-op, unknown jobs
  fail with `jobs.not_found`.
- `events.py` — event frames: build + full schema validation (the hub's
  TS guard is minimal by design), `bridge_state_event`, `job_event`.

## Wire semantics

- Frames are newline-delimited JSON objects (`framing.encode_frame`).
- Response is exactly one of `result` / `error` (schema `oneOf`).
- App errors ride `error.data` as `{code, retryable, message_key,
  details}`; `message_key` is the user-facing lookup key in both shells.
- Bridge error codes are part of the contract: add, never rename. The
  registry lives in `envelope.py`'s docstring.
- Inline enums (`kind`, bridge `state`) and consts are enforced here even
  though the generated Python/Rust degrade them to `str`/`String`.

## Tests

`middleware/test/bridge/` — targeted only (RESOURCE RULE). The
jsonschema cross-check tests are `importorskip`-guarded like
`contracts/test`, since jsonschema is a transitive, not declared,
dependency.

# Python sidecar (W0-12, #876)

`python -m middleware.src.sidecar --data-dir DIR` serves the bridge contract
over newline-delimited JSON-RPC on stdio.

- stdout carries only framed protocol messages (`middleware.src.bridge.framing`).
- stderr carries redacted diagnostics only; tracebacks never cross the wire.
- `system.handshake` is required before any other command. It enforces the
  `image-toolkit-bridge` protocol name and the compatibility range from
  `middleware.src.bridge.handshake`.
- Dispatch is routed by `bridge.catalog()` from `contracts/methods.toml`; no
  second routing table or JSON-RPC envelope lives here.
- The W0-12 jobs capability is an in-memory registry used for conformance.
  Feature services replace the executor behind the same contract in later
  waves.
- Module import and startup do not import Torch or other ML stacks. Heavy
  service imports belong behind future capability dispatchers.

Supervisor integration: `middleware.src.supervisor.children.sidecar_argv()`
builds the explicit-runtime command #877 uses when `Supervisor` is created
with `use_real_sidecar=True`. The heartbeat file remains
`<data-dir>/supervisor/sidecar.heartbeat`.

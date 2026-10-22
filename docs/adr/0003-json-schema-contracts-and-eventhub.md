# ADR-0003: JSON Schema Contract Spine, Error/Cancel Envelopes, and Generated EventHub

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#874](https://github.com/ACFHarbinger/Image-Toolkit/issues/874), [#875](https://github.com/ACFHarbinger/Image-Toolkit/issues/875), [#878](https://github.com/ACFHarbinger/Image-Toolkit/issues/878)

## Context

Hand-maintained request/response types across TypeScript, Python, and Rust drift easily, and raw Python tracebacks or ad-hoc event payloads make error handling and state recovery brittle across process restarts.

## Decision

1. **Single source of truth in `contracts/` (#874):** Every capability defines a JSON Schema under `contracts/schemas/capability/` and routing entries in `contracts/methods.toml`. `python contracts/generate.py` generates TypeScript, Python, and Rust bindings plus `contracts/CONTRACTS.sha256` (`--check` enforced in CI).
2. **Structured error envelope (#875):** All bridge errors return `{code, retryable, message_key, details}` mapped from `middleware/src/errors/`. Raw Python tracebacks never reach the webview.
3. **Unified cooperative cancellation (#875):** Cancellation uses a single idempotent `job.cancel` method with a cooperative cancellation token and bounded escalation.
4. **Generated EventHub with sequence catch-up (#878):** EventHub intents and facts are generated from contracts. Each channel maintains a state snapshot plus a bounded event tail with monotonically increasing sequence numbers; any sequence gap triggers an automatic resnapshot. Durable jobs replay from `job_events` / `events.jsonl`. `frontend/src/store/appStore.ts` holds only ephemeral UI state.

## Consequences

- Schema changes require running `python contracts/generate.py` and updating the corresponding module README contract hash.
- UI components recover cleanly from missed events or sidecar restarts without bespoke polling loops.

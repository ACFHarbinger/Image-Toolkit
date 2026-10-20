# Bridge contracts

Source of truth for the types that cross the Tauri ↔ Python bridge
(W0-10, #874; Kimi Q1 answer: JSON Schema per capability, revisit after
the Convert pilot). Nothing here is hand-written twice: the schemas in
this directory generate the TypeScript, Python and Rust types, and
`CONTRACTS.sha256` + CI make drift impossible.

## Layout

```
contracts/
├── methods.toml                     # method-routing table + event channels
├── schemas/
│   ├── envelope/                    # wire framing: request/response/error/event
│   └── capability/                  # one JSON Schema file per capability
├── generate.py                      # stdlib-only codegen; `python generate.py [--check]`
├── generated/
│   ├── ts/                          # imported by the webview / EventHub (#878)
│   ├── python/contracts_generated.py  # imported by middleware services
│   └── rust/contracts.rs            # wired into src-tauri by #876
├── CONTRACTS.sha256                 # per-source hashes + total (generated)
└── test/                            # structural tests (stdlib) + jsonschema deep checks
```

## Wire semantics

- **Framing** is JSON-RPC 2.0 over stdio (roadmap "Bridge"): `request.json`
  and `response.json`. A response carries exactly one of `result` or
  `error`; the JSON-RPC error object's `data` field holds the
  **application error envelope** (`error.json`):
  `{code, retryable, message_key, details}`. `code`/`message_key` are
  dotted lowercase keys mapped onto `middleware/src/errors/`; the webview
  never receives tracebacks.
- **Events** (`event.json`) carry `channel`, `seq` (≥ 1, per channel),
  `kind` (`intent` | `fact`), `durable`, `ts` and a `payload` validated
  against the channel's schema in `methods.toml`. Per Kimi Q3 (answered):
  each channel keeps a snapshot plus a bounded tail; a sequence gap
  triggers a resnapshot; durable-job events replay from persisted
  `job_events` / `events.jsonl`. Non-durable events are dropped from the
  tail.
- **Cancel**: `jobs.cancel` is idempotent (safe to retry, safe on a
  terminal job) with cooperative token + escalation inside the service.

## Method-routing table

`methods.toml` is the one place that says which methods exist, which
schemas their `params`/`result` obey, which channels a method emits,
its error codes and its stability. Schema refs are `"<stem>.<Title>"`:
`stem` is the unique schema file stem under `schemas/`, `Title` a root
or `$defs` title. OpenCode's `HostClient` (#876) routes from this table,
so retiring a duplicate Rust command becomes a routing edit, not a
rewrite.

## Adding a capability

1. Add `schemas/capability/<stem>.json` (draft 2020-12, root `title` =
   `<Stem>Capability`, `$id = "capability/<stem>.json"`). Give every
   object a `$defs` entry with a `title`; the generator refuses anonymous
   inline objects. Cross-file refs: relative paths (`"../envelope/error.json"`).
2. Add `[[method]]` / `[[channel]]` rows to `methods.toml`. Method names
   are `<capability>.<verb>` and must match the `capability` column.
3. Run `python contracts/generate.py` and commit the regenerated
   `generated/` + `CONTRACTS.sha256` together with the schema change.
4. CI (`contracts/generate.py --check` in the lint job, plus
   `pytest contracts/test`) fails on drift.

## Versioning

`methods.toml` rows carry `stability` (`experimental` | `stable`). The
UI and sidecar ship as one tested version pair confirmed by
`system.handshake` (Codex R6); remote clients negotiate within the
handshake's `compatibility` range. Error codes are part of the contract:
add, never rename.

## Known generation degradations (typing-only)

- `const` fields emit `Literal[...]` in TS/Python; Rust degrades to the
  scalar type with a `must be` doc note — the framing layer (#875)
  enforces exact values.
- Inline (anonymous) `enum`s degrade to `string` / `str` / `String`;
  titled `$defs` enums generate real enums/unions. Prefer `$defs`.
- JSON unions of scalars (e.g. JSON-RPC `id`) degrade to
  `serde_json::Value` in Rust.

Generated types are typing-only. Runtime envelope validation is the
bridge package's job (#875); these files carry no validators.

## Consumers

| Issue | Owner | Consumes |
|---|---|---|
| #875 | Mistral | envelopes, `system.handshake` framing, error envelope |
| #876 | OpenCode | `methods.toml` routing, TS/Python/Rust types |
| #878 | Mistral | event envelope, `jobs`/`bridge` channels (snapshot+tail) |
| Gate D (#847–#852) | Cursor | `jobs.*` methods and channel for the Cloud Jobs window |
| Convert pilot (#894) | Kimi | adds the `convert` capability as the walkthrough case |

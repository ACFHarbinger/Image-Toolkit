# EventHub (#878, W0-14)

The webview's in-app event bus. Sidecar and daemons emit intents/facts on
versioned channels; views subscribe to snapshot-shaped channel state. Per
the locked decisions (Kimi Q3, Cursor W2): each channel keeps a snapshot
plus a bounded tail with per-channel sequence numbers; a sequence gap
triggers a resnapshot; durable-job events replay from persisted
`job_events` / `events.jsonl`; `appStore.ts` keeps only ephemeral UI
state — components read domain state through `useChannelState`.

## Layout

- `generated/channels.ts` — GENERATED from `contracts/methods.toml`
  `[[channel]]` rows by `contracts/generate.py` (CI freshness-checked).
  Channel names, payload/snapshot bindings, durable defaults.
- `envelope.ts` — runtime guard for wire frames (shape + values the hub
  relies on). Full JSON-Schema event validation is #875's job.
- `buffer.ts` — pure per-channel buffer: in-order apply, stale drop,
  bounded durable tail, catch-up queue, snapshot install + replay.
- `reducers.ts` — pure per-channel folds from event to snapshot state.
- `hub.ts` — `EventHub`: ingest, subscriptions, resnapshot orchestration
  (with a livelock guard for providers that stop advancing).
- `transport.ts` — the seam for #875's transport: decoded frames in, no
  RPC envelope here.
- `react.ts` — `useChannelState` binding.

## Catch-up contract

A subscriber with no state triggers a provider resnapshot. Events keep
arriving while it is in flight; they queue (bounded) instead of folding
onto pre-gap state, then replay in order on install. Events the snapshot
already covers are dropped; a second hole re-triggers the resnapshot. The
`SnapshotProvider` for `jobs` is `jobs.list` over the bridge client
(wired by #876); tests use fakes.

## Tests

`__tests__/` (vitest). `fixtures.test.ts` consumes the shared
schema-validated frames in `contracts/test/fixtures/events/` (validated
in CI by `contracts/test`), so the TS reducer/buffer tests run against
contract fixtures, not hand-copied copies.

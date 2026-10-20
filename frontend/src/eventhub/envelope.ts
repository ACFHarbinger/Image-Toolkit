// EventHub runtime envelope guard (#878).
//
// Typing-only contract types come from contracts/generated/ts; this guard is
// the hub's first line of defense for frames arriving off the wire. It checks
// shape and value constraints the hub relies on (known channel, integer
// seq >= 1, kind enum, object payload). Full JSON-Schema validation of every
// event is the bridge package's job (#875) — the envelope schema is
// contracts/schemas/envelope/event.json.

import type { BridgeEvent } from "../../../contracts/generated/ts/event";

export const EVENT_CHANNEL_PATTERN = /^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$/;

export type GuardResult =
  | { readonly ok: true; readonly event: BridgeEvent }
  | { readonly ok: false; readonly reason: string };

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function guardEvent(frame: unknown, knownChannels: ReadonlySet<string>): GuardResult {
  if (!isPlainObject(frame)) {
    return { ok: false, reason: "event frame is not an object" };
  }
  const { channel, seq, kind, durable, ts, payload } = frame;
  if (typeof channel !== "string" || !EVENT_CHANNEL_PATTERN.test(channel)) {
    return { ok: false, reason: `channel ${JSON.stringify(channel)} is not a dotted lowercase name` };
  }
  if (!knownChannels.has(channel)) {
    return { ok: false, reason: `unknown channel ${JSON.stringify(channel)}` };
  }
  if (typeof seq !== "number" || !Number.isInteger(seq) || seq < 1) {
    return { ok: false, reason: `seq must be an integer >= 1, got ${JSON.stringify(seq)}` };
  }
  if (kind !== "intent" && kind !== "fact") {
    return { ok: false, reason: `kind must be "intent" | "fact", got ${JSON.stringify(kind)}` };
  }
  if (typeof durable !== "boolean") {
    return { ok: false, reason: `durable must be a boolean, got ${JSON.stringify(durable)}` };
  }
  if (typeof ts !== "string") {
    return { ok: false, reason: `ts must be a string, got ${JSON.stringify(ts)}` };
  }
  if (!isPlainObject(payload)) {
    return { ok: false, reason: "payload must be an object" };
  }
  return { ok: true, event: frame as unknown as BridgeEvent };
}

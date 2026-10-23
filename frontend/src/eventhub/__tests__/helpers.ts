import { describe, expect, it } from "vitest";
import type { BridgeEvent } from "../../../../contracts/generated/ts/event";

export function makeEvent(
  channel: string,
  seq: number,
  overrides: Partial<BridgeEvent> = {},
): BridgeEvent {
  return {
    channel,
    seq,
    kind: "fact",
    durable: true,
    ts: "2026-10-20T12:00:00Z",
    payload: { job_id: "job-1", state: "running" },
    ...overrides,
  } as BridgeEvent;
}

export function jobEvent(seq: number, jobId: string, state: string, extra: object = {}): BridgeEvent {
  return makeEvent("jobs", seq, { payload: { job_id: jobId, state, ...extra } });
}

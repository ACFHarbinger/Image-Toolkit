import { describe, expect, it } from "vitest";
import jobsFixture from "../../../../contracts/test/fixtures/events/jobs.json";
import bridgeFixture from "../../../../contracts/test/fixtures/events/bridge.json";
import type { BridgeEvent } from "../../../../contracts/generated/ts/event";
import { EventHub, type ChannelSnapshot, type SnapshotProvider } from "../hub";
import type { ChannelName } from "../generated/channels";

class StaticProvider implements SnapshotProvider {
  constructor(private readonly shots: Partial<Record<ChannelName, ChannelSnapshot>>) {}
  fetch(channel: ChannelName): Promise<ChannelSnapshot> {
    return Promise.resolve(this.shots[channel] ?? { seq: 0, snapshot: channel === "jobs" ? { jobs: [] } : { state: "down" } });
  }
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("contract event fixtures", () => {
  it("fold the jobs fixture into snapshot state with insertion order", async () => {
    const hub = new EventHub({ provider: new StaticProvider({}) });
    for (const frame of jobsFixture.events as BridgeEvent[]) {
      const result = hub.ingest(frame);
      expect(result.ok).toBe(true);
    }
    const state = hub.getState("jobs");
    expect(state?.jobs.map((j) => j.job_id)).toEqual(["job-100", "job-101"]);
    expect(state?.jobs[0].state).toBe("completed");
    expect(state?.jobs[0].progress).toEqual({ done: 10, total: 42 });
    expect(state?.jobs[1].state).toBe("cancelling");
    expect(hub.lastSeq("jobs")).toBe(jobsFixture.events.length);
    // every fixture event is durable: all six stay in the bounded tail
    expect(hub.getTail("jobs").map((e) => e.seq)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it("folds the bridge fixture while keeping its non-durable tail empty", async () => {
    const hub = new EventHub({ provider: new StaticProvider({}) });
    for (const frame of bridgeFixture.events as BridgeEvent[]) {
      expect(hub.ingest(frame).ok).toBe(true);
    }
    expect(hub.getState("bridge")).toEqual({ state: "ready" });
    expect(hub.getTail("bridge")).toEqual([]);
    expect(hub.lastSeq("bridge")).toBe(3);
  });

  it("replays both fixtures through the catch-up path after a late join", async () => {
    // The provider's snapshot covers only the first two jobs events; the
    // rest arrive as queued tail events and replay on install.
    const provider = new StaticProvider({
      jobs: { seq: 2, snapshot: { jobs: [{ job_id: "job-100", kind: "convert", state: "running" }] } },
    });
    const hub = new EventHub({ provider });
    const seen: string[][] = [];
    hub.subscribe("jobs", (state) => seen.push(state.jobs.map((j) => j.job_id)));
    for (const frame of jobsFixture.events.slice(2) as BridgeEvent[]) {
      hub.ingest(frame);
    }
    await flush();
    expect(hub.isCatchingUp("jobs")).toBe(false);
    expect(hub.lastSeq("jobs")).toBe(6);
    const state = hub.getState("jobs");
    expect(state?.jobs.map((j) => j.job_id)).toEqual(["job-100", "job-101"]);
    // The snapshot carried the authoritative kind; the reducer preserved it.
    expect(state?.jobs[0].kind).toBe("convert");
    expect(seen.at(-1)).toEqual(["job-100", "job-101"]);
  });
});

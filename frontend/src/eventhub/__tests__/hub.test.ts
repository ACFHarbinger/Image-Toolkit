import { describe, expect, it } from "vitest";
import { EventHub, type ChannelSnapshot, type SnapshotProvider } from "../hub";
import type { ChannelName } from "../generated/channels";
import { makeEvent } from "./helpers";

class FakeProvider implements SnapshotProvider {
  calls: ChannelName[] = [];
  failures = 0;
  fallback: ChannelSnapshot = { seq: 0, snapshot: { jobs: [] } };
  constructor(
    private readonly shots: Partial<Record<ChannelName, ChannelSnapshot | (() => ChannelSnapshot)>> = {},
  ) {}

  fetch(channel: ChannelName): Promise<ChannelSnapshot> {
    this.calls.push(channel);
    if (this.failures > 0) {
      this.failures -= 1;
      return Promise.reject(new Error("provider down"));
    }
    const shot = this.shots[channel] ?? this.fallback;
    return Promise.resolve(typeof shot === "function" ? shot() : shot);
  }
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

function jobFrame(seq: number, jobId = `j${seq}`) {
  return makeEvent("jobs", seq, { payload: { job_id: jobId, state: "running" } });
}

describe("EventHub", () => {
  it("ingests valid frames and folds channel state", () => {
    const hub = new EventHub({ provider: new FakeProvider({}) });
    const first = hub.ingest(jobFrame(1));
    const second = hub.ingest(jobFrame(2));
    expect(first).toMatchObject({ ok: true, channel: "jobs", outcome: { status: "appended" } });
    expect(second.outcome).toMatchObject({ status: "appended" });
    expect(hub.getState("jobs")?.jobs.map((j) => j.job_id)).toEqual(["j1", "j2"]);
    expect(hub.lastSeq("jobs")).toBe(2);
  });

  it("rejects malformed frames with a reason and touches no channel", () => {
    const hub = new EventHub({ provider: new FakeProvider({}) });
    const bad = hub.ingest({ channel: "jobs", seq: 0, kind: "fact", durable: true, ts: "t", payload: {} });
    expect(bad.ok).toBe(false);
    expect(bad.reason).toMatch(/seq/);
    expect(hub.getState("jobs")).toBeUndefined();
  });

  it("notifies subscribers on every applied event, not on stale ones", async () => {
    const hub = new EventHub({ provider: new FakeProvider({}) });
    hub.ingest(jobFrame(1));
    hub.ingest(jobFrame(2));
    const seen: string[][] = [];
    hub.subscribe("jobs", (state) => seen.push(state.jobs.map((j) => j.job_id)));
    hub.ingest(jobFrame(2)); // stale duplicate: no notification
    hub.ingest(jobFrame(3));
    await flush();
    expect(seen).toEqual([["j1", "j2"], ["j1", "j2", "j3"]]);
  });

  it("late-joining subscriber triggers a resnapshot and receives the install", async () => {
    const provider = new FakeProvider({
      jobs: { seq: 9, snapshot: { jobs: [{ job_id: "from-snap", kind: "sync", state: "running" }] } },
    });
    const hub = new EventHub({ provider });
    const seen: string[][] = [];
    hub.subscribe("jobs", (state) => seen.push(state.jobs.map((j) => j.job_id)));
    expect(provider.calls).toEqual(["jobs"]);
    await flush();
    expect(seen).toEqual([["from-snap"]]);
    expect(hub.lastSeq("jobs")).toBe(9);
    expect(hub.ingest(jobFrame(9)).outcome).toMatchObject({ status: "stale" });
    expect(hub.ingest(jobFrame(10)).outcome).toMatchObject({ status: "appended" });
  });

  it("resnapshots on a sequence gap and replays queued events in order", async () => {
    // First fetch sees events 1-3; the re-fetch after the replay hole sees
    // the service caught up through 5.
    let fetchCount = 0;
    const provider = new FakeProvider({
      jobs: () => {
        fetchCount += 1;
        return fetchCount === 1
          ? {
              seq: 3,
              snapshot: {
                jobs: [
                  { job_id: "j1", kind: "k", state: "running" },
                  { job_id: "j2", kind: "k", state: "completed" },
                  { job_id: "j3", kind: "k", state: "completed" },
                ],
              },
            }
          : {
              seq: 5,
              snapshot: {
                jobs: [
                  { job_id: "j1", kind: "k", state: "running" },
                  { job_id: "j2", kind: "k", state: "completed" },
                  { job_id: "j3", kind: "k", state: "completed" },
                  { job_id: "j4", kind: "k", state: "running" },
                  { job_id: "j5", kind: "k", state: "running" },
                ],
              },
            };
      },
    });
    const gaps: Array<{ expected: number; got: number }> = [];
    const hub = new EventHub({ provider, onGap: (_c, info) => gaps.push(info) });
    hub.ingest(jobFrame(1));
    const seen: string[][] = [];
    hub.subscribe("jobs", (state) => seen.push(state.jobs.map((j) => j.job_id)));

    hub.ingest(jobFrame(4));
    hub.ingest(jobFrame(5));
    expect(hub.isCatchingUp("jobs")).toBe(true);
    expect(gaps).toEqual([{ expected: 2, got: 4 }]);
    await flush();

    expect(hub.isCatchingUp("jobs")).toBe(false);
    expect(hub.lastSeq("jobs")).toBe(5);
    expect(hub.getState("jobs")?.jobs.map((j) => j.job_id)).toEqual(["j1", "j2", "j3", "j4", "j5"]);
    expect(seen.at(-1)).toEqual(["j1", "j2", "j3", "j4", "j5"]);
    expect(gaps).toEqual([{ expected: 2, got: 4 }]);
  });

  it("gives up on a provider whose snapshot never advances", async () => {
    const provider = new FakeProvider({
      jobs: { seq: 1, snapshot: { jobs: [{ job_id: "j1", kind: "k", state: "running" }] } },
    });
    const errors: unknown[] = [];
    const hub = new EventHub({ provider, onProviderError: (_c, e) => errors.push(e) });
    hub.ingest(jobFrame(1));
    hub.ingest(jobFrame(4)); // gap; retain it for replay
    hub.ingest(jobFrame(5)); // queued; the snapshot can never cover it
    await flush();
    expect(hub.isCatchingUp("jobs")).toBe(true);
    expect(hub.lastSeq("jobs")).toBe(1);
    expect(String(errors[0])).toMatch(/did not advance/);
  });

  it("reports provider failures through onProviderError and keeps catching up", async () => {
    const provider = new FakeProvider();
    provider.failures = 1;
    const errors: unknown[] = [];
    const hub = new EventHub({ provider, onProviderError: (_c, e) => errors.push(e) });
    hub.ingest(jobFrame(1));
    hub.ingest(jobFrame(3)); // gap -> auto resnapshot -> provider fails
    await flush();
    expect(errors).toHaveLength(1);
    expect(hub.isCatchingUp("jobs")).toBe(true);
    expect(hub.lastSeq("jobs")).toBe(1);
    // Once the provider recovers with a fresh snapshot, the queued event folds.
    provider.fallback = {
      seq: 3,
      snapshot: {
        jobs: [
          { job_id: "j1", kind: "k", state: "completed" },
          { job_id: "j2", kind: "k", state: "completed" },
          { job_id: "j3", kind: "k", state: "running" },
        ],
      },
    };
    expect(await hub.resnapshot("jobs")).toBe(true);
    expect(hub.lastSeq("jobs")).toBe(3);
    expect(hub.getState("jobs")?.jobs.map((j) => j.job_id)).toEqual(["j1", "j2", "j3"]);
  });

  it("keeps the durable tail bounded and per channel", () => {
    const hub = new EventHub({ provider: new FakeProvider({}), tailMax: 2 });
    for (let seq = 1; seq <= 4; seq += 1) {
      hub.ingest(jobFrame(seq));
    }
    expect(hub.getTail("jobs").map((e) => e.seq)).toEqual([3, 4]);
    expect(hub.getTail("bridge")).toEqual([]);
  });

  it("unsubscribes cleanly", async () => {
    const hub = new EventHub({ provider: new FakeProvider({}) });
    const seen: number[] = [];
    const unsubscribe = hub.subscribe("jobs", (state) => seen.push(state.jobs.length));
    hub.ingest(jobFrame(1));
    await flush();
    expect(seen).toEqual([1]); // late-join snapshot delivered
    unsubscribe();
    hub.ingest(jobFrame(2));
    await flush();
    expect(seen).toEqual([1]); // no further notifications
  });
});

describe("review recovery regressions", () => {
  it("replays the event that first exposed a gap", async () => {
    const provider = new FakeProvider({ jobs: { seq: 2, snapshot: { jobs: [] } } });
    const hub = new EventHub({ provider });
    hub.ingest(jobFrame(1));
    hub.ingest(jobFrame(3));
    await flush();
    expect(hub.lastSeq("jobs")).toBe(3);
    expect(hub.getState("jobs")?.jobs.map((j) => j.job_id)).toEqual(["j3"]);
  });

  it("retries a failed snapshot when another event arrives", async () => {
    let count = 0;
    const provider = new FakeProvider({ jobs: () => {
      count += 1;
      if (count === 1) throw new Error("offline");
      return { seq: 2, snapshot: { jobs: [] } };
    } });
    const hub = new EventHub({ provider });
    hub.ingest(jobFrame(1));
    hub.ingest(jobFrame(3));
    await flush();
    hub.ingest(jobFrame(4));
    await flush();
    expect(hub.lastSeq("jobs")).toBe(4);
    expect(hub.isCatchingUp("jobs")).toBe(false);
  });

  it("does not replace newer state with a stale snapshot", async () => {
    const hub = new EventHub({ provider: new FakeProvider({ jobs: { seq: 0, snapshot: { jobs: [] } } }) });
    hub.ingest(jobFrame(1));
    expect(await hub.resnapshot("jobs")).toBe(false);
    expect(hub.lastSeq("jobs")).toBe(1);
  });
});

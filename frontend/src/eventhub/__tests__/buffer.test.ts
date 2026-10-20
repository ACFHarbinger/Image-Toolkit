import { describe, expect, it } from "vitest";
import { ChannelBuffer } from "../buffer";
import type { BridgeEvent } from "../../../../contracts/generated/ts/event";
import type { JobListSnapshot } from "../../../../contracts/generated/ts/jobs";
import { jobsReducer } from "../reducers";
import { makeEvent } from "./helpers";

function buffer(tailMax = 3, pendingMax = 4) {
  return new ChannelBuffer<JobListSnapshot>({ tailMax, pendingMax, reducer: jobsReducer });
}

function ev(seq: number, durable = true): BridgeEvent {
  return makeEvent("jobs", seq, { durable, payload: { job_id: `j${seq}`, state: "running" } });
}

describe("ChannelBuffer", () => {
  it("applies gapless events in order and tracks lastSeq", () => {
    const b = buffer();
    expect(b.append(ev(1)).status).toBe("appended");
    expect(b.append(ev(2)).status).toBe("appended");
    expect(b.lastSeq).toBe(2);
    expect(b.state?.jobs.map((j) => j.job_id)).toEqual(["j1", "j2"]);
  });

  it("flags a gap when an event arrives out of order", () => {
    const b = buffer();
    b.append(ev(1));
    expect(b.append(ev(3))).toEqual({ status: "gap", expected: 2, got: 3 });
  });

  it("treats late events as stale without applying them", () => {
    const b = buffer();
    b.append(ev(1));
    b.append(ev(2));
    const before = b.state;
    expect(b.append(ev(2)).status).toBe("stale");
    expect(b.append(ev(1)).status).toBe("stale");
    expect(b.state).toBe(before);
    expect(b.lastSeq).toBe(2);
  });

  it("detects a gap on the very first event when joining mid-stream", () => {
    const b = buffer();
    expect(b.append(ev(5))).toEqual({ status: "gap", expected: 1, got: 5 });
  });

  it("queues events during catch-up and replays them after a snapshot install", () => {
    const b = buffer();
    b.append(ev(1));
    b.append(ev(2));
    b.beginCatchUp();
    expect(b.append(ev(3)).status).toBe("queued");
    expect(b.append(ev(4)).status).toBe("queued");
    expect(b.catchingUp).toBe(true);

    const result = b.installSnapshot(2, { jobs: [{ job_id: "j1", kind: "k", state: "running" }] });
    expect(result.replayed).toBe(2);
    expect(result.gapAt).toBeUndefined();
    expect(b.catchingUp).toBe(false);
    expect(b.lastSeq).toBe(4);
    expect(b.state?.jobs.map((j) => j.job_id)).toEqual(["j1", "j3", "j4"]);
  });

  it("drops queued events the snapshot already covers", () => {
    const b = buffer();
    b.beginCatchUp();
    b.append(ev(1));
    b.append(ev(2));
    b.append(ev(3));
    const result = b.installSnapshot(2, { jobs: [] });
    expect(result.replayed).toBe(1);
    expect(b.lastSeq).toBe(3);
  });

  it("re-enters catch-up when the queue hides another hole", () => {
    const b = buffer();
    b.beginCatchUp();
    b.append(ev(1));
    b.append(ev(2));
    b.append(ev(5));
    const result = b.installSnapshot(0, { jobs: [] });
    expect(result.replayed).toBe(2);
    expect(result.gapAt).toEqual({ expected: 3, got: 5 });
    expect(b.catchingUp).toBe(true);
    expect(b.lastSeq).toBe(2);
  });

  it("bounds the durable tail and evicts oldest first", () => {
    const b = buffer(3);
    for (let seq = 1; seq <= 5; seq += 1) {
      b.append(ev(seq));
    }
    expect(b.tail().map((e) => e.seq)).toEqual([3, 4, 5]);
  });

  it("keeps non-durable events out of the tail but folds them into state", () => {
    const b = buffer(10);
    b.append(ev(1, false));
    b.append(ev(2));
    b.append(ev(3, false));
    expect(b.tail().map((e) => e.seq)).toEqual([2]);
    expect(b.state?.jobs.map((j) => j.job_id)).toEqual(["j1", "j2", "j3"]);
  });

  it("drops oldest queued events when the pending queue overflows", () => {
    const b = buffer(10, 2);
    b.beginCatchUp();
    b.append(ev(1));
    b.append(ev(2));
    b.append(ev(3));
    const result = b.installSnapshot(0, { jobs: [] });
    expect(result.replayed).toBe(2); // seq 1 evicted, 2 and 3 replay
    expect(b.lastSeq).toBe(3);
  });

  it("clears the tail on snapshot install (the snapshot supersedes it)", () => {
    const b = buffer();
    b.append(ev(1));
    b.append(ev(2));
    expect(b.tail().length).toBe(2);
    b.installSnapshot(5, { jobs: [] });
    expect(b.tail().length).toBe(0);
    expect(b.lastSeq).toBe(5);
    expect(b.append(ev(5)).status).toBe("stale");
    expect(b.append(ev(6)).status).toBe("appended");
  });
});

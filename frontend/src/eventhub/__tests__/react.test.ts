import { afterEach, describe, expect, it } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import { EventHub, type ChannelSnapshot, type SnapshotProvider } from "../hub";
import { useChannelState } from "../react";
import type { ChannelName } from "../generated/channels";
import { makeEvent } from "./helpers";

class StaticProvider implements SnapshotProvider {
  constructor(private readonly shots: Partial<Record<ChannelName, ChannelSnapshot>> = {}) {}
  fetch(channel: ChannelName): Promise<ChannelSnapshot> {
    return Promise.resolve(this.shots[channel] ?? { seq: 0, snapshot: { jobs: [] } });
  }
}

afterEach(cleanup);

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

function jobFrame(seq: number, jobId = `j${seq}`) {
  return makeEvent("jobs", seq, { payload: { job_id: jobId, state: "running" } });
}

describe("useChannelState", () => {
  it("starts undefined, takes the provider snapshot, then follows updates", async () => {
    const hub = new EventHub({ provider: new StaticProvider() });
    const { result } = renderHook(() => useChannelState(hub, "jobs"));
    expect(result.current).toBeUndefined();

    // subscribing with no state triggers a resnapshot; until it lands,
    // events queue in the buffer rather than folding
    await act(async () => {
      hub.ingest(jobFrame(1));
      await flush();
    });
    expect(result.current?.jobs.map((j) => j.job_id)).toEqual(["j1"]);

    act(() => {
      hub.ingest(jobFrame(2));
    });
    expect(result.current?.jobs.map((j) => j.job_id)).toEqual(["j1", "j2"]);
  });

  it("renders the current state immediately for a late joiner", () => {
    const hub = new EventHub({ provider: new StaticProvider() });
    hub.ingest(jobFrame(1));
    const { result } = renderHook(() => useChannelState(hub, "jobs"));
    expect(result.current?.jobs.map((j) => j.job_id)).toEqual(["j1"]);
  });
});

import { describe, expect, it } from "vitest";
import { bridgeReducer, jobsReducer, REDUCERS } from "../reducers";
import { CHANNEL_NAMES } from "../generated/channels";
import { makeEvent } from "./helpers";

describe("jobsReducer", () => {
  it("inserts new jobs in arrival order and upserts in place", () => {
    let state = jobsReducer(undefined, makeEvent("jobs", 1, { payload: { job_id: "a", state: "queued" } }));
    state = jobsReducer(state, makeEvent("jobs", 2, { payload: { job_id: "b", state: "running" } }));
    state = jobsReducer(state, makeEvent("jobs", 3, { payload: { job_id: "a", state: "running" } }));
    expect(state.jobs.map((j) => j.job_id)).toEqual(["a", "b"]);
    expect(state.jobs[0].state).toBe("running");
  });

  it("keeps the previous progress when an event omits it", () => {
    let state = jobsReducer(
      undefined,
      makeEvent("jobs", 1, { payload: { job_id: "a", state: "running", progress: { done: 3, total: 9 } } }),
    );
    state = jobsReducer(state, makeEvent("jobs", 2, { payload: { job_id: "a", state: "completed" } }));
    expect(state.jobs[0].progress).toEqual({ done: 3, total: 9 });
    expect(state.jobs[0].state).toBe("completed");
  });

  it("marks jobs unseen by a snapshot with an unknown kind until one arrives", () => {
    const state = jobsReducer(undefined, makeEvent("jobs", 1, { payload: { job_id: "a", state: "queued" } }));
    expect(state.jobs[0].kind).toBe("unknown");
  });

  it("preserves kind and error already present in the state", () => {
    const initial = { jobs: [{ job_id: "a", kind: "convert", state: "running" as const }] };
    const state = jobsReducer(initial, makeEvent("jobs", 1, { payload: { job_id: "a", state: "failed" } }));
    expect(state.jobs[0].kind).toBe("convert");
    expect(state.jobs[0].state).toBe("failed");
  });

  it("ignores payloads without a string job_id and still returns a state", () => {
    const state = jobsReducer(undefined, makeEvent("jobs", 1, { payload: { state: "running" } }));
    expect(state.jobs).toEqual([]);
  });
});

describe("bridgeReducer", () => {
  it("folds down/ready transitions", () => {
    expect(bridgeReducer(undefined, makeEvent("bridge", 1, { payload: { state: "ready" } }))).toEqual({ state: "ready" });
    expect(bridgeReducer({ state: "ready" }, makeEvent("bridge", 2, { payload: { state: "down" } }))).toEqual({ state: "down" });
  });

  it("falls back to down for malformed payloads on an empty state", () => {
    expect(bridgeReducer(undefined, makeEvent("bridge", 1, { payload: { state: "sideways" } }))).toEqual({ state: "down" });
  });

  it("keeps the previous state for malformed payloads", () => {
    expect(bridgeReducer({ state: "ready" }, makeEvent("bridge", 1, { payload: { state: "sideways" } }))).toEqual({ state: "ready" });
  });
});

describe("REDUCERS", () => {
  it("covers exactly the generated channel names", () => {
    expect(Object.keys(REDUCERS).sort()).toEqual([...CHANNEL_NAMES].sort());
  });
});

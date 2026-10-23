// EventHub channel reducers (#878) — pure folds from an event into the
// channel's snapshot-shaped state. The fold semantics per channel are owned
// here by hand; the channel list, payload/snapshot bindings and durability
// defaults are generated from contracts/methods.toml (see generated/).
//
// Snapshot state is what a late joiner receives; it must always be
// reconstructible from a provider snapshot (jobs.list for `jobs`) plus the
// event tail, which is why reducers only ever derive state from the previous
// state and the current event.

import type { BridgeEvent } from "../../../contracts/generated/ts/event";
import type { JobListSnapshot, JobStatus } from "../../../contracts/generated/ts/jobs";
import type { BridgeStateSnapshot } from "../../../contracts/generated/ts/system";
import type { ChannelName } from "./generated/channels";

export interface ChannelStates {
  readonly jobs: JobListSnapshot;
  readonly bridge: BridgeStateSnapshot;
}

export type ChannelReducer<C extends ChannelName> = (
  state: ChannelStates[C] | undefined,
  event: BridgeEvent,
) => ChannelStates[C];

const UNKNOWN_JOB_KIND = "unknown";

export const jobsReducer: ChannelReducer<"jobs"> = (state, event) => {
  const payload = event.payload as { job_id?: unknown; state?: unknown; progress?: unknown };
  const jobId = typeof payload.job_id === "string" ? payload.job_id : null;
  if (jobId === null) {
    return state ?? { jobs: [] };
  }
  const order: string[] = [];
  const byId = new Map<string, JobStatus>();
  for (const job of state?.jobs ?? []) {
    order.push(job.job_id);
    byId.set(job.job_id, job);
  }
  if (!byId.has(jobId)) {
    order.push(jobId);
  }
  const previous = byId.get(jobId);
  const progress = payload.progress !== undefined ? payload.progress : previous?.progress;
  const kind = previous?.kind ?? UNKNOWN_JOB_KIND;
  byId.set(jobId, {
    job_id: jobId,
    kind,
    state: payload.state as JobStatus["state"],
    ...(progress !== undefined ? { progress: progress as JobStatus["progress"] } : {}),
    ...(previous?.error !== undefined ? { error: previous.error } : {}),
  });
  return { jobs: order.map((id) => byId.get(id)!) };
};

export const bridgeReducer: ChannelReducer<"bridge"> = (state, event) => {
  const payload = event.payload as { state?: unknown };
  if (payload.state !== "down" && payload.state !== "ready") {
    return state ?? { state: "down" };
  }
  return { state: payload.state };
};

export const REDUCERS: { readonly [C in ChannelName]: ChannelReducer<C> } = {
  jobs: jobsReducer,
  bridge: bridgeReducer,
};

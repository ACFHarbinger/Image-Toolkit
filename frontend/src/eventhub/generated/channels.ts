// GENERATED — contract hash 7f853bd58530640761fee9a62783e191b67b9cbc62db9153cfadfc7c15d42687. Do not edit; edit the schema and regenerate.
import type { JobEventPayload, JobListSnapshot } from "../../../../contracts/generated/ts/jobs";
import type { BridgeStatePayload, BridgeStateSnapshot } from "../../../../contracts/generated/ts/system";

export const CHANNEL_NAMES = ["jobs", "bridge"] as const;
export type ChannelName = (typeof CHANNEL_NAMES)[number];

export interface ChannelSpec<P, S> {
  readonly name: ChannelName;
  readonly payloadTitle: string;
  readonly snapshotTitle: string;
  readonly durableDefault: boolean;
  readonly producers: readonly string[];
  readonly consumers: readonly string[];
  readonly notes: string;
}

export interface ChannelRegistry {
  readonly "jobs": ChannelSpec<JobEventPayload, JobListSnapshot>;
  readonly "bridge": ChannelSpec<BridgeStatePayload, BridgeStateSnapshot>;
}

export const CHANNEL_REGISTRY: ChannelRegistry = {
  "jobs": {
    name: "jobs",
    payloadTitle: "JobEventPayload",
    snapshotTitle: "JobListSnapshot",
    durableDefault: true,
    producers: ["sidecar", "cloud-jobs-daemon"],
    consumers: ["webview"],
    notes: "State transitions and progress of durable jobs; replay source is job_events / events.jsonl.",
  },
  "bridge": {
    name: "bridge",
    payloadTitle: "BridgeStatePayload",
    snapshotTitle: "BridgeStateSnapshot",
    durableDefault: false,
    producers: ["supervisor"],
    consumers: ["webview"],
    notes: "Restart contract (roadmap): bridge.down then bridge.ready around sidecar restarts; in-flight session requests fail with the error envelope.",
  },
};

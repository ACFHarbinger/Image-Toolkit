// EventHub (#878) — public surface. See README.md in this directory.

export { ChannelBuffer, DEFAULT_PENDING_MAX, DEFAULT_TAIL_MAX } from "./buffer";
export type { AppendOutcome, InstallResult } from "./buffer";
export { EVENT_CHANNEL_PATTERN, guardEvent } from "./envelope";
export type { GuardResult } from "./envelope";
export { EventHub } from "./hub";
export type { ChannelSnapshot, HubOptions, IngestResult, SnapshotProvider } from "./hub";
export { REDUCERS, bridgeReducer, jobsReducer } from "./reducers";
export type { ChannelReducer, ChannelStates } from "./reducers";
export { attachTransport } from "./transport";
export type { EventTransport } from "./transport";
export { useChannelState } from "./react";
export { CHANNEL_NAMES, CHANNEL_REGISTRY } from "./generated/channels";
export type { ChannelName, ChannelRegistry as ChannelRegistryShape, ChannelSpec } from "./generated/channels";

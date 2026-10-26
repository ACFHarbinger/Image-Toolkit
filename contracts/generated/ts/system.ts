// GENERATED — contract hash cb09b3509952d4f2709405f0468eda7f1d4955df5dba0507d05db47f923732c0. Do not edit; edit the schema and regenerate.

export interface BridgeStatePayload {
  readonly state: "down" | "ready";
}
export interface BridgeStateSnapshot {
  readonly state: "down" | "ready";
}
export interface ClientInfo {
  readonly name: string;
  readonly version: string;
}
export interface Compatibility {
  readonly min: string;
  readonly max: string;
}
export interface HandshakeParams {
  readonly protocol: string;
  readonly client: ClientInfo;
}
export interface HandshakeResult {
  readonly protocol: string;
  readonly version: string;
  readonly compatibility: Compatibility;
  readonly capabilities: Array<string>;
}
export type PingParams = Record<string, unknown>;
export interface PingResult {
  readonly ok: true;
}

// GENERATED — contract hash 9fe77d2de0e32c92dfddbdf87c37a1f78a2aa550494a3394c78ad951fd387f08. Do not edit; edit the schema and regenerate.

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

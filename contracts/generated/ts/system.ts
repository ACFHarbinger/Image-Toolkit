// GENERATED — contract hash bca68aa26aa4dff9163ec317617db41a7cf4b1d5f8198ea7f4b3f952664d3782. Do not edit; edit the schema and regenerate.

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

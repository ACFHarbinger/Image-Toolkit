// GENERATED — contract hash 48a603dc6dcc15a3a230962ec97d6ff121dc28bd5222277e1eb476fb951789d0. Do not edit; edit the schema and regenerate.

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

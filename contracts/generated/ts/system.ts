// GENERATED — contract hash 982b5ee1c894cc7cc385319c615075e261812de38001db245180d72ca8b6e2c7. Do not edit; edit the schema and regenerate.

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

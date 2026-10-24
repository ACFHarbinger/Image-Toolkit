// GENERATED — contract hash 43786106791c039a8287c7b4e4ad317f69a1e4ab0543c78a9ff14b6c8e29e7d2. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

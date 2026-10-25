// GENERATED — contract hash eb57d1d3ee001de50bb35743f515830d8370c51552d7d005103b952116fb1b96. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

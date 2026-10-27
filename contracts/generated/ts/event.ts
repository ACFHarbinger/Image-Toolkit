// GENERATED — contract hash 9de51fd76cff26625db8bc02d1154d1664e095d6d5e14f6349c28a223d5ca512. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

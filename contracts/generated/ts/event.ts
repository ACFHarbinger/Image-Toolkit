// GENERATED — contract hash 0d32f1eb2b24dbf8a6a979c5d8cadb97d33755cf15241cb784241f253c00c55c. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

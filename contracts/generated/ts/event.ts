// GENERATED — contract hash f7decebc58560f91af1448b80d01a55b0df7965df43a1c409469b3ecbb344e67. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

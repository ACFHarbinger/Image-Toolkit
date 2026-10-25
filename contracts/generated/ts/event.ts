// GENERATED — contract hash 02cbf994e4637ef9eaf9b96f7bc8b6258c31d0f77f66e4fec308264c40cddf06. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

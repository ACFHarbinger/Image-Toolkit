// GENERATED — contract hash 6a45b8f32749068100d96710e9ad83f596745d32b6cb9702fc61e1997c228ea4. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

// GENERATED — contract hash 1b786b00c07f6a36997bbfb2c4f7587b3fc5c9afdaf805a1a251a13d3b617e85. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

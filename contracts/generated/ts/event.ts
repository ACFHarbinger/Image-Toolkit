// GENERATED — contract hash a375ee1734bd400623a9aa1b2c07ff89ab62c643d11f99548743568562a87ca9. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

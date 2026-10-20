// GENERATED — contract hash 982b5ee1c894cc7cc385319c615075e261812de38001db245180d72ca8b6e2c7. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

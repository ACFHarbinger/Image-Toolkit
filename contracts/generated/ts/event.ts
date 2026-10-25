// GENERATED — contract hash 121107d6c8af7ea8eaf2408ee5ee09b85b47ac31aafc0a0cccb660d30457f571. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

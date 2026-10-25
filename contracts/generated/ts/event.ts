// GENERATED — contract hash 141e9dd167559991d9c1639884ad1460a97baa9297e5847fbddd7e35315adc12. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

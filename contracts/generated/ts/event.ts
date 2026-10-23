// GENERATED — contract hash 8df3e3c358bb96402c6c835a3701454161463c07b6f8d0517b138016d22ef4a0. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

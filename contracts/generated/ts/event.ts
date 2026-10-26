// GENERATED — contract hash 28918ce8760d36700226684cdf4b39a9465953292b3c3913b49e167c15ce7d55. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

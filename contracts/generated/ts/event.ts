// GENERATED — contract hash 36dcc44c132f5c8c9190f6760f223968be8ca33bdba8f1a7fe546e31a155ba50. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

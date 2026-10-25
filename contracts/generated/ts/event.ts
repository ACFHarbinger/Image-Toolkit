// GENERATED — contract hash e98d26c96ac04681cd010af6b6d27aa2803c65965ba50e9301fa967f227459dd. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

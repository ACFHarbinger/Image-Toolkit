// GENERATED — contract hash 06d78f58ef216bfc151693c8ebd6bb263e26e834d2411a707e2e8bf116219881. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

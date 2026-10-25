// GENERATED — contract hash 0ddf43995ce7387ccdcb17b3e1810f19002528a099b4e8c2a036122b876a07fb. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

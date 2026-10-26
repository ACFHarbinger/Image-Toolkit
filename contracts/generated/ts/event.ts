// GENERATED — contract hash af34b6b15ababc46f3e0add43e55c137e6b0ea67f7546a3fdfe58e02ded46031. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

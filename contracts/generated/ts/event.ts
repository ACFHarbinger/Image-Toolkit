// GENERATED — contract hash 3233ab7fcaaa28c5e93c830b5852f2ef5d5181dba831967ce1073e10c44d75ec. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

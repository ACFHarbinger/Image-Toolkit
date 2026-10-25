// GENERATED — contract hash 6351f82fd45a8c5d6143cf73e3570df6c3d8d70c885f1e2ccfcf5d09f3540f21. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

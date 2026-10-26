// GENERATED — contract hash a06471e200d0ebbad6b544aa116489d517a985e837bd9bf5c797eb5238e2867d. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

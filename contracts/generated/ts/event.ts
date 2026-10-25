// GENERATED — contract hash 08faec06515d9a8705e5ee5589a1933a46e3091792150fb9145b7bdb772a2acb. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

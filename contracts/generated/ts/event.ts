// GENERATED — contract hash 239dc4acbba4111ef20878825587c4d6be98066d75cb0526995ffceaafec9cdb. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

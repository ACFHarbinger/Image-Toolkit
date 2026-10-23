// GENERATED — contract hash 458ae5d7b75d09fd889bc0a4f1c891ad9d5fc73cf5612a38292f3dbc0bcc24f2. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

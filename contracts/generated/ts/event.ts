// GENERATED — contract hash 518f5fa10208b0ed73cfe7fbbea67d2d0baddbad24edd98e22e685e1522561a0. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

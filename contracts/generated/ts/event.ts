// GENERATED — contract hash db2448a4bdeabe1e4ed117d1df96cf7502ed74c7c1b95d27c342ebd8754977e3. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

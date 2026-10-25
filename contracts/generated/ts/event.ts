// GENERATED — contract hash bca68aa26aa4dff9163ec317617db41a7cf4b1d5f8198ea7f4b3f952664d3782. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

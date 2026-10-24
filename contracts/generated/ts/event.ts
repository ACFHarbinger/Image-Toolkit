// GENERATED — contract hash 7886a9fb066af0b1778fca0b4bf80c544815754858676745c46d3f584b33e46c. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

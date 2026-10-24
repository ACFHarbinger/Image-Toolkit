// GENERATED — contract hash 0e53e547598e72b888deb0e0169a3b6505d29f2d941fe41911a7301fd6bcd455. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

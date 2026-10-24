// GENERATED — contract hash d3ad88d256890708aae55f71b8555461f5137da710beb8f83ced0deb22ae992f. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

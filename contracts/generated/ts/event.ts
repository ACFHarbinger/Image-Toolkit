// GENERATED — contract hash e3ece40abeda17e5df8d079ddeb991acf09d8b6d21b5da6663083a66186f821d. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

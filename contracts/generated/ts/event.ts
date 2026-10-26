// GENERATED — contract hash d4c2f9f05e94f415f5a6aecc1d7684c3dcd8e9bd27a3076fe28a1c5cfdf5a174. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

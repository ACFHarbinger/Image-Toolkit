// GENERATED — contract hash 1b61179c45bf104ff11ace0dc1d0236da1e1e7b9c540fb808333f24757910a89. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

// GENERATED — contract hash c30cf0dd6674a685340ce15641f019f568d5adba75e10d53baca8364f72fe25d. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

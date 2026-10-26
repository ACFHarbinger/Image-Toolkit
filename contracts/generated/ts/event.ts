// GENERATED — contract hash c9b6edf9c60311bf50a4e7d58a6a25d9164f0ceda3a71af6ec8de11344e19fe8. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

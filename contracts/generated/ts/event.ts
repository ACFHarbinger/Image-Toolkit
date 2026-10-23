// GENERATED — contract hash 48a603dc6dcc15a3a230962ec97d6ff121dc28bd5222277e1eb476fb951789d0. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

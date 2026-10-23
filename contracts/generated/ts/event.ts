// GENERATED — contract hash 5a4561cc935e5e7098bbb70e673dbe80fcc9da00470d369b67b897593f256ffe. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

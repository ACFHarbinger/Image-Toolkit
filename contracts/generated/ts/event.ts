// GENERATED — contract hash fd24c10a6c68f14e14dab5faa90a7731cd8aaa7a57489826f7c8836964930567. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

// GENERATED — contract hash ec6a61092d909f9e2161d5089fa6ebc740ab2ce342d29bb779e41de84a587bdc. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

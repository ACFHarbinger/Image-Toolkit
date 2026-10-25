// GENERATED — contract hash d631902fe126f39d94dc625e1c8688455abc25cc6d7b3c704ab441fd31d985ea. Do not edit; edit the schema and regenerate.

export interface BridgeEvent {
  readonly channel: string;
  readonly seq: number;
  readonly kind: "intent" | "fact";
  readonly durable: boolean;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

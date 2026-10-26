// GENERATED — contract hash 8f3b63259aeee332f0b0ef1780647fdc1e5692c6d3e1a1d6b8b0aeb24360f303. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

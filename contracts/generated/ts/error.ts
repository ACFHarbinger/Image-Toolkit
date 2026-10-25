// GENERATED — contract hash 9a0cc13149be2f4357ee006a22bcdf31bed4796f55b7e30240cfb3eda4b5e150. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

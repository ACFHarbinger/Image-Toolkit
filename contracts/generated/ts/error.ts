// GENERATED — contract hash 1b786b00c07f6a36997bbfb2c4f7587b3fc5c9afdaf805a1a251a13d3b617e85. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

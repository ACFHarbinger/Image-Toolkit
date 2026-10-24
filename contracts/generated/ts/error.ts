// GENERATED — contract hash 0e53e547598e72b888deb0e0169a3b6505d29f2d941fe41911a7301fd6bcd455. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

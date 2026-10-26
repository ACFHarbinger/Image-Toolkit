// GENERATED — contract hash 9fe77d2de0e32c92dfddbdf87c37a1f78a2aa550494a3394c78ad951fd387f08. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

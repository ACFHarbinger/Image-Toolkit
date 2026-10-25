// GENERATED — contract hash 866790a842dad1e8e0cd5ce44c24e77c53142f7ea0cb3e3db9476deb9b92c43a. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

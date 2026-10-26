// GENERATED — contract hash 1b081c15dfb3252eeb7f0209c44d8f0e6d1689dc3d7a36162b2e9c360c9d65cd. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

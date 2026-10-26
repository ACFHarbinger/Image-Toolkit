// GENERATED — contract hash 184e19fe7526c6a9f25ef4689e2df0cc7a2b4ad9cf77a0fbf5460be658376f83. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

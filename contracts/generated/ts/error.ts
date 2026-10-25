// GENERATED — contract hash 6ccbd3c8689db93cd2433f03ff38f9704d5ff9ff0c055064c5e69501e7aeb5f1. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

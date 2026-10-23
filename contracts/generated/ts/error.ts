// GENERATED — contract hash 458ae5d7b75d09fd889bc0a4f1c891ad9d5fc73cf5612a38292f3dbc0bcc24f2. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

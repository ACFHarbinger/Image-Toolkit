// GENERATED — contract hash 3233ab7fcaaa28c5e93c830b5852f2ef5d5181dba831967ce1073e10c44d75ec. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

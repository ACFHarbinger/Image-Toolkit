// GENERATED — contract hash 9c3ee12cc3be627bb53d8e6b3f564849a135edb081df72e2492a9981a5782385. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

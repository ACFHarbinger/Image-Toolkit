// GENERATED — contract hash fd24c10a6c68f14e14dab5faa90a7731cd8aaa7a57489826f7c8836964930567. Do not edit; edit the schema and regenerate.

export interface BridgeError {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;
}

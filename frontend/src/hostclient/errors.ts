// HostClientError: the decoded wire error envelope (W0-12, #876).
//
// Every transport adapter decodes the bridge error envelope
// `{code, retryable, message_key, details}` (contracts/schemas/envelope/
// error.json) into this one error type. `message_key` is the user-facing
// lookup key; no traceback ever crosses the bridge (#875).

import type { BridgeError } from "./types";

export class HostClientError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly message_key: string;
  readonly details?: Record<string, unknown>;

  constructor(envelope: BridgeError) {
    super(`${envelope.code} (${envelope.message_key})`);
    this.name = "HostClientError";
    this.code = envelope.code;
    this.retryable = envelope.retryable;
    this.message_key = envelope.message_key;
    this.details = envelope.details;
  }

  /** Client-side failure (never crossed the wire): attach order, routing. */
  static local(code: string, details?: Record<string, unknown>): HostClientError {
    return new HostClientError({ code, retryable: false, message_key: `bridge.errors.${code.split(".").pop()}`, details });
  }
}

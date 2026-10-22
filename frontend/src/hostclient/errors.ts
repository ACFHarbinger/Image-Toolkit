import type { BridgeError, BridgeResponse, ErrorResponse, ResultResponse } from "../../../contracts/generated/ts";

export class BridgeAppError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly messageKey: string;
  readonly details?: Record<string, unknown>;

  constructor(error: BridgeError) {
    super(error.message_key);
    this.name = "BridgeAppError";
    this.code = error.code;
    this.retryable = error.retryable;
    this.messageKey = error.message_key;
    this.details = error.details;
  }

  toEnvelope(): BridgeError {
    return {
      code: this.code,
      retryable: this.retryable,
      message_key: this.messageKey,
      ...(this.details ? { details: this.details } : {}),
    };
  }
}

export class BridgeTransportError extends Error {
  readonly retryable = true;

  constructor(message: string) {
    super(message);
    this.name = "BridgeTransportError";
  }
}

export function isErrorResponse(response: BridgeResponse): response is ErrorResponse {
  return "error" in response;
}

export function isResultResponse(response: BridgeResponse): response is ResultResponse {
  return "result" in response;
}

export function bridgeUnavailable(details?: Record<string, unknown>): BridgeAppError {
  return new BridgeAppError({
    code: "bridge.down",
    retryable: true,
    message_key: "bridge.unavailable",
    ...(details ? { details } : {}),
  });
}

export function decodeBridgeResult<T>(response: BridgeResponse, requestId: string | number | null): T {
  if (response.id !== requestId) {
    throw new BridgeTransportError(`bridge response id mismatch: expected ${String(requestId)}`);
  }
  if (isErrorResponse(response)) {
    throw new BridgeAppError(response.error.data);
  }
  if (!isResultResponse(response)) {
    throw new BridgeTransportError("bridge response carries neither result nor error");
  }
  return response.result as T;
}

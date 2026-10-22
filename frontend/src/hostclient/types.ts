// Wire types for the HostClient (W0-12, #876).
//
// Contract payload types come from the generated (typing-only) TS client in
// `contracts/generated/ts` (W0-10, #874). The frames themselves are
// validated by the Python bridge package (#875); here we carry them as
// minimally-typed structures and decode errors into `HostClientError`.

import type { BridgeError, BridgeEvent } from "../../../contracts/generated/ts";

export type { BridgeError, BridgeEvent };
export type {
  CancelResult,
  HandshakeResult,
  JobStatus,
  ListParams,
  ListResult,
  PingResult,
  SubmitResult,
} from "../../../contracts/generated/ts";

/** The tested version pair this client ships as (Codex R6). */
export const BRIDGE_PROTOCOL_NAME = "image-toolkit-bridge";
export const BRIDGE_PROTOCOL_VERSION = "1.0.0";

/** JSON-RPC 2.0 request frame (contracts/schemas/envelope/request.json). */
export interface RequestFrame {
  readonly jsonrpc: "2.0";
  readonly id: string;
  readonly method: string;
  readonly params?: Record<string, unknown>;
}

/** JSON-RPC 2.0 response frame (contracts/schemas/envelope/response.json). */
export interface ResponseFrame {
  readonly jsonrpc: "2.0";
  readonly id: string | number | null;
  readonly result?: unknown;
  readonly error?: { readonly code: number; readonly message: string; readonly data: BridgeError };
}

export function isEventFrame(frame: Record<string, unknown>): boolean {
  return typeof frame.channel === "string";
}

export function isResponseFrame(frame: Record<string, unknown>): boolean {
  return frame.jsonrpc === "2.0" && ("result" in frame || "error" in frame);
}

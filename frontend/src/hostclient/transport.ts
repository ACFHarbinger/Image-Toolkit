import type { BridgeEvent, BridgeRequest, BridgeResponse } from "../../../contracts/generated/ts";

/** One shared request/response transport. No second RPC envelope lives here. */
export interface BridgeTransport {
  request(request: BridgeRequest): Promise<BridgeResponse>;
  /** Optional decoded event stream (jobs/bridge channels). */
  onEvent?(listener: (frame: BridgeEvent) => void): () => void;
  /** Optional bounded reconnect hook used before a retry. */
  reset?(): Promise<void> | void;
  close?(): Promise<void> | void;
}

export function buildBridgeRequest(
  method: string,
  requestId: string | number,
  params?: Record<string, unknown>,
): BridgeRequest {
  return {
    jsonrpc: "2.0",
    id: requestId,
    method,
    ...(params === undefined ? {} : { params }),
  };
}

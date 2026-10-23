// GENERATED — contract hash 48a603dc6dcc15a3a230962ec97d6ff121dc28bd5222277e1eb476fb951789d0. Do not edit; edit the schema and regenerate.
import type { BridgeError } from "./error";

export type BridgeResponse = ResultResponse | ErrorResponse;
export interface ErrorResponse {
  readonly jsonrpc: "2.0";
  readonly id: string | number | null;
  readonly error: RpcErrorObject;
}
export interface ResultResponse {
  readonly jsonrpc: "2.0";
  readonly id: string | number | null;
  readonly result: Record<string, unknown> | Array<unknown> | string | number | boolean | null;
}
export interface RpcErrorObject {
  readonly code: number;
  readonly message: string;
  readonly data: BridgeError;
}

// GENERATED — contract hash 6ccbd3c8689db93cd2433f03ff38f9704d5ff9ff0c055064c5e69501e7aeb5f1. Do not edit; edit the schema and regenerate.
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

// GENERATED — contract hash fa9e3693e2291ced0dfb8ea17a7f05e5e7d4db54a64c8886140409356df48860. Do not edit; edit the schema and regenerate.
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

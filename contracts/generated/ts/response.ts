// GENERATED — contract hash a60d8764530060b4277a430a09842662f494142a594a546bda95b31a575f5262. Do not edit; edit the schema and regenerate.
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

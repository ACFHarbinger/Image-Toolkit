// GENERATED — contract hash 9c3ee12cc3be627bb53d8e6b3f564849a135edb081df72e2492a9981a5782385. Do not edit; edit the schema and regenerate.
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

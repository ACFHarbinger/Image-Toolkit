// GENERATED — contract hash 9fe77d2de0e32c92dfddbdf87c37a1f78a2aa550494a3394c78ad951fd387f08. Do not edit; edit the schema and regenerate.

export interface GetManyParams {
  readonly keys: Array<string>;
}
export interface GetManyResult {
  readonly values: Record<string, unknown>;
}
export interface GetParams {
  readonly key: string;
}
export interface GetResult {
  readonly key: string;
  readonly value: null | boolean | number | string | Array<unknown> | Record<string, unknown>;
  readonly scope: Scope;
}
export type Scope = "device" | "account" | "session";
export interface SetManyParams {
  readonly updates: Record<string, unknown>;
}
export interface SetManyResult {
  readonly values: Record<string, unknown>;
}
export interface SetParams {
  readonly key: string;
  readonly value: null | boolean | number | string | Array<unknown> | Record<string, unknown>;
}
export interface SetResult {
  readonly key: string;
  readonly value: null | boolean | number | string | Array<unknown> | Record<string, unknown>;
  readonly scope: Scope;
}

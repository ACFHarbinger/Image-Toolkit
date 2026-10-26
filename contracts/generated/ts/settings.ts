// GENERATED — contract hash 184e19fe7526c6a9f25ef4689e2df0cc7a2b4ad9cf77a0fbf5460be658376f83. Do not edit; edit the schema and regenerate.

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

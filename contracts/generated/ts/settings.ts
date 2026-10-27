// GENERATED — contract hash ea722120ad8fa351bac3b321f84c91a7ef6452903f1eab7771fe53292a7ece8f. Do not edit; edit the schema and regenerate.

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

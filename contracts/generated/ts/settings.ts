// GENERATED — contract hash c9dc9d7141ed461cca53dea9e9cff60d7c77cf1731bb7b0c6ecd3e7a875df09f. Do not edit; edit the schema and regenerate.

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

// GENERATED — contract hash d631902fe126f39d94dc625e1c8688455abc25cc6d7b3c704ab441fd31d985ea. Do not edit; edit the schema and regenerate.

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

// GENERATED — contract hash a4f0fd0f3b4e540630dddc3eaec3ec0e11e1e32419cff02dda892fb79373d8d4. Do not edit; edit the schema and regenerate.

export interface LogsReadParams {
  readonly path: string;
  readonly limit: number;
}
export interface LogsReadResult {
  readonly found: boolean;
  readonly path: string;
  readonly lines: Array<string>;
  readonly error_count: number;
  readonly reason: string;
}
export interface MetadataDescribeParams {
  readonly path: string;
}
export interface MetadataDescribeResult {
  readonly found: boolean;
  readonly path: string;
  readonly name: string;
  readonly size: number;
  readonly suffix: string;
  readonly reason: string;
}

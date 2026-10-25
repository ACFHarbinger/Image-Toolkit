// GENERATED — contract hash a375ee1734bd400623a9aa1b2c07ff89ab62c643d11f99548743568562a87ca9. Do not edit; edit the schema and regenerate.

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

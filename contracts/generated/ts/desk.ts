// GENERATED — contract hash 3624089fd7d9b561e8900f0d7db9e39da11aa994b2d92e7cbee47cd74baee130. Do not edit; edit the schema and regenerate.

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

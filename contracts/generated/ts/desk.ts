// GENERATED — contract hash 7f853bd58530640761fee9a62783e191b67b9cbc62db9153cfadfc7c15d42687. Do not edit; edit the schema and regenerate.

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

// GENERATED — contract hash 11d82ceaf8037efde28126d5553743180fc68a3cda0403f18d9fb8b764f6b3df. Do not edit; edit the schema and regenerate.

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

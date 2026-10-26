// GENERATED — contract hash e3ece40abeda17e5df8d079ddeb991acf09d8b6d21b5da6663083a66186f821d. Do not edit; edit the schema and regenerate.

export interface ProbeParams {
  readonly path: string;
}
export interface ProbeResult {
  readonly available: boolean;
  readonly path: string;
  readonly width: number;
  readonly height: number;
  readonly duration_seconds: number;
  readonly codec: string;
  readonly error: string;
}

// GENERATED — contract hash 9828d6dad4009910dd9a3f4c0e97811a422e460f41ff2599b0549387882f5f56. Do not edit; edit the schema and regenerate.

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

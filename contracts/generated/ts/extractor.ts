// GENERATED — contract hash d4c2f9f05e94f415f5a6aecc1d7684c3dcd8e9bd27a3076fe28a1c5cfdf5a174. Do not edit; edit the schema and regenerate.

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

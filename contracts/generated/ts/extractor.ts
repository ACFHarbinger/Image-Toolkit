// GENERATED — contract hash 9de51fd76cff26625db8bc02d1154d1664e095d6d5e14f6349c28a223d5ca512. Do not edit; edit the schema and regenerate.

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

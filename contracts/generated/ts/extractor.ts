// GENERATED — contract hash fa9e3693e2291ced0dfb8ea17a7f05e5e7d4db54a64c8886140409356df48860. Do not edit; edit the schema and regenerate.

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

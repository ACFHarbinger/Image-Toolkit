// GENERATED — contract hash c9b6edf9c60311bf50a4e7d58a6a25d9164f0ceda3a71af6ec8de11344e19fe8. Do not edit; edit the schema and regenerate.

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

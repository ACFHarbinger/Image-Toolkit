// GENERATED — contract hash 9fe77d2de0e32c92dfddbdf87c37a1f78a2aa550494a3394c78ad951fd387f08. Do not edit; edit the schema and regenerate.

export interface ExtractorCutParams {
  readonly path: string;
  readonly output_dir: string;
  readonly arrangement: "grid" | "vertical" | "horizontal";
  readonly frame_width: number;
  readonly frame_height: number;
  readonly offset_x: number;
  readonly offset_y: number;
  readonly spacing: number;
  readonly include_partial: boolean;
}
export interface ExtractorJobResult {
  readonly job_id: string;
}
export interface ExtractorRangeParams {
  readonly path: string;
  readonly start_seconds: number;
  readonly end_seconds: number;
  readonly output_path: string;
}
export interface ExtractorSnapshotParams {
  readonly path: string;
  readonly time_seconds: number;
  readonly output_path: string;
}
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

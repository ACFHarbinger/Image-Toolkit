// GENERATED — contract hash 9fe77d2de0e32c92dfddbdf87c37a1f78a2aa550494a3394c78ad951fd387f08. Do not edit; edit the schema and regenerate.

export interface StitchCanvasParams {
  readonly input_dir: string;
  readonly preset?: string | null;
}
export interface StitchCanvasResult {
  readonly success: boolean;
  readonly width?: number;
  readonly height?: number;
  readonly num_frames: number;
  readonly frames?: Array<string>;
  readonly elapsed_seconds: number;
  readonly error?: string | null;
}
export interface StitchRunParams {
  readonly input_dir: string;
  readonly output_path?: string | null;
  readonly preset?: string | null;
  readonly blend_mode?: string | null;
}
export interface StitchRunResult {
  readonly success: boolean;
  readonly output_path?: string | null;
  readonly canvas_width?: number | null;
  readonly canvas_height?: number | null;
  readonly frames_processed: number;
  readonly elapsed_seconds: number;
  readonly error?: string | null;
}
export interface StitchStatusParams {
  readonly route: string;
}
export interface StitchStatusResult {
  readonly route: string;
  readonly started: boolean;
  readonly reason: string;
  readonly panel?: string | null;
  readonly stage?: string | null;
  readonly canvas_width?: number | null;
  readonly canvas_height?: number | null;
  readonly frames_count?: number | null;
}

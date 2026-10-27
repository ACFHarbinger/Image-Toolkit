// GENERATED — contract hash 3624089fd7d9b561e8900f0d7db9e39da11aa994b2d92e7cbee47cd74baee130. Do not edit; edit the schema and regenerate.

export interface ConvertBatchParams {
  readonly input_dir: string;
  readonly output_dir: string;
  readonly output_format?: string;
  readonly input_formats?: Array<string>;
  readonly quality?: 95;
  readonly recursive?: boolean;
  readonly overwrite?: boolean;
  readonly paths?: Array<string>;
  readonly action?: "convert" | "resample" | "reencode";
  readonly width?: number;
  readonly height?: number;
  readonly algorithm?: "nearest" | "bilinear" | "bicubic" | "lanczos";
  readonly video_codec?: "h264" | "hevc" | "av1" | "vp9" | "copy";
  readonly audio_codec?: "aac" | "opus" | "mp3" | "flac" | "copy";
  readonly crf?: number;
}
export interface ConvertBatchResult {
  readonly job_id: string;
}
export interface ConvertListDirParams {
  readonly directory: string;
}
export interface ConvertListDirResult {
  readonly files: Array<string>;
  readonly error: string;
}
export interface ConvertParams {
  readonly input_path: string;
  readonly output_path: string;
  readonly output_format?: string;
  readonly quality?: 95;
  readonly overwrite?: boolean;
}
export interface ConvertResult {
  readonly input_path: string;
  readonly output_path: string;
  readonly success: boolean;
  readonly size_bytes?: number;
  readonly elapsed_seconds?: number;
  readonly error?: string | null;
}

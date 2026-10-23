// GENERATED — contract hash 48a603dc6dcc15a3a230962ec97d6ff121dc28bd5222277e1eb476fb951789d0. Do not edit; edit the schema and regenerate.

export interface ConvertBatchParams {
  readonly input_dir: string;
  readonly output_dir: string;
  readonly output_format?: string;
  readonly input_formats?: Array<string>;
  readonly quality?: 95;
  readonly recursive?: boolean;
  readonly overwrite?: boolean;
}
export interface ConvertBatchResult {
  readonly total_discovered: number;
  readonly succeeded: number;
  readonly failed: number;
  readonly output_paths?: Array<string>;
  readonly elapsed_seconds?: number;
  readonly errors?: Array<string>;
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

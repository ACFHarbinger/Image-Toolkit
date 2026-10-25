// GENERATED — contract hash 8d642deabccbb8401ee088016267db1b62784b7eec1a586b20d6336549b79c39. Do not edit; edit the schema and regenerate.

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
  readonly job_id: string;
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

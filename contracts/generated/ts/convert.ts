// GENERATED — contract hash 48148467512ee584ac757ff420b1212bf259e6bc06655926b2980419a7ded0cc. Do not edit; edit the schema and regenerate.

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

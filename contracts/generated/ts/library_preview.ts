// GENERATED — contract hash a06471e200d0ebbad6b544aa116489d517a985e837bd9bf5c797eb5238e2867d. Do not edit; edit the schema and regenerate.

export interface DescribeItem {
  readonly path: string;
  readonly exists: boolean;
  readonly width: number;
  readonly height: number;
  readonly animated: boolean;
  readonly error: string;
}
export interface DescribeParams {
  readonly paths: Array<string>;
}
export interface DescribeResult {
  readonly items: Array<DescribeItem>;
}
export interface DifferenceParams {
  readonly left: string;
  readonly right: string;
  readonly boost: 1 | 2 | 4 | 8;
}
export interface DifferenceResult {
  readonly available: boolean;
  readonly width: number;
  readonly height: number;
  readonly mean_abs: number;
  readonly reason: string;
  readonly png_base64: string;
}
export interface FrameParams {
  readonly path: string;
}
export interface FrameResult {
  readonly path: string;
  readonly width: number;
  readonly height: number;
  readonly png_base64: string;
  readonly error: string;
}

// GENERATED — contract hash c9dc9d7141ed461cca53dea9e9cff60d7c77cf1731bb7b0c6ecd3e7a875df09f. Do not edit; edit the schema and regenerate.

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

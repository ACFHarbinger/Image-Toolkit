// GENERATED — contract hash 6ccbd3c8689db93cd2433f03ff38f9704d5ff9ff0c055064c5e69501e7aeb5f1. Do not edit; edit the schema and regenerate.

export interface ConcatenateParams {
  readonly paths: Array<string>;
  readonly output_path: string;
  readonly direction: "horizontal" | "vertical";
  readonly spacing: number;
  readonly align: "start" | "center" | "end";
}
export interface ConcatenateResult {
  readonly written: boolean;
  readonly output_path: string;
  readonly width: number;
  readonly height: number;
  readonly preview_png_base64: string;
  readonly error: string;
}

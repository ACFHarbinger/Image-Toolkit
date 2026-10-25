// GENERATED — contract hash 9828d6dad4009910dd9a3f4c0e97811a422e460f41ff2599b0549387882f5f56. Do not edit; edit the schema and regenerate.

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

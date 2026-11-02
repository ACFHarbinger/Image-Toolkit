// GENERATED — contract hash c30cf0dd6674a685340ce15641f019f568d5adba75e10d53baca8364f72fe25d. Do not edit; edit the schema and regenerate.

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
export interface MergePlaceParams {
  readonly placements: Array<MergePlacement>;
  readonly output_path: string;
}
export interface MergePlacement {
  readonly path: string;
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

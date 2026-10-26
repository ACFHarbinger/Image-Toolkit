// GENERATED — contract hash 1b081c15dfb3252eeb7f0209c44d8f0e6d1689dc3d7a36162b2e9c360c9d65cd. Do not edit; edit the schema and regenerate.

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

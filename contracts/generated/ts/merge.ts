// GENERATED — contract hash 35537ebccd17268699e0134e7765a44288a13d2edf300ce1e33770aeee8d3856. Do not edit; edit the schema and regenerate.

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

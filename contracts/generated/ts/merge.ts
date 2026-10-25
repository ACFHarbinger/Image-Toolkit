// GENERATED — contract hash 48148467512ee584ac757ff420b1212bf259e6bc06655926b2980419a7ded0cc. Do not edit; edit the schema and regenerate.

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

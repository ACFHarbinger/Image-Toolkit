// GENERATED — contract hash ea722120ad8fa351bac3b321f84c91a7ef6452903f1eab7771fe53292a7ece8f. Do not edit; edit the schema and regenerate.

export interface ArapDeformParams {
  readonly image_path: string;
  readonly control_points: Array<Array<number>>;
  readonly target_points: Array<Array<number>>;
  readonly output_path?: string;
  readonly mesh_resolution?: number;
}
export interface ArapDeformPayload {
  readonly success: boolean;
  readonly output_path?: string | null;
  readonly num_vertices: number;
  readonly num_triangles: number;
  readonly elapsed_seconds: number;
  readonly error?: string | null;
}
export interface ColorizeReferenceParams {
  readonly lineart_path: string;
  readonly reference_path: string;
  readonly output_path?: string;
  readonly epsilon?: number;
  readonly max_iter?: number;
}
export interface ColorizeScribbleParams {
  readonly lineart_path: string;
  readonly scribble_path: string;
  readonly output_path?: string;
  readonly intensity?: number;
  readonly use_screentone?: boolean;
}
export interface ColorizeScribblePayload {
  readonly success: boolean;
  readonly output_path?: string | null;
  readonly width: number;
  readonly height: number;
  readonly elapsed_seconds: number;
  readonly error?: string | null;
}
export interface PropagateSequenceParams {
  readonly frame_paths: Array<string>;
  readonly keyframe_index?: number;
  readonly keyframe_color_path?: string;
  readonly output_dir?: string;
}
export interface PropagateSequencePayload {
  readonly success: boolean;
  readonly output_paths: Array<string>;
  readonly frames_processed: number;
  readonly elapsed_seconds: number;
  readonly error?: string | null;
}

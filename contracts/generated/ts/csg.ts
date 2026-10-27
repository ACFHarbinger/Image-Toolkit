// GENERATED — contract hash 0f49aea8dd625fc56b2e2aaefc29f91d6c8e55ea3e9a57354a03e5352c6ad9b5. Do not edit; edit the schema and regenerate.

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

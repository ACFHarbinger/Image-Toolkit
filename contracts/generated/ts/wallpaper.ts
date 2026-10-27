// GENERATED — contract hash 35537ebccd17268699e0134e7765a44288a13d2edf300ce1e33770aeee8d3856. Do not edit; edit the schema and regenerate.

export type GetMonitorsParams = Record<string, unknown>;
export interface GetMonitorsResult {
  readonly monitors: Array<MonitorInfo>;
  readonly desktop_environment: string;
}
export interface MonitorInfo {
  readonly id: string;
  readonly name: string;
  readonly width: number;
  readonly height: number;
  readonly x: number;
  readonly y: number;
  readonly is_primary: boolean;
}
export interface SetWallpaperParams {
  readonly path_map: Record<string, string>;
  readonly style?: "fill" | "fit" | "stretch" | "center" | "tile" | "span";
  readonly monitors?: Array<number>;
  readonly background_color?: string | null;
}
export interface SetWallpaperResult {
  readonly success: boolean;
  readonly message: string;
  readonly applied_monitors: Array<string>;
}
export interface SlideshowConfigParams {
  readonly update: boolean;
  readonly interval_seconds?: number | null;
  readonly style?: string | null;
  readonly monitor_queues?: Record<string, Array<string>> | null;
  readonly current_paths?: Record<string, string> | null;
}
export interface SlideshowConfigResult {
  readonly interval_seconds: number;
  readonly style: string;
  readonly monitor_queues: Record<string, Array<string>>;
  readonly current_paths: Record<string, string>;
  readonly config_path: string;
  readonly running: boolean;
}
export interface SlideshowToggleParams {
  readonly running: boolean;
}
export interface SlideshowToggleResult {
  readonly running: boolean;
  readonly pid?: number | null;
  readonly message: string;
}
export interface WallpaperGraphEdge {
  readonly source: string;
  readonly target: string;
}
export interface WallpaperGraphNode {
  readonly id: string;
  readonly path: string;
  readonly duration_seconds: number;
}
export interface WallpaperGraphParams {
  readonly update: boolean;
  readonly path: string;
  readonly nodes?: Array<WallpaperGraphNode>;
  readonly edges?: Array<WallpaperGraphEdge>;
  readonly end_behavior?: "repeat" | "stay" | "solid";
  readonly end_color?: string;
}
export interface WallpaperGraphResult {
  readonly path: string;
  readonly nodes: Array<WallpaperGraphNode>;
  readonly edges: Array<WallpaperGraphEdge>;
  readonly end_behavior: "repeat" | "stay" | "solid";
  readonly end_color: string;
  readonly error: string;
}

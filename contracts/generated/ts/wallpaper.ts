// GENERATED — contract hash 239dc4acbba4111ef20878825587c4d6be98066d75cb0526995ffceaafec9cdb. Do not edit; edit the schema and regenerate.

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
}
export interface SlideshowToggleParams {
  readonly running: boolean;
}
export interface SlideshowToggleResult {
  readonly running: boolean;
  readonly pid?: number | null;
  readonly message: string;
}

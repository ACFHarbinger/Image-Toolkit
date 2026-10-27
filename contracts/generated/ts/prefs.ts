// GENERATED — contract hash 3624089fd7d9b561e8900f0d7db9e39da11aa994b2d92e7cbee47cd74baee130. Do not edit; edit the schema and regenerate.

export interface PrefsDescribeParams {
  readonly account: string;
}
export interface PrefsDescribeResult {
  readonly sections: Array<"account" | "profiles" | "gallery" | "logging" | "shortcuts">;
  readonly credentials_changed: false;
  readonly reason: "credentials stay on the C++ vault session";
}
export interface PrefsGallery {
  readonly thumbnail_size: number;
  readonly page_size: number;
  readonly confirm_deletions: boolean;
  readonly recursive_scan: boolean;
}
export interface PrefsGetParams {
  readonly account: string;
}
export interface PrefsGetResult {
  readonly account: string;
  readonly profiles: PrefsProfiles;
  readonly gallery: PrefsGallery;
  readonly logging: PrefsLogging;
  readonly shortcuts: Array<PrefsShortcut>;
}
export interface PrefsLogging {
  readonly level: "DEBUG" | "INFO" | "WARNING" | "ERROR";
  readonly file_logging: boolean;
}
export interface PrefsProfiles {
  readonly startup_category: string;
  readonly startup_tab: string;
}
export interface PrefsSetParams {
  readonly account: string;
  readonly current_password?: string;
  readonly new_password?: string;
  readonly profiles: PrefsProfiles;
  readonly gallery: PrefsGallery;
  readonly logging: PrefsLogging;
  readonly shortcut?: PrefsShortcutOverride;
}
export interface PrefsSetResult {
  readonly success: boolean;
  readonly reason: string;
  readonly credentials_changed: boolean;
  readonly account: string;
  readonly profiles: PrefsProfiles;
  readonly gallery: PrefsGallery;
  readonly logging: PrefsLogging;
  readonly shortcuts: Array<PrefsShortcut>;
}
export interface PrefsShortcut {
  readonly id: string;
  readonly description: string;
  readonly scope: string;
  readonly default: string;
  readonly custom: string;
}
export interface PrefsShortcutOverride {
  readonly action: string;
  readonly chord: string;
}

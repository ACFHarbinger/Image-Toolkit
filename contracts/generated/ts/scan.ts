// GENERATED — contract hash 8f3b63259aeee332f0b0ef1780647fdc1e5692c6d3e1a1d6b8b0aeb24360f303. Do not edit; edit the schema and regenerate.

export interface SaveMetadataItem {
  readonly path: string;
  readonly tags?: Array<string>;
  readonly group_name?: string | null;
  readonly subgroup_name?: string | null;
}
export interface SaveMetadataParams {
  readonly items: Array<SaveMetadataItem>;
}
export interface SaveMetadataResult {
  readonly saved_count: number;
  readonly success: boolean;
  readonly database_available: boolean;
  readonly errors?: Array<string>;
}
export interface ScanDirectoryParams {
  readonly directory: string;
  readonly recursive?: boolean;
  readonly formats?: Array<string>;
  readonly max_results?: number;
}
export interface ScanDirectoryResult {
  readonly directory: string;
  readonly total_found: number;
  readonly images: Array<ScannedImage>;
  readonly database_available: boolean;
}
export interface ScannedImage {
  readonly path: string;
  readonly filename: string;
  readonly extension: string;
  readonly size_bytes: number;
  readonly width?: number | null;
  readonly height?: number | null;
  readonly in_database: boolean;
  readonly tags?: Array<string>;
  readonly group_name?: string | null;
  readonly subgroup_name?: string | null;
}
export interface SuggestTagsParams {
  readonly paths: Array<string>;
}
export interface SuggestTagsResult {
  readonly suggestions: Record<string, Array<string>>;
}

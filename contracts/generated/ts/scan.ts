// GENERATED — contract hash e3ece40abeda17e5df8d079ddeb991acf09d8b6d21b5da6663083a66186f821d. Do not edit; edit the schema and regenerate.

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

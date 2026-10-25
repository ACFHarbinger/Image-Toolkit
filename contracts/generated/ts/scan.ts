// GENERATED — contract hash 9a0cc13149be2f4357ee006a22bcdf31bed4796f55b7e30240cfb3eda4b5e150. Do not edit; edit the schema and regenerate.

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

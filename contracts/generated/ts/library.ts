// GENERATED — contract hash a375ee1734bd400623a9aa1b2c07ff89ab62c643d11f99548743568562a87ca9. Do not edit; edit the schema and regenerate.

export type EmptyParams = Record<string, unknown>;
export interface GroupRecord {
  readonly name: string;
  readonly subgroups: Array<string>;
}
export interface ImageRecord {
  readonly id: number;
  readonly file_path: string;
  readonly filename: string;
  readonly file_size?: number | null;
  readonly width?: number | null;
  readonly height?: number | null;
  readonly phash?: number | null;
  readonly group_name?: string | null;
  readonly subgroup_name?: string | null;
  readonly date_added?: string | null;
  readonly date_modified?: string | null;
  readonly tags?: Array<string>;
  readonly distance?: number | null;
}
export interface ListGroupsResult {
  readonly available: boolean;
  readonly groups: Array<GroupRecord>;
}
export interface ListImagesParams {
  readonly group_name?: string;
  readonly subgroup_name?: string;
  readonly tags?: Array<string>;
  readonly filename_pattern?: string;
  readonly input_formats?: Array<string>;
  readonly group_names?: Array<string>;
  readonly subgroup_names?: Array<string>;
  readonly limit?: number;
}
export interface ListImagesResult {
  readonly available: boolean;
  readonly images: Array<ImageRecord>;
}
export interface ListTagsResult {
  readonly available: boolean;
  readonly tags: Array<string>;
}

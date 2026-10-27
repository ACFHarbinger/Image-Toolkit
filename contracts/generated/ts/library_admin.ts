// GENERATED — contract hash 3624089fd7d9b561e8900f0d7db9e39da11aa994b2d92e7cbee47cd74baee130. Do not edit; edit the schema and regenerate.

export type AdminEmptyParams = Record<string, unknown>;
export interface AdminGroupRecord {
  readonly name: string;
  readonly subgroups: Array<string>;
}
export interface BrowseParams {
  readonly table: string;
  readonly limit: number;
  readonly offset: number;
  readonly column?: string;
  readonly equals?: string;
}
export interface BrowseResult {
  readonly available: boolean;
  readonly columns: Array<string>;
  readonly rows: Array<BrowseRow>;
  readonly row_count: number;
  readonly error: string;
}
export interface BrowseRow {
  readonly cells: Array<string>;
}
export interface CatalogResult {
  readonly available: boolean;
  readonly groups: Array<AdminGroupRecord>;
  readonly tags: Array<TagRecord>;
  readonly tables: Array<string>;
}
export type MutateAction = "create_group" | "create_subgroup" | "create_tag" | "remove_group" | "remove_subgroup" | "remove_tag" | "merge_tags" | "rename_group" | "rename_subgroup" | "rename_tag" | "update_tag" | "delete_image";
export interface MutateParams {
  readonly action: MutateAction;
  readonly name: string;
  readonly parent?: string;
  readonly category?: string;
  readonly destination?: string;
}
export interface MutateResult {
  readonly available: boolean;
  readonly applied: number;
  readonly error: string;
}
export interface TagRecord {
  readonly name: string;
  readonly category: string;
}

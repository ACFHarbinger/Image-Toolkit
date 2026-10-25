// GENERATED — contract hash eb57d1d3ee001de50bb35743f515830d8370c51552d7d005103b952116fb1b96. Do not edit; edit the schema and regenerate.

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
  readonly groups: Array<GroupRecord>;
  readonly tags: Array<TagRecord>;
}
export type EmptyParams = Record<string, unknown>;
export interface GroupRecord {
  readonly name: string;
  readonly subgroups: Array<string>;
}
export type MutateAction = "create_group" | "create_subgroup" | "create_tag" | "remove_group" | "remove_subgroup" | "remove_tag" | "merge_tags";
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

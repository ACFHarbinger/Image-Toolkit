// GENERATED — contract hash c30cf0dd6674a685340ce15641f019f568d5adba75e10d53baca8364f72fe25d. Do not edit; edit the schema and regenerate.

export interface EngineRecord {
  readonly id: "bing" | "google" | "iqdb" | "local_cbir" | "saucenao" | "tineye" | "yandex";
  readonly label: string;
}
export interface EnginesResult {
  readonly engines: Array<EngineRecord>;
}
export type ReverseSearchEmptyParams = Record<string, unknown>;
export interface ReverseSearchResultItem {
  readonly url: string;
  readonly engine: string;
  readonly score: number;
  readonly resolution?: string;
  readonly title?: string | null;
}
export interface SearchParams {
  readonly engine: "bing" | "google" | "iqdb" | "local_cbir" | "saucenao" | "tineye" | "yandex";
  readonly image_path: string;
  readonly limit?: number;
  readonly roi?: Array<number>;
}
export interface SearchResult {
  readonly ok: boolean;
  readonly engine: string;
  readonly results: Array<ReverseSearchResultItem>;
  readonly error?: string | null;
}

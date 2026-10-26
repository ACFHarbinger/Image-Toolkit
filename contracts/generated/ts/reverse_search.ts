// GENERATED — contract hash ea722120ad8fa351bac3b321f84c91a7ef6452903f1eab7771fe53292a7ece8f. Do not edit; edit the schema and regenerate.

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

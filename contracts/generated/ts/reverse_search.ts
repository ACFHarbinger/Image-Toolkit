// GENERATED — contract hash 3624089fd7d9b561e8900f0d7db9e39da11aa994b2d92e7cbee47cd74baee130. Do not edit; edit the schema and regenerate.

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

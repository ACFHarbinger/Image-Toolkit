// GENERATED — contract hash 35537ebccd17268699e0134e7765a44288a13d2edf300ce1e33770aeee8d3856. Do not edit; edit the schema and regenerate.

export interface EntityReconDescribeResult {
  readonly available: boolean;
  readonly config: ReconConfigSnapshot;
}
export type EntityReconEmptyParams = Record<string, unknown>;
export interface EntityReconResolveParams {
  readonly image_path: string;
  readonly search_scope?: "local" | "web" | "both";
  readonly local_match_threshold?: number;
  readonly top_k?: number;
}
export interface EntityReconResolveResult {
  readonly available: boolean;
  readonly found: boolean;
  readonly name: string;
  readonly confidence: number;
  readonly method: string;
  readonly origin: "local" | "web" | "none";
  readonly local_matches: Array<LocalMatchItem>;
  readonly web_domains: Array<WebDomainItem>;
  readonly report: ProvenanceReportItem;
  readonly error?: string | null;
}
export interface LocalMatchItem {
  readonly label: string;
  readonly path: string;
  readonly score: number;
}
export interface ProvenanceEntryItem {
  readonly kind: string;
  readonly label: string;
  readonly source: string;
  readonly domain?: string;
  readonly score: number;
  readonly method: string;
}
export interface ProvenanceReportItem {
  readonly query_hash: string;
  readonly predicted_name: string;
  readonly confidence: number;
  readonly method: string;
  readonly created_at: string;
  readonly entries: Array<ProvenanceEntryItem>;
}
export interface ReconConfigSnapshot {
  readonly search_scope: "local" | "web" | "both";
  readonly privacy_mode: boolean;
  readonly local_match_threshold: number;
  readonly top_k: number;
  readonly embed_mode: "face" | "clip";
  readonly reverse_engines: Array<string>;
}
export interface WebDomainItem {
  readonly domain: string;
  readonly count: number;
  readonly urls: Array<string>;
}

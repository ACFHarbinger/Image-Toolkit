// GENERATED — contract hash 9de51fd76cff26625db8bc02d1154d1664e095d6d5e14f6349c28a223d5ca512. Do not edit; edit the schema and regenerate.

export interface AuthConfig {
  readonly username?: string | null;
  readonly api_key?: string | null;
}
export interface CrawlParams {
  readonly crawler_type: "general" | "danbooru" | "gelbooru" | "sankaku" | "safebooru";
  readonly download_dir: string;
  readonly url?: string | null;
  readonly tags?: string | null;
  readonly limit?: number | null;
  readonly max_pages?: number | null;
  readonly actions?: Array<string> | null;
  readonly login_config?: LoginConfig;
  readonly auth?: AuthConfig;
}
export interface CrawlResult {
  readonly success: boolean;
  readonly crawler_type: string;
  readonly total_downloaded: number;
  readonly download_dir: string;
  readonly errors: Array<string>;
  readonly elapsed_seconds: number;
}
export type CrawlerSupportedParams = Record<string, unknown>;
export interface CrawlerSupportedResult {
  readonly types: Array<string>;
  readonly boards: Array<string>;
  readonly action_templates: Array<string>;
}
export interface LoginConfig {
  readonly url?: string | null;
  readonly username?: string | null;
  readonly password?: string | null;
}

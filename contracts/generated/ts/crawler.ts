// GENERATED — contract hash c9b6edf9c60311bf50a4e7d58a6a25d9164f0ceda3a71af6ec8de11344e19fe8. Do not edit; edit the schema and regenerate.

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

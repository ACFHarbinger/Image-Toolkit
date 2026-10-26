// GENERATED — contract hash 0f49aea8dd625fc56b2e2aaefc29f91d6c8e55ea3e9a57354a03e5352c6ad9b5. Do not edit; edit the schema and regenerate.

export interface MediaFetchParams {
  readonly url: string;
  readonly destination: string;
}
export interface MediaFetchResult {
  readonly success: boolean;
  readonly url: string;
  readonly destination_path: string;
  readonly bytes_downloaded: number;
  readonly elapsed_seconds: number;
  readonly error?: string | null;
}
export interface MediaPlanParams {
  readonly url: string;
  readonly destination: string;
}
export interface MediaPlanResult {
  readonly accepted: boolean;
  readonly downloaded: false;
  readonly url: string;
  readonly destination: string;
  readonly reason: string;
}

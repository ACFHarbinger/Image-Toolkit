// GENERATED — contract hash 28918ce8760d36700226684cdf4b39a9465953292b3c3913b49e167c15ce7d55. Do not edit; edit the schema and regenerate.

export interface DriveSyncPlanParams {
  readonly provider: "google_drive" | "dropbox" | "onedrive";
  readonly paths: Array<string>;
}
export interface DriveSyncPlanResult {
  readonly submitted: false;
  readonly provider: "google_drive" | "dropbox" | "onedrive";
  readonly count: number;
  readonly reason: string;
}

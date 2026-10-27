// GENERATED — contract hash 0f49aea8dd625fc56b2e2aaefc29f91d6c8e55ea3e9a57354a03e5352c6ad9b5. Do not edit; edit the schema and regenerate.
import type { BridgeError } from "./error";

export interface CancelParams {
  readonly job_id: string;
}
export interface CancelResult {
  readonly ok: true;
}
export interface JobEventPayload {
  readonly job_id: string;
  readonly state: JobState;
  readonly progress?: JobProgress;
}
export interface JobListSnapshot {
  readonly jobs: Array<JobStatus>;
}
export interface JobProgress {
  readonly done: number;
  readonly total: number;
}
export type JobState = "queued" | "provisioning" | "running" | "cancelling" | "collecting" | "settling" | "completed" | "failed" | "cancelled" | "capped";
export interface JobStatus {
  readonly job_id: string;
  readonly kind: string;
  readonly state: JobState;
  readonly progress?: JobProgress;
  readonly error?: BridgeError;
  readonly result?: Record<string, unknown>;
}
export interface ListParams {
  readonly states?: Array<JobState>;
  readonly limit?: number;
}
export interface ListResult {
  readonly jobs: Array<JobStatus>;
}
export interface StatusParams {
  readonly job_id: string;
}
export interface SubmitParams {
  readonly kind: string;
  readonly spec: Record<string, unknown>;
}
export interface SubmitResult {
  readonly job_id: string;
}

// GENERATED — contract hash fd88a7fef136d55677f1b54786db5f5cc6ad804b203c2f6e41cebc765dabefbd. Do not edit; edit the schema and regenerate.
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

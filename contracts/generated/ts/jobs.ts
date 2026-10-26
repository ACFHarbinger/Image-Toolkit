// GENERATED — contract hash e0db33d9af5a9a4f1a6cdc08951212bea919fbae41766e4c197dbe507cb15e7e. Do not edit; edit the schema and regenerate.
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

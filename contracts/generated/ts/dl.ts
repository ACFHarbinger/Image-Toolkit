// GENERATED — contract hash ea722120ad8fa351bac3b321f84c91a7ef6452903f1eab7771fe53292a7ece8f. Do not edit; edit the schema and regenerate.

export interface DlCancelParams {
  readonly run_id: string;
}
export interface DlCancelResult {
  readonly run_id: string;
  readonly canceled: boolean;
  readonly message: string;
}
export interface DlComfyQueueParams {
  readonly workflow: Record<string, unknown>;
  readonly client_id?: string;
  readonly overrides?: Record<string, unknown>;
}
export interface DlComfyQueueResult {
  readonly prompt_id: string;
  readonly queued: boolean;
  readonly message: string;
}
export interface DlComfyRunStatusParams {
  readonly prompt_id: string;
}
export interface DlComfyRunStatusResult {
  readonly prompt_id: string;
  readonly status: string;
  readonly completed: boolean;
  readonly output_images: Array<string>;
  readonly message: string;
}
export interface DlComfyStartParams {
  readonly port?: number;
  readonly enable_manager?: boolean;
  readonly external?: boolean;
}
export interface DlComfyStartResult {
  readonly port: number;
  readonly url: string;
  readonly state: string;
  readonly success: boolean;
  readonly message: string;
}
export interface DlComfyStatusParams {
  readonly probe?: boolean;
}
export interface DlComfyStatusResult {
  readonly state: string;
  readonly url: string;
  readonly port: number;
  readonly owns_server: boolean;
  readonly ready: boolean;
}
export type DlComfyStopParams = Record<string, unknown>;
export interface DlComfyStopResult {
  readonly stopped: boolean;
  readonly message: string;
}
export interface DlEvaluateParams {
  readonly model_path: string;
  readonly dataset_path: string;
  readonly metrics?: Array<string>;
  readonly config?: Record<string, unknown>;
}
export interface DlEvaluateResult {
  readonly job_id: string;
  readonly status: string;
  readonly scores: Record<string, number>;
  readonly message: string;
}
export interface DlGenerateParams {
  readonly model_architecture: string;
  readonly output_dir: string;
  readonly prompt?: string;
  readonly negative_prompt?: string;
  readonly model_path?: string;
  readonly num_images?: number;
  readonly seed?: number;
  readonly config?: Record<string, unknown>;
}
export interface DlGenerateResult {
  readonly job_id: string;
  readonly status: string;
  readonly output_images: Array<string>;
  readonly message: string;
}
export interface DlInferParams {
  readonly model_version: string;
  readonly image_path: string;
  readonly prompts?: Array<string>;
  readonly config?: Record<string, unknown>;
}
export interface DlInferResult {
  readonly job_id: string;
  readonly predictions: Array<DlPrediction>;
  readonly message: string;
}
export interface DlInspectParams {
  readonly run_dir: string;
}
export interface DlInspectResult {
  readonly found: boolean;
  readonly run_dir: string;
  readonly run_id: string;
  readonly status: string;
  readonly engine: string;
  readonly model_id: string;
  readonly event_count: number;
  readonly started: false;
  readonly reason: string;
}
export interface DlPrediction {
  readonly label: string;
  readonly score: number;
}
export interface DlStatusParams {
  readonly run_id: string;
  readonly run_dir?: string;
}
export interface DlStatusResult {
  readonly run_id: string;
  readonly status: string;
  readonly step: number;
  readonly total_steps: number;
  readonly loss?: number;
  readonly events_count: number;
  readonly message: string;
}
export interface DlTrainParams {
  readonly model_architecture: string;
  readonly dataset_path: string;
  readonly output_dir: string;
  readonly output_name?: string;
  readonly epochs?: number;
  readonly batch_size?: number;
  readonly learning_rate?: number;
  readonly device?: string;
  readonly config?: Record<string, unknown>;
}
export interface DlTrainResult {
  readonly run_id: string;
  readonly run_dir: string;
  readonly status: string;
  readonly started: boolean;
  readonly message: string;
}

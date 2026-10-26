// GENERATED — contract hash 25bb1ff48ee734cd0ab7e3b3a0936c4ad12ee96988058c651d235a1188a48fd3. Do not edit; edit the schema and regenerate.

export interface ActionItem {
  readonly type: "Print Response URL" | "Print Response Status Code" | "Print Response Headers" | "Print Response Content (Text)" | "Save Response Content (Binary)";
  readonly param?: string;
}
export interface ExecuteParams {
  readonly url: string;
  readonly method?: "GET" | "POST" | "PUT" | "DELETE" | "HEAD" | "PATCH";
  readonly headers?: Record<string, string>;
  readonly body?: string;
  readonly timeout_seconds?: number;
}
export interface ExecuteResult {
  readonly url: string;
  readonly status_code: number;
  readonly status_text: string;
  readonly headers: Record<string, string>;
  readonly content_type: string;
  readonly body: string;
  readonly duration_ms: number;
  readonly error?: string | null;
}
export interface RequestItem {
  readonly type: "GET" | "POST" | "PUT" | "DELETE" | "HEAD" | "PATCH";
  readonly param?: string;
  readonly headers?: Record<string, string>;
}
export interface SequenceItemResult {
  readonly index: number;
  readonly url: string;
  readonly method: string;
  readonly status_code: number;
  readonly saved_path?: string | null;
  readonly error?: string | null;
}
export interface SequenceParams {
  readonly base_url: string;
  readonly requests: Array<RequestItem>;
  readonly actions: Array<ActionItem>;
  readonly timeout_seconds?: number;
}
export interface SequenceResult {
  readonly status: "completed" | "failed" | "cancelled";
  readonly base_url: string;
  readonly total_requests: number;
  readonly completed_requests: number;
  readonly logs: Array<string>;
  readonly items: Array<SequenceItemResult>;
  readonly message: string;
}

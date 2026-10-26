// GENERATED — contract hash fa9e3693e2291ced0dfb8ea17a7f05e5e7d4db54a64c8886140409356df48860. Do not edit; edit the schema and regenerate.

export interface EditParams {
  readonly document_id: string;
  readonly operation: string;
  readonly parameters?: Record<string, unknown> | null;
}
export interface EditResult {
  readonly success: boolean;
  readonly document_id: string;
  readonly output_document_id?: string | null;
  readonly modified_layers: Array<string>;
  readonly elapsed_seconds: number;
  readonly error?: string | null;
}
export interface ExportDocumentParams {
  readonly document_id: string;
  readonly output_path: string;
  readonly format?: string | null;
  readonly quality?: number | null;
}
export interface ExportDocumentResult {
  readonly success: boolean;
  readonly output_path: string;
  readonly size_bytes: number;
  readonly elapsed_seconds: number;
  readonly error?: string | null;
}
export type ListCapabilitiesParams = Record<string, unknown>;
export interface ListCapabilitiesResult {
  readonly capabilities: Array<string>;
  readonly models_available: Array<string>;
  readonly error?: string | null;
}
export interface OpenDocumentParams {
  readonly source: string;
  readonly document_id?: string | null;
  readonly metadata?: Record<string, unknown> | null;
}
export interface OpenDocumentResult {
  readonly success: boolean;
  readonly document_id: string;
  readonly frame_count: number;
  readonly width: number;
  readonly height: number;
  readonly elapsed_seconds: number;
  readonly error?: string | null;
}

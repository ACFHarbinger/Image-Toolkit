// GENERATED — contract hash 14dc0dc0480777ad7b420a37a80c7b853d9b7799347579fd417e144297b27b6c. Do not edit; edit the schema and regenerate.

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

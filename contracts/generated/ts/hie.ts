// GENERATED — contract hash 9de51fd76cff26625db8bc02d1154d1664e095d6d5e14f6349c28a223d5ca512. Do not edit; edit the schema and regenerate.

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
export interface HieLayer {
  readonly id: string;
  readonly name: string;
  readonly visible: boolean;
  readonly opacity: number;
  readonly blend_mode?: string | null;
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
export interface RenderViewportParams {
  readonly document_id: string;
  readonly zoom?: number | null;
  readonly pan_x?: number | null;
  readonly pan_y?: number | null;
  readonly viewport_width?: number | null;
  readonly viewport_height?: number | null;
}
export interface RenderViewportResult {
  readonly success: boolean;
  readonly document_id: string;
  readonly width?: number;
  readonly height?: number;
  readonly layers?: Array<HieLayer>;
  readonly elapsed_seconds: number;
  readonly error?: string | null;
}

/**
 * Drag-out source for the S-05 drag-and-drop spike (#891).
 *
 * Chromium implements the de-facto `DownloadURL` DataTransfer type: a
 * `mime:filename:url` payload the browser turns into a real file when
 * the user drops onto a supporting file manager. `text/uri-list` backs
 * it up for targets that only speak URLs. Native out-of-webview drags
 * (Wayland compositors ignore DownloadURL entirely) plug in through the
 * NativeDragOut seam at the bottom — see the TODO there.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { DragEvent as ReactDragEvent } from "react";

export interface OutboundDragItem {
  readonly mime: string;
  readonly filename: string;
  /** Object/blob URL the payload points at. */
  readonly blobUrl: string;
}

const FALLBACK_MIME = "application/octet-stream";

/**
 * Build one `mime:filename:url` DownloadURL entry. Colons and newlines
 * in the filename would corrupt the parse (the URL section may contain
 * colons — only the filename is sanitized), so they become underscores.
 */
export function buildDownloadUrlPayload(mime: string, filename: string, blobUrl: string): string {
  const safeMime = mime.length > 0 ? mime : FALLBACK_MIME;
  const safeName = filename.replace(/[:/\r\n]+/g, "_");
  return `${safeMime}:${safeName}:${blobUrl}`;
}

/**
 * Populate a DataTransfer for dragging out. Multiple items ride as
 * newline-joined DownloadURL entries plus a CRLF-joined uri-list.
 */
export function applyDragSource(dt: DataTransfer, items: readonly OutboundDragItem[]): void {
  if (items.length === 0) return;
  dt.setData(
    "DownloadURL",
    items.map((item) => buildDownloadUrlPayload(item.mime, item.filename, item.blobUrl)).join("\n"),
  );
  dt.setData("text/uri-list", items.map((item) => item.blobUrl).join("\r\n"));
  dt.effectAllowed = "copy";
}

export interface UseDragSourceOptions {
  readonly onDragStart?: (event: ReactDragEvent<HTMLElement>) => void;
  readonly onDragEnd?: (event: ReactDragEvent<HTMLElement>) => void;
}

export interface DragSourceBinding {
  readonly draggable: boolean;
  readonly dragging: boolean;
  readonly onDragStart: (event: ReactDragEvent<HTMLElement>) => void;
  readonly onDragEnd: (event: ReactDragEvent<HTMLElement>) => void;
}

/**
 * Hook spreading drag-source props onto an element:
 * `<div {...useDragSource(items)}>`. Items/options are read at event
 * time, so callers can pass a fresh array each render.
 */
export function useDragSource(
  items: readonly OutboundDragItem[],
  options: UseDragSourceOptions = {},
): DragSourceBinding {
  const [dragging, setDragging] = useState(false);
  const latest = useRef({ items, options });
  useEffect(() => {
    latest.current = { items, options };
  });
  const onDragStart = useCallback((event: ReactDragEvent<HTMLElement>) => {
    applyDragSource(event.dataTransfer, latest.current.items);
    setDragging(true);
    latest.current.options.onDragStart?.(event);
  }, []);
  const onDragEnd = useCallback((event: ReactDragEvent<HTMLElement>) => {
    setDragging(false);
    latest.current.options.onDragEnd?.(event);
  }, []);
  return { draggable: true, dragging, onDragStart, onDragEnd };
}

/**
 * TODO(S-05 production follow-up): native drags out of the webview need
 * a Tauri-side drag source — `tauri-plugin-drag`'s `start_drag`, or a
 * custom Rust command over `tauri::Drag` where the platform supports
 * it. Production wiring registers a handle here at startup;
 * `useDragSource` then delegates to it when a filesystem path is known
 * (DownloadURL stays the blob fallback). Until a handle is registered
 * `getNativeDragOut()` returns null and callers keep the web-standard
 * path. No Rust is shipped as part of this spike.
 */
export interface NativeDragOutHandle {
  readonly startDrag: (paths: string[]) => Promise<void>;
}

let nativeDragOut: NativeDragOutHandle | null = null;

export function registerNativeDragOut(handle: NativeDragOutHandle | null): void {
  nativeDragOut = handle;
}

export function getNativeDragOut(): NativeDragOutHandle | null {
  return nativeDragOut;
}

/**
 * Inbound ingestion adapter for the S-05 drag-and-drop spike (#891).
 *
 * Turns Tauri webview drag-drop events — and, as the plain-browser/Vite
 * fallback, DOM DataTransfer drops — into validated PlannedDrop batches
 * via planDrop(). `@tauri-apps/api/webview` is only ever dynamic-imported
 * inside subscribeTauriDrop(), so jsdom tests and the Vite dev browser
 * never load the Tauri module (no runtime globals exist there).
 */

import { useEffect, useRef, type RefObject } from "react";
import { planDrop, type DropFs, type PlannedDrop } from "./paths";
import type { DragDropEvent } from "@tauri-apps/api/webview";

/** Normalized drop event. Unlike Tauri's DragDropEvent, paths is always present (empty on over/leave). */
export interface TauriDropPosition {
  readonly x: number;
  readonly y: number;
}

export type TauriDropEvent = {
  readonly type: "over" | "enter" | "leave" | "drop";
  readonly position: TauriDropPosition;
  readonly paths: readonly string[];
};

/** Small assertable summary for each handled event/batch. */
export interface InboundSummary {
  /** True when the event was hover noise (over/enter/leave); counts stay 0. */
  readonly ignored: boolean;
  readonly accepted: number;
  readonly rejected: number;
}

export interface InboundPlanOptions {
  readonly fs: DropFs;
  /** Budget knobs forwarded to planDrop(). */
  readonly maxBytesPerFile?: number;
  readonly maxItems?: number;
  readonly maxTotalBytes?: number;
  readonly extensions?: readonly string[];
}

export interface InboundDropHandler {
  handleTauriEvent(evt: TauriDropEvent): Promise<InboundSummary>;
  handleDomDrop(domPaths: readonly string[]): Promise<InboundSummary>;
}

/**
 * Build the ingestion pipeline. `onBatch` fires once per drop with the
 * accepted PlannedDrops (only when at least one path survives planning).
 */
export function createInboundDrop(
  onBatch: (batch: readonly PlannedDrop[]) => void,
  options: InboundPlanOptions,
): InboundDropHandler {
  const plan = async (paths: readonly string[]): Promise<InboundSummary> => {
    const result = await planDrop(paths, options);
    if (result.accepted.length > 0) onBatch(result.accepted);
    return { ignored: false, accepted: result.accepted.length, rejected: result.rejected.length };
  };
  return {
    async handleTauriEvent(evt) {
      if (evt.type !== "drop") return { ignored: true, accepted: 0, rejected: 0 };
      return plan(evt.paths);
    },
    handleDomDrop(domPaths) {
      return plan(domPaths);
    },
  };
}

/**
 * Pull filesystem paths out of a DOM DataTransfer. Chromium-based
 * webviews expose `File.path`; elsewhere fall back to text/uri-list
 * (file:// URLs only) so the Vite dev browser can still demo a drop.
 * Returns [] when the transfer carries no usable paths (e.g. raw remote
 * URLs), which planDrop then rejects nothing on.
 */
export function extractDomPaths(dt: DataTransfer): string[] {
  const fromFiles: string[] = [];
  for (const file of Array.from(dt.files)) {
    const withPath = file as File & { path?: string };
    if (typeof withPath.path === "string" && withPath.path.length > 0) fromFiles.push(withPath.path);
  }
  if (fromFiles.length > 0) return fromFiles;
  const uriList = dt.getData("text/uri-list");
  if (uriList.length === 0) return [];
  const paths: string[] = [];
  for (const line of uriList.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed.length === 0 || trimmed.startsWith("#")) continue;
    if (!trimmed.startsWith("file://")) continue;
    let pathname = trimmed.slice("file://".length);
    if (!pathname.startsWith("/")) {
      // file://host/path — drop the authority section.
      const slash = pathname.indexOf("/");
      pathname = slash >= 0 ? pathname.slice(slash) : "/";
    }
    try {
      pathname = decodeURIComponent(pathname);
    } catch {
      // Keep the raw escape sequence when it is not valid URI encoding.
    }
    paths.push(pathname);
  }
  return paths;
}

function normalizeTauriPayload(payload: DragDropEvent): TauriDropEvent {
  switch (payload.type) {
    case "enter":
      return { type: "enter", position: { x: payload.position.x, y: payload.position.y }, paths: payload.paths };
    case "drop":
      return { type: "drop", position: { x: payload.position.x, y: payload.position.y }, paths: payload.paths };
    case "over":
      return { type: "over", position: { x: payload.position.x, y: payload.position.y }, paths: [] };
    case "leave":
      // Tauri's leave payload carries no position; report the origin.
      return { type: "leave", position: { x: 0, y: 0 }, paths: [] };
  }
}

/**
 * Subscribe to the current webview's native drag-drop events. The Tauri
 * module is dynamic-imported; in plain browsers (and jsdom) the import
 * or getCurrentWebview() fails and this no-ops with a console.warn so
 * the DOM fallback stays the only active path. Returns an unsubscribe
 * function; safe to call before the async subscription settles.
 */
export function subscribeTauriDrop(handler: (evt: TauriDropEvent) => void): () => void {
  let cancelled = false;
  let unlisten: (() => void) | undefined;
  import("@tauri-apps/api/webview")
    .then((mod) =>
      mod.getCurrentWebview().onDragDropEvent((event) => {
        if (!cancelled) handler(normalizeTauriPayload(event.payload));
      }),
    )
    .then((off) => {
      if (cancelled) off();
      else unlisten = off;
    })
    .catch((err: unknown) => {
      console.warn(
        "[dragdrop] Tauri drag-drop subscription unavailable; DOM fallback remains active:",
        err,
      );
    });
  return () => {
    cancelled = true;
    if (unlisten) unlisten();
  };
}

export interface FileDropTargetOptions {
  readonly fs: DropFs;
  readonly onBatch: (batch: readonly PlannedDrop[]) => void;
  readonly maxBytesPerFile?: number;
  readonly maxItems?: number;
  readonly maxTotalBytes?: number;
  readonly extensions?: readonly string[];
  /** Set false to suspend both subscriptions. Default true. */
  readonly enabled?: boolean;
}

/**
 * Wire a drop target: Tauri native events plus DOM dragover/drop on the
 * referenced element (dragover is preventDefault()ed — without it the
 * browser refuses the drop). fs/budget knobs are mount-time; onBatch is
 * always the latest render's callback. Cleans up both paths on unmount.
 */
export function useFileDropTarget(
  ref: RefObject<HTMLElement | null>,
  options: FileDropTargetOptions,
): void {
  const latest = useRef(options);
  useEffect(() => {
    latest.current = options;
  });
  useEffect(() => {
    if (options.enabled === false) return undefined;
    const target = ref.current;
    if (!target) return undefined;
    const handler = createInboundDrop((batch) => latest.current.onBatch(batch), {
      fs: options.fs,
      maxBytesPerFile: options.maxBytesPerFile,
      maxItems: options.maxItems,
      maxTotalBytes: options.maxTotalBytes,
      extensions: options.extensions,
    });
    const unsubscribeTauri = subscribeTauriDrop((evt) => {
      void handler.handleTauriEvent(evt);
    });
    const onDragOver = (event: DragEvent) => {
      event.preventDefault();
    };
    const onDrop = (event: DragEvent) => {
      event.preventDefault();
      if (event.dataTransfer) {
        void handler.handleDomDrop(extractDomPaths(event.dataTransfer));
      }
    };
    target.addEventListener("dragover", onDragOver);
    target.addEventListener("drop", onDrop);
    return () => {
      unsubscribeTauri();
      target.removeEventListener("dragover", onDragOver);
      target.removeEventListener("drop", onDrop);
    };
    // fs/budgets are captured at mount; onBatch reaches the latest render via latest.current.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref, options.enabled]);
}

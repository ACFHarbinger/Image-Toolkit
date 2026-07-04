/**
 * Typed message contract between content scripts, popup/options pages, and
 * the background service worker (§7.2). All runtime messages are members of
 * this discriminated union.
 */

export interface DownloadImageMsg {
  action: "download_image";
  src: string;
  /** URL of the page the image was captured from (provenance / site rules). */
  pageUrl?: string;
}

export interface ScanDupTabsMsg {
  action: "scan_dup_tabs";
}

export interface ClearDupTabsMsg {
  action: "clear_dup_tabs";
}

export interface CloseDupTabsMsg {
  action: "close_dup_tabs";
  /** Tab ids to close (all duplicates except the kept tab per set). */
  tabIds: number[];
}

export interface FocusTabMsg {
  action: "focus_tab";
  tabId: number;
  windowId: number;
}

/** Popup → content script: download every image/video on the page (§7.9A). */
export interface DownloadAllMediaMsg {
  action: "download_all_media";
}

/** Popup → content script: enter click-to-select overlay mode (§7.9B). */
export interface StartSelectionOverlayMsg {
  action: "start_selection_overlay";
}

/** Content script → background: batch-download collected URLs (§7.9). */
export interface DownloadBatchMsg {
  action: "download_batch";
  urls: string[];
  pageUrl: string;
}

/** Response to DownloadAllMediaMsg / StartSelectionOverlayMsg. */
export interface PageCaptureResponse {
  ok: boolean;
  images?: number;
  videos?: number;
  error?: string;
}

export type ExtensionMessage =
  | DownloadImageMsg
  | ScanDupTabsMsg
  | ClearDupTabsMsg
  | CloseDupTabsMsg
  | FocusTabMsg
  | DownloadAllMediaMsg
  | StartSelectionOverlayMsg
  | DownloadBatchMsg;

/** One duplicate set: ≥2 tabs sharing the same normalized URL. */
export interface DupTabSet {
  url: string;
  tabs: Array<{
    id: number;
    windowId: number;
    title: string;
    favIconUrl?: string;
  }>;
}

export interface ScanDupTabsResult {
  sets: DupTabSet[];
  totalDuplicates: number;
  /** True when highlighting used Chromium tab groups (vs popup-only). */
  grouped: boolean;
}

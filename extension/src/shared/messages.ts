/**
 * Typed message contract between content scripts, popup/options pages, and
 * the background service worker (§7.2). All runtime messages are members of
 * this discriminated union.
 */

export interface DownloadImageMsg {
  action: "download_image";
  src: string;
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

export type ExtensionMessage =
  | DownloadImageMsg
  | ScanDupTabsMsg
  | ClearDupTabsMsg
  | CloseDupTabsMsg
  | FocusTabMsg;

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

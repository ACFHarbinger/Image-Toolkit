/**
 * Background service worker (MV3).
 *
 * - Owns the "Save to selected directory" context-menu item.
 * - Downloads images into Downloads/<targetFolder>/ (uniquified).
 * - Routes typed runtime messages from content scripts and the popup.
 */
import { api, setActionBadge, storageGet, storageSet } from "./shared/api";
import { loadSettings } from "./shared/settings";
import { buildFilename, resolveFolder } from "./shared/naming";
import {
  dupCheck,
  ingest,
  findSimilar,
  BridgeError,
  type DupCheckResult,
  type SimilarResult,
} from "./shared/bridge";
import { parseImageMetadata } from "./shared/imageMeta";
import type { ExtensionMessage, ResolveContextImageResponse } from "./shared/messages";

const MENU_ID = "save-to-custom-folder";
const SAVE_PROFILE_MENU_ID = "save-to-profile";
const DUP_CHECK_MENU_ID = "dup-check";
const INGEST_MENU_ID = "send-to-app";
const SIMILAR_MENU_ID = "find-similar";
const INSPECT_MENU_ID = "inspect-metadata";
const FRAME_MENU_ID = "capture-frame";
const BURST_MENU_ID = "capture-frame-burst";
const SEARCH_MENU_ID = "reverse-search";

/** Reverse-image-search services (§7.16B). URL gets the image URL appended. */
const SEARCH_SERVICES: Array<{ id: string; title: string; url: string }> = [
  { id: "saucenao", title: "SauceNAO", url: "https://saucenao.com/search.php?url=" },
  { id: "tracemoe", title: "trace.moe (anime scene)", url: "https://trace.moe/?auto&url=" },
  { id: "lens", title: "Google Lens", url: "https://lens.google.com/uploadbyurl?url=" },
  { id: "iqdb", title: "IQDB", url: "https://iqdb.org/?url=" },
  { id: "tineye", title: "TinEye", url: "https://www.tineye.com/search?url=" },
];

// MV3 service workers can be restarted at any time; (re)create the menus on
// install, on startup, and whenever folder profiles change. `removeAll`
// avoids duplicate-id errors.
async function createContextMenu(): Promise<void> {
  const settings = await loadSettings();
  api.contextMenus.removeAll(() => {
    api.contextMenus.create({
      id: MENU_ID,
      title: "Save to selected directory",
      contexts: ["image"],
    });
    // §7.10 folder-profile quick-switch: only worth a submenu once there's
    // more than one profile to pick from.
    const profiles = (settings.folderProfiles ?? []).filter(Boolean);
    if (profiles.length > 1) {
      api.contextMenus.create({
        id: SAVE_PROFILE_MENU_ID,
        title: "Save to profile ▸",
        contexts: ["image"],
      });
      for (const profile of profiles) {
        api.contextMenus.create({
          id: `${SAVE_PROFILE_MENU_ID}:${profile}`,
          parentId: SAVE_PROFILE_MENU_ID,
          title: profile,
          contexts: ["image"],
        });
      }
    }
    api.contextMenus.create({
      id: DUP_CHECK_MENU_ID,
      title: "Check if already downloaded",
      contexts: ["image"],
    });
    api.contextMenus.create({
      id: INGEST_MENU_ID,
      title: "Send to Image Toolkit",
      contexts: ["image"],
    });
    api.contextMenus.create({
      id: SIMILAR_MENU_ID,
      title: "Find similar in my library",
      contexts: ["image"],
    });
    api.contextMenus.create({
      id: INSPECT_MENU_ID,
      title: "Inspect image metadata",
      contexts: ["image"],
    });
    api.contextMenus.create({
      id: FRAME_MENU_ID,
      title: "Capture video frame",
      contexts: ["video"],
    });
    api.contextMenus.create({
      id: BURST_MENU_ID,
      title: "Capture 5-frame burst",
      contexts: ["video"],
    });
    api.contextMenus.create({
      id: SEARCH_MENU_ID,
      title: "Search image on",
      contexts: ["image"],
    });
    for (const svc of SEARCH_SERVICES) {
      api.contextMenus.create({
        id: `${SEARCH_MENU_ID}:${svc.id}`,
        parentId: SEARCH_MENU_ID,
        title: svc.title,
        contexts: ["image"],
      });
    }
  });
}

api.runtime.onInstalled.addListener(() => void createContextMenu());
if (api.runtime.onStartup) {
  api.runtime.onStartup.addListener(() => void createContextMenu());
}
// Rebuild the "Save to profile ▸" submenu live when the profile list
// changes in options, instead of requiring an extension reload.
api.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && "folderProfiles" in changes) {
    void createContextMenu();
  }
});

/** One entry in the turbo-capture history ring buffer (§7.12), popup-rendered. */
export interface TurboHistoryEntry {
  when: string;
  url: string;
  filename: string;
  status: "ok" | "error";
  error?: string;
}

const TURBO_HISTORY_LIMIT = 25;

/**
 * Record a turbo capture into the `turboHistory` ring buffer and bump the
 * toolbar badge counter (`turboCaptureCount`). Shares the single badge slot
 * with §7.13's duplicate-tab count — see `setActionBadge()`'s docstring.
 */
async function recordTurboCapture(entry: TurboHistoryEntry): Promise<void> {
  const { turboHistory } = await storageGet<{ turboHistory: TurboHistoryEntry[] }>(
    "turboHistory",
  );
  const history = [entry, ...(turboHistory ?? [])].slice(0, TURBO_HISTORY_LIMIT);
  await storageSet({ turboHistory: history });

  const { turboCaptureCount } = await storageGet<{ turboCaptureCount: number }>(
    "turboCaptureCount",
  );
  const count = (turboCaptureCount ?? 0) + 1;
  await storageSet({ turboCaptureCount: count });
  await setActionBadge(String(count), "#5865f2");
}

/**
 * Download an image URL into the folder resolved by site rules (§7.10),
 * naming it via the filename template, and optionally writing a JSON
 * provenance sidecar next to it. Pass *overrideFolder* (from the "Save to
 * profile ▸" submenu) to bypass site-rule resolution for this one save
 * without changing the active default folder. Pass *source: "turbo"* to
 * feed the §7.12 badge counter + history panel.
 */
/**
 * Result of a single `api.downloads.download()` call — used by the grid-
 * preview page (§7.9C) to render a per-item progress/status badge instead of
 * the fire-and-forget behavior plain `download_image`/`download_batch`
 * callers rely on.
 */
export interface DownloadOutcome {
  ok: boolean;
  error?: string;
}

export async function downloadImage(
  imageUrl: string,
  pageUrl?: string,
  suggestedName?: string,
  overrideFolder?: string,
  source?: "turbo" | "manual" | "batch",
): Promise<DownloadOutcome> {
  const settings = await loadSettings();
  const folder = overrideFolder || resolveFolder(settings, pageUrl);
  const relName = suggestedName
    ? suggestedName.replace(/[<>:"\\|?*]/g, "_")
    : buildFilename(settings.filenameTemplate, imageUrl, pageUrl);
  const destinationPath = `${folder}/${relName}`;

  const outcome = await new Promise<DownloadOutcome>((resolve) => {
    api.downloads.download(
      {
        url: imageUrl,
        filename: destinationPath,
        conflictAction: "uniquify",
        saveAs: false,
      },
      (downloadId) => {
        const err = api.runtime.lastError;
        const ok = !err && downloadId !== undefined;
        if (source === "turbo") {
          void recordTurboCapture({
            when: new Date().toISOString(),
            url: imageUrl,
            filename: destinationPath,
            status: ok ? "ok" : "error",
            error: err?.message,
          });
        }
        resolve({ ok, error: err?.message });
      },
    );
  });

  if (settings.saveSidecar) {
    const sidecar = {
      source_url: imageUrl,
      page_url: pageUrl ?? null,
      saved_at: new Date().toISOString(),
    };
    // btoa needs latin-1; escape non-ASCII first.
    const b64 = btoa(unescape(encodeURIComponent(JSON.stringify(sidecar, null, 2))));
    api.downloads.download({
      url: `data:application/json;base64,${b64}`,
      filename: `${destinationPath}.json`,
      conflictAction: "uniquify",
      saveAs: false,
    });
  }

  return outcome;
}

/**
 * §7.11 context-menu correlation: `info.srcUrl` from the context-menu API is
 * often a thumbnail (site lazy-loading, srcset, or a raw `<canvas>` with no
 * `srcUrl` at all). Ask the tab's content script to re-resolve the best URL
 * for the element the user actually right-clicked; falls back to the raw
 * `fallbackUrl` if the tab has no content script (browser-internal pages)
 * or the round trip otherwise fails.
 */
async function resolveContextImageUrl(
  tabId: number | undefined,
  fallbackUrl: string,
): Promise<string> {
  if (tabId === undefined) return fallbackUrl;
  try {
    const resp = (await api.tabs.sendMessage(tabId, {
      action: "resolve_context_image",
      srcUrl: fallbackUrl,
    })) as ResolveContextImageResponse | undefined;
    return resp?.url || fallbackUrl;
  } catch {
    return fallbackUrl;
  }
}

/** Stored under `lastDupCheck` for the popup to render (§7.6). */
export interface LastDupCheck {
  when: string;
  imageUrl: string;
  result?: DupCheckResult;
  error?: string;
}

function notify(title: string, message: string): void {
  try {
    api.notifications.create({
      type: "basic",
      iconUrl: api.runtime.getURL("icons/icon-128.png"),
      title,
      message,
    });
  } catch (err) {
    console.warn("[Image-Toolkit] notification failed:", err);
  }
}

/** Run a duplicate check for an image and surface the outcome (§7.6). */
async function runDupCheck(imageUrl: string): Promise<void> {
  const entry: LastDupCheck = {
    when: new Date().toISOString(),
    imageUrl,
  };
  try {
    const result = await dupCheck(imageUrl);
    entry.result = result;
    if (result.matches.length === 0) {
      notify(
        "No duplicates found",
        `Not in your library (${result.scanned} files checked).`,
      );
    } else {
      const best = result.matches[0];
      notify(
        `${result.matches.length} possible duplicate(s) found`,
        `Closest: ${best.path} (distance ${best.hamming}). ` +
          "Open the extension popup for details.",
      );
    }
  } catch (err) {
    entry.error =
      err instanceof BridgeError ? err.message : String(err);
    notify("Duplicate check failed", entry.error);
  }
  await api.storage.local.set({ lastDupCheck: entry });
}

/** Stored under `lastSimilar` for the popup to render (§7.8). */
export interface LastSimilar {
  when: string;
  imageUrl: string;
  result?: SimilarResult;
  error?: string;
}

/** Run a ranked visual-similarity search and surface the outcome (§7.8). */
async function runSimilar(imageUrl: string): Promise<void> {
  const entry: LastSimilar = {
    when: new Date().toISOString(),
    imageUrl,
  };
  try {
    const result = await findSimilar(imageUrl);
    entry.result = result;
    if (result.results.length === 0) {
      notify(
        "No similar images found",
        `Your library appears empty (${result.scanned} files checked).`,
      );
    } else {
      const best = result.results[0];
      notify(
        `${result.results.length} similar image(s) found`,
        `Closest: ${best.path} (score ${best.score.toFixed(2)}). ` +
          "Open the extension popup for details.",
      );
    }
  } catch (err) {
    entry.error = err instanceof BridgeError ? err.message : String(err);
    notify("Similarity search failed", entry.error);
  }
  await api.storage.local.set({ lastSimilar: entry });
}

/** Ingest an image into the app's library and surface the outcome (§7.7). */
async function runIngest(
  imageUrl: string,
  pageUrl?: string,
  pageTitle?: string,
): Promise<void> {
  try {
    const result = await ingest(imageUrl, pageUrl, pageTitle);
    notify("Sent to Image Toolkit", `Saved as ${result.path}`);
  } catch (err) {
    if (err instanceof BridgeError && err.status === 409) {
      notify("Already in library", err.message);
    } else {
      notify(
        "Send to Image Toolkit failed",
        err instanceof BridgeError ? err.message : String(err),
      );
    }
  }
}

/** Ask the tab's content script to capture video frame(s) (§7.15A). */
async function runFrameCapture(
  tabId: number,
  srcUrl: string | undefined,
  burst: number,
): Promise<void> {
  try {
    const resp = (await api.tabs.sendMessage(tabId, {
      action: "capture_video_frame",
      srcUrl,
      burst,
      intervalMs: 500,
    })) as { ok: boolean; frames?: number; error?: string } | undefined;
    if (!resp?.ok) {
      notify("Frame capture failed", resp?.error ?? "Unknown error.");
    } else if (resp.error) {
      notify(
        "Frame capture incomplete",
        `${resp.frames} frame(s) saved. ${resp.error}`,
      );
    } else if (burst > 1) {
      notify("Frames captured", `${resp.frames} frames saved.`);
    }
  } catch (err) {
    notify("Frame capture failed", String(err));
  }
}

api.contextMenus.onClicked.addListener((info, tab) => {
  const menuId = String(info.menuItemId);

  // Video frame capture works even when the video has no srcUrl (MSE/blob)
  if (menuId === FRAME_MENU_ID || menuId === BURST_MENU_ID) {
    if (tab?.id !== undefined) {
      void runFrameCapture(
        tab.id,
        info.srcUrl,
        menuId === BURST_MENU_ID ? 5 : 1,
      );
    }
    return;
  }

  if (!info.srcUrl) return;

  if (menuId === MENU_ID) {
    void resolveContextImageUrl(tab?.id, info.srcUrl).then((url) =>
      downloadImage(url, info.pageUrl),
    );
    return;
  }
  if (menuId.startsWith(`${SAVE_PROFILE_MENU_ID}:`)) {
    const profile = menuId.slice(SAVE_PROFILE_MENU_ID.length + 1);
    void resolveContextImageUrl(tab?.id, info.srcUrl).then((url) =>
      downloadImage(url, info.pageUrl, undefined, profile),
    );
    return;
  }
  if (menuId === DUP_CHECK_MENU_ID) {
    void runDupCheck(info.srcUrl);
    return;
  }
  if (menuId === INGEST_MENU_ID) {
    void runIngest(info.srcUrl, info.pageUrl, tab?.title);
    return;
  }
  if (menuId === SIMILAR_MENU_ID) {
    void runSimilar(info.srcUrl);
    return;
  }
  if (menuId === INSPECT_MENU_ID) {
    void runInspect(info.srcUrl);
    return;
  }
  if (menuId.startsWith(`${SEARCH_MENU_ID}:`)) {
    const svcId = menuId.slice(SEARCH_MENU_ID.length + 1);
    const svc = SEARCH_SERVICES.find((s) => s.id === svcId);
    if (svc) {
      void api.tabs.create({
        url: svc.url + encodeURIComponent(info.srcUrl),
      });
    }
  }
});

/** Fetch, parse and display an image's embedded metadata (§7.16A). */
async function runInspect(imageUrl: string): Promise<void> {
  let entry: { imageUrl: string; meta: unknown; error?: string };
  try {
    const resp = await fetch(imageUrl);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const bytes = new Uint8Array(await resp.arrayBuffer());
    entry = { imageUrl, meta: await parseImageMetadata(bytes) };
  } catch (err) {
    entry = {
      imageUrl,
      meta: { format: "unknown", text: {}, exif: {} },
      error: String(err),
    };
  }
  await api.storage.local.set({ lastInspect: entry });
  void api.windows.create({
    url: api.runtime.getURL("inspect.html"),
    type: "popup",
    width: 560,
    height: 640,
  });
}

/** Batch-download URLs collected by the bulk grabber (§7.9). */
async function downloadBatch(urls: string[], pageUrl: string): Promise<void> {
  for (const url of urls) {
    try {
      await downloadImage(url, pageUrl);
    } catch (err) {
      console.warn("[Image-Toolkit] batch item failed:", url, err);
    }
  }
  notify(
    "Bulk download started",
    `${urls.length} file(s) queued into your download folder.`,
  );
}

api.runtime.onMessage.addListener(
  (request: ExtensionMessage, sender, sendResponse) => {
    if (request.action === "download_image" && request.src) {
      void downloadImage(
        request.src,
        request.pageUrl ?? sender.tab?.url,
        request.suggestedName,
        undefined,
        request.source,
      );
      return false;
    }
    if (request.action === "download_batch" && request.urls?.length) {
      void downloadBatch(request.urls, request.pageUrl ?? sender.tab?.url ?? "");
      return false;
    }
    if (request.action === "download_gallery_item" && request.url) {
      // §7.9C: unlike the fire-and-forget batch path above, the grid-preview
      // page awaits this per item to drive its own progress/status badge.
      void downloadImage(request.url, request.pageUrl, undefined, undefined, "batch").then(
        sendResponse,
      );
      return true; // async response
    }
    return false;
  },
);

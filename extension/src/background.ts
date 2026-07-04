/**
 * Background service worker (MV3).
 *
 * - Owns the "Save to selected directory" context-menu item.
 * - Downloads images into Downloads/<targetFolder>/ (uniquified).
 * - Routes typed runtime messages from content scripts and the popup.
 */
import { api } from "./shared/api";
import { loadSettings } from "./shared/settings";
import { buildFilename, resolveFolder } from "./shared/naming";
import type { ExtensionMessage } from "./shared/messages";

const MENU_ID = "save-to-custom-folder";
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
// install and on startup. `removeAll` avoids duplicate-id errors.
function createContextMenu(): void {
  api.contextMenus.removeAll(() => {
    api.contextMenus.create({
      id: MENU_ID,
      title: "Save to selected directory",
      contexts: ["image"],
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

api.runtime.onInstalled.addListener(createContextMenu);
if (api.runtime.onStartup) {
  api.runtime.onStartup.addListener(createContextMenu);
}

/**
 * Download an image URL into the folder resolved by site rules (§7.10),
 * naming it via the filename template, and optionally writing a JSON
 * provenance sidecar next to it.
 */
export async function downloadImage(
  imageUrl: string,
  pageUrl?: string,
): Promise<void> {
  const settings = await loadSettings();
  const folder = resolveFolder(settings, pageUrl);
  const relName = buildFilename(settings.filenameTemplate, imageUrl, pageUrl);
  const destinationPath = `${folder}/${relName}`;

  api.downloads.download({
    url: imageUrl,
    filename: destinationPath,
    conflictAction: "uniquify",
    saveAs: false,
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
}

api.contextMenus.onClicked.addListener((info) => {
  if (!info.srcUrl) return;
  const menuId = String(info.menuItemId);

  if (menuId === MENU_ID) {
    void downloadImage(info.srcUrl, info.pageUrl);
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

api.runtime.onMessage.addListener(
  (request: ExtensionMessage, sender, _sendResponse) => {
    if (request.action === "download_image" && request.src) {
      void downloadImage(request.src, request.pageUrl ?? sender.tab?.url);
    }
    return false;
  },
);

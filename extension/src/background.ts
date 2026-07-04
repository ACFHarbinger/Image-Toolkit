/**
 * Background service worker (MV3).
 *
 * - Owns the "Save to selected directory" context-menu item.
 * - Downloads images into Downloads/<targetFolder>/ (uniquified).
 * - Routes typed runtime messages from content scripts and the popup.
 */
import { api } from "./shared/api";
import { loadSettings } from "./shared/settings";
import type { ExtensionMessage } from "./shared/messages";

const MENU_ID = "save-to-custom-folder";

// MV3 service workers can be restarted at any time; (re)create the menu on
// install and on startup. `removeAll` avoids duplicate-id errors.
function createContextMenu(): void {
  api.contextMenus.removeAll(() => {
    api.contextMenus.create({
      id: MENU_ID,
      title: "Save to selected directory",
      contexts: ["image"],
    });
  });
}

api.runtime.onInstalled.addListener(createContextMenu);
if (api.runtime.onStartup) {
  api.runtime.onStartup.addListener(createContextMenu);
}

/** Download an image URL into the configured target folder. */
export async function downloadImage(imageUrl: string): Promise<void> {
  const settings = await loadSettings();
  const folder = settings.targetFolder || "data";

  // Attempt to extract a filename from the URL
  let filename = imageUrl.split("/").pop()?.split("?")[0] ?? "";

  // Fallback if filename is weird or empty
  if (!filename || filename.length < 3 || filename.length > 200) {
    filename = `image_${Date.now()}.jpg`;
  }

  api.downloads.download({
    url: imageUrl,
    filename: `${folder}/${filename}`,
    conflictAction: "uniquify",
    saveAs: false,
  });
}

api.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === MENU_ID && info.srcUrl) {
    void downloadImage(info.srcUrl);
  }
});

api.runtime.onMessage.addListener(
  (request: ExtensionMessage, _sender, _sendResponse) => {
    if (request.action === "download_image" && request.src) {
      void downloadImage(request.src);
    }
    return false;
  },
);

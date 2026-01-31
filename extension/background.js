// Detect environment
const api = (typeof browser !== 'undefined') ? browser : chrome;

// 1. Create the Context Menu Item
api.contextMenus.create({
  id: "save-to-custom-folder",
  title: "Save to selected directory",
  contexts: ["image"]
});

// Helper to handle downloads
const downloadImage = (imageUrl) => {
  // Helper to get storage data supporting both Promise (Firefox) and Callback (Chrome)
  const getStorage = (key) => {
    return new Promise((resolve) => {
      if (typeof browser !== 'undefined') {
        api.storage.local.get(key).then(resolve);
      } else {
        api.storage.local.get(key, resolve);
      }
    });
  };

  getStorage("targetFolder").then((storage) => {
    const folder = storage.targetFolder || "data"; // Default if not set

    // Attempt to extract a filename from the URL
    let filename = imageUrl.split('/').pop().split('?')[0];

    // Fallback if filename is weird or empty
    if (!filename || filename.length < 3 || filename.length > 200) {
      filename = `image_${Date.now()}.jpg`;
    }

    // Combine folder and filename
    const destinationPath = `${folder}/${filename}`;

    // Trigger the download
    api.downloads.download({
      url: imageUrl,
      filename: destinationPath,
      conflictAction: "uniquify",
      saveAs: false
    });
  });
};

// 2. Listen for clicks on the menu
api.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "save-to-custom-folder") {
    downloadImage(info.srcUrl);
  }
});

// 3. Listen for messages from content script (Turbo Mode)
api.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "download_image" && request.src) {
    downloadImage(request.src);
  }
});
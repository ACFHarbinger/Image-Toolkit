// 1. Create the Context Menu Item
browser.contextMenus.create({
  id: "save-to-custom-folder",
  title: "Save to selected directory",
  contexts: ["image"] // Only show on images
});

// 2. Listen for clicks on the menu
browser.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "save-to-custom-folder") {
    
    // Get the user's preferred folder
    const storage = await browser.storage.local.get("targetFolder");
    const folder = storage.targetFolder || "data"; // Default if not set

    // Get the URL of the image clicked
    const imageUrl = info.srcUrl;

    // Attempt to extract a filename from the URL
    let filename = imageUrl.split('/').pop().split('?')[0];
    
    // Fallback if filename is weird or empty
    if (!filename || filename.length < 3 || filename.length > 200) {
      filename = `image_${Date.now()}.jpg`;
    }

    // Combine folder and filename
    // Note: The API treats "folder/filename.jpg" as a relative path inside Downloads
    const destinationPath = `${folder}/${filename}`;

    // Trigger the download
    browser.downloads.download({
      url: imageUrl,
      filename: destinationPath,
      conflictAction: "uniquify" // Rename file if it already exists (image(1).jpg)
    });
  }
});
// electron/preload.js

const { contextBridge, ipcRenderer } = require("electron");

/**
 * Securely expose a limited set of APIs from the main process
 * to the renderer process (your React app).
 */
contextBridge.exposeInMainWorld("electronAPI", {
  /**
   * Asks the main process to open a native "select directory" dialog.
   * Returns a promise that resolves with the selected path or null if cancelled.
   */
  openDirectoryDialog: () => ipcRenderer.invoke("dialog:openDirectory"),

  /**
   * Asks the main process to scan a directory for image files.
   * 'directoryPath' is the full path to scan.
   * Returns a promise that resolves with an array of image objects.
   */
  scanDirectory: (directoryPath) =>
    ipcRenderer.invoke("fs:scanDirectory", directoryPath),

  /**
   * Asks the main process to read an image file and return its Base64 representation.
   * 'filePath' is the full path to the image.
   */
  readImageAsBase64: (filePath) =>
    ipcRenderer.invoke("fs:readImageAsBase64", filePath),

  /**
   * A generic file system operation handler.
   * 'operation' (e.g., 'deleteFile') and 'filePath' are provided.
   */
  performFsOperation: (operation, filePath) =>
    ipcRenderer.invoke("fs:performOperation", operation, filePath),

  // --- You can add other functions you need here ---
  // Example:
  // addImagesToDatabase: (imagePaths) => ipcRenderer.invoke('db:addImages', imagePaths),
});

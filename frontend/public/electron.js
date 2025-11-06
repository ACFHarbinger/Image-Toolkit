// --- ADD 'ipcMain' and 'dialog' to your imports ---
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const url = require('url');

// This function creates the main browser window
function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false, // ← HIDE until React is ready
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    icon: path.join(__dirname, 'public/icons/image_toolkit_icon.png'),
  });

  let retries = 0;
  const maxRetries = 20;

  const tryLoad = () => {
    mainWindow.loadURL('http://localhost:3000').then(() => {
      mainWindow.show();
      mainWindow.focus();
      mainWindow.webContents.openDevTools();
    }).catch(() => {
      if (retries++ < maxRetries) {
        console.log(`React not ready… retry ${retries}/${maxRetries}`);
        setTimeout(tryLoad, 500);
      } else {
        mainWindow.loadURL(`data:text/html,
          <h1 style="text-align:center;margin-top:100px;font-family:sans-serif">
            React Server Failed
          </h1>
          <p style="text-align:center">
            Run: <code>npm run dev</code>
          </p>`);
        mainWindow.show();
      }
     });
  };

  if (process.env.NODE_ENV === 'development') {
    tryLoad();
  } else {
    // PRODUCTION: Correct path inside .asar
    const indexPath = path.join(__dirname, '..', 'build', 'index.html');
    
    mainWindow.loadFile(indexPath)
      .then(() => {
        mainWindow.show();
        mainWindow.focus();
      })
      .catch(err => {
        console.error('Failed to load index.html:', err);
        mainWindow.loadURL('data:text/html,<h1 style="color:red">Build folder missing!</h1><p>Run: <code>npm run build-react</code></p>');
        mainWindow.show();
      });
  }
}

// Electron is ready to create browser windows
// --- MODIFIED THIS BLOCK to register handlers *before* creating the window ---
app.whenReady().then(() => {
  
  // --- ADDED THIS HANDLER ---
  // Listens for 'dialog:openDirectory' from preload.js
  ipcMain.handle('dialog:openDirectory', async () => {
    const { canceled, filePaths } = await dialog.showOpenDialog({
      properties: ['openDirectory'],
    });
    if (canceled || filePaths.length === 0) {
      return null; // User cancelled or selected nothing
    }
    return filePaths[0]; // Return the first selected path
  });
  // --- END OF ADDED HANDLER ---

  createWindow(); // Your original function call
});
// --- END OF MODIFIED BLOCK ---

// Quit when all windows are closed, except on macOS.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
  app.quit();
  }
});

// Reopen a window if the app is activated and no windows are open (macOS specific)
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});


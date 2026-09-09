const { app, BrowserWindow, ipcMain, screen, shell } = require('electron');
const path = require('path');

const WEB_URL = process.env.GENQUNTAA_WEB_URL || 'http://localhost:3000';
let mainWindow;
let overlayWindow;

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    title: 'GenQuantaa AI',
    backgroundColor: '#0b0d0c',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadURL(WEB_URL);
}

function createOverlay() {
  const { width } = screen.getPrimaryDisplay().workAreaSize;
  overlayWindow = new BrowserWindow({
    width: 430,
    height: 280,
    x: Math.max(16, width - 450),
    y: 24,
    frame: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    title: 'GenQuantaa AI Copilot',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  overlayWindow.loadFile(path.join(__dirname, 'overlay.html'));
  overlayWindow.setAlwaysOnTop(true, 'floating');
}

app.whenReady().then(() => {
  ipcMain.handle('open-workspace', () => mainWindow?.show());
  ipcMain.handle('open-live', () => mainWindow?.loadURL(`${WEB_URL}/live`));
  ipcMain.handle('toggle-overlay', () => {
    if (overlayWindow?.isVisible()) overlayWindow.hide();
    else overlayWindow?.show();
    return overlayWindow?.isVisible() ?? false;
  });
  ipcMain.handle('publish-copilot-update', (_event, payload) => {
    if (!overlayWindow || overlayWindow.isDestroyed() || !payload || typeof payload !== 'object') return false;
    overlayWindow.showInactive();
    overlayWindow.webContents.send('copilot-update', payload);
    return true;
  });
  ipcMain.handle('external-link', (_event, url) => {
    if (typeof url === 'string' && /^https?:\/\//.test(url)) shell.openExternal(url);
  });

  createMainWindow();
  createOverlay();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

const { app, BrowserWindow, ipcMain, screen, shell } = require('electron');
const path = require('path');
const { MeetingOrchestrator, detectMeetingProvider, PROVIDERS } = require('./meeting-orchestrator');
const { ScreenContextService } = require('./screen-context');
const WEB_URL = process.env.GENQUNTAA_WEB_URL || 'http://localhost:3000'; const API_URL = process.env.GENQUNTAA_API_URL || 'http://localhost:8000';
let mainWindow; let overlayWindow; let meetingOrchestrator; let screenContext; let redirectingToAuth = false;
function createMainWindow() { mainWindow = new BrowserWindow({ width: 1280, height: 820, minWidth: 960, minHeight: 640, title: 'GenQuantaa AI', backgroundColor: '#0b0d0c', webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true } }); mainWindow.loadURL(WEB_URL); }
function createOverlay() { const { width } = screen.getPrimaryDisplay().workAreaSize; overlayWindow = new BrowserWindow({ width: 430, height: 280, x: Math.max(16, width - 450), y: 24, frame: false, transparent: true, resizable: false, alwaysOnTop: true, skipTaskbar: true, title: 'GenQuantaa AI Copilot', webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true } }); overlayWindow.loadFile(path.join(__dirname, 'overlay.html')); overlayWindow.setAlwaysOnTop(true, 'floating'); }
async function getAuthCookie() { if (!mainWindow || mainWindow.isDestroyed()) return null; try { const cookies = await mainWindow.webContents.session.cookies.get({ url: API_URL, name: 'genquantaa_session' }); const cookie = cookies.find((item) => item.name === 'genquantaa_session' && item.value); return cookie ? `${cookie.name}=${cookie.value}` : null; } catch { return null; } }
async function clearAuthCookie() { try { await mainWindow?.webContents.session.cookies.remove(API_URL, 'genquantaa_session'); } catch { /* session may already be unavailable */ } }
async function requireAuthentication() {
  if (redirectingToAuth) return;
  redirectingToAuth = true;
  try {
    meetingOrchestrator?.stop(false);
    screenContext?.stop();
    await clearAuthCookie();
    if (mainWindow && !mainWindow.isDestroyed()) await mainWindow.loadURL(`${WEB_URL}/auth`);
    overlayWindow?.hide();
  } finally {
    redirectingToAuth = false;
  }
}
function broadcastMeetingState(state) { if (!overlayWindow || overlayWindow.isDestroyed()) return; overlayWindow.webContents.send('meeting-state', state); if (state.active && state.status === 'running') overlayWindow.showInactive(); }
function broadcastScreenState(state) { if (!overlayWindow || overlayWindow.isDestroyed()) return; overlayWindow.webContents.send('screen-context-state', { ...state, sources: state.sources?.map(({ thumbnail, ...source }) => source) || [] }); }
app.whenReady().then(() => {
  ipcMain.handle('open-workspace', () => mainWindow?.show()); ipcMain.handle('open-live', () => mainWindow?.loadURL(`${WEB_URL}/live`));
  ipcMain.handle('toggle-overlay', () => { if (overlayWindow?.isVisible()) overlayWindow.hide(); else overlayWindow?.show(); return overlayWindow?.isVisible() ?? false; });
  ipcMain.handle('publish-copilot-update', (_event, payload) => { if (!overlayWindow || overlayWindow.isDestroyed() || !payload || typeof payload !== 'object') return false; overlayWindow.showInactive(); overlayWindow.webContents.send('copilot-update', payload); return true; });
  ipcMain.handle('external-link', (_event, url) => { if (typeof url === 'string' && /^https?:\/\//.test(url)) shell.openExternal(url); });
  ipcMain.handle('detect-meeting-provider', (_event, meetingUrl) => { const provider = detectMeetingProvider(meetingUrl); return provider ? { id: provider.id, name: provider.name } : null; }); ipcMain.handle('meeting-providers', () => PROVIDERS.map(({ id, name }) => ({ id, name })));
  ipcMain.handle('start-meeting-monitor', async (_event, payload) => { try { return await meetingOrchestrator.start(payload || {}); } catch (error) { return { active: false, status: 'error', error: error instanceof Error ? error.message : 'Meeting orchestration failed' }; } }); ipcMain.handle('stop-meeting-monitor', () => meetingOrchestrator.stop()); ipcMain.handle('meeting-state', () => meetingOrchestrator.getState());
  ipcMain.handle('screen-context-sources', () => screenContext.listSources()); ipcMain.handle('screen-context-start', async (_event, sourceId) => { try { return await screenContext.start(sourceId); } catch (error) { return { active: false, status: 'error', error: error instanceof Error ? error.message : 'Could not start screen context' }; } });
  ipcMain.handle('screen-context-analyze', async () => { try { return await screenContext.analyzeCurrent(); } catch (error) { return { active: screenContext.active, status: 'error', error: error instanceof Error ? error.message : 'Visual analysis failed' }; } });
  ipcMain.handle('screen-context-adaptive', (_event, enabled) => { try { return screenContext.setAdaptive(enabled); } catch (error) { return { active: screenContext.active, status: 'error', error: error instanceof Error ? error.message : 'Could not update adaptive capture' }; } });
  ipcMain.handle('screen-context-sensitivity', (_event, threshold) => { try { return screenContext.setDiffThreshold(threshold); } catch (error) { return { active: screenContext.active, status: 'error', error: error instanceof Error ? error.message : 'Could not update sensitivity' }; } });
  ipcMain.handle('screen-context-continuous-start', async (_event, intervalMs) => { try { return screenContext.startContinuous(intervalMs); } catch (error) { return { active: screenContext.active, status: 'error', error: error instanceof Error ? error.message : 'Could not enable continuous context' }; } });
  ipcMain.handle('screen-context-continuous-stop', () => { screenContext.stopContinuous(); return screenContext.getState(); }); ipcMain.handle('screen-context-stop', () => screenContext.stop()); ipcMain.handle('screen-context-state', () => screenContext.getState());
  createMainWindow(); createOverlay(); meetingOrchestrator = new MeetingOrchestrator({ mainWindow, webUrl: WEB_URL, apiUrl: API_URL, authCookieProvider: getAuthCookie, onAuthRequired: requireAuthentication, onState: broadcastMeetingState }); screenContext = new ScreenContextService({ onState: broadcastScreenState, apiUrl: API_URL, authCookieProvider: getAuthCookie, onAuthRequired: requireAuthentication });
  app.on('before-quit', () => { meetingOrchestrator?.stop(false); screenContext?.stop(); }); app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createMainWindow(); });
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });

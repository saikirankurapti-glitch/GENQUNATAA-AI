const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('genquantaa', {
  openWorkspace: () => ipcRenderer.invoke('open-workspace'),
  openLive: () => ipcRenderer.invoke('open-live'),
  toggleOverlay: () => ipcRenderer.invoke('toggle-overlay'),
  openExternal: (url) => ipcRenderer.invoke('external-link', url),
});

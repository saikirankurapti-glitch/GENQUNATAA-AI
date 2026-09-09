const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('genquantaa', {
  openWorkspace: () => ipcRenderer.invoke('open-workspace'),
  openLive: () => ipcRenderer.invoke('open-live'),
  toggleOverlay: () => ipcRenderer.invoke('toggle-overlay'),
  openExternal: (url) => ipcRenderer.invoke('external-link', url),
  publishCopilotUpdate: (payload) => ipcRenderer.invoke('publish-copilot-update', payload),
  onCopilotUpdate: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on('copilot-update', listener);
    return () => ipcRenderer.removeListener('copilot-update', listener);
  },
});

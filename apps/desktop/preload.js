const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('genquantaa', {
  openWorkspace: () => ipcRenderer.invoke('open-workspace'),
  openLive: () => ipcRenderer.invoke('open-live'),
  toggleOverlay: () => ipcRenderer.invoke('toggle-overlay'),
  openExternal: (url) => ipcRenderer.invoke('external-link', url),
  publishCopilotUpdate: (payload) => ipcRenderer.invoke('publish-copilot-update', payload),
  detectMeetingProvider: (meetingUrl) => ipcRenderer.invoke('detect-meeting-provider', meetingUrl),
  getMeetingProviders: () => ipcRenderer.invoke('meeting-providers'),
  startMeetingMonitor: (payload) => ipcRenderer.invoke('start-meeting-monitor', payload),
  stopMeetingMonitor: () => ipcRenderer.invoke('stop-meeting-monitor'),
  getMeetingState: () => ipcRenderer.invoke('meeting-state'),
  onMeetingState: (callback) => { const listener = (_event, payload) => callback(payload); ipcRenderer.on('meeting-state', listener); return () => ipcRenderer.removeListener('meeting-state', listener); },
  getScreenContextSources: () => ipcRenderer.invoke('screen-context-sources'),
  startScreenContext: (sourceId) => ipcRenderer.invoke('screen-context-start', sourceId),
  analyzeScreenContext: () => ipcRenderer.invoke('screen-context-analyze'),
  stopScreenContext: () => ipcRenderer.invoke('screen-context-stop'),
  getScreenContextState: () => ipcRenderer.invoke('screen-context-state'),
  onScreenContextState: (callback) => { const listener = (_event, payload) => callback(payload); ipcRenderer.on('screen-context-state', listener); return () => ipcRenderer.removeListener('screen-context-state', listener); },
  onCopilotUpdate: (callback) => { const listener = (_event, payload) => callback(payload); ipcRenderer.on('copilot-update', listener); return () => ipcRenderer.removeListener('copilot-update', listener); },
});

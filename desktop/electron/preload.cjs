const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('marassim', Object.freeze({
  config: () => ipcRenderer.invoke('config:get'),
  startServer: (importExisting) => ipcRenderer.invoke('server:start', !!importExisting),
  probe: (url) => ipcRenderer.invoke('server:probe', url),
  pair: () => ipcRenderer.invoke('server:pair'),
  request: (path, options) => ipcRenderer.invoke('api:request', path, options),
  logout: () => ipcRenderer.invoke('session:logout'),
  saveFile: (file) => ipcRenderer.invoke('file:save', file),
  enableReplica: (name) => ipcRenderer.invoke('replica:enable', name),
  syncBackup: () => ipcRenderer.invoke('replica:sync'),
  exportRecoveryKey: () => ipcRenderer.invoke('recovery:export'),
  installTasks: () => ipcRenderer.invoke('tasks:install'),
  resetConnection: () => ipcRenderer.invoke('config:reset'),
}));

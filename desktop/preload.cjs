const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('hamartiaDesktop', Object.freeze({
  restoreBackup: (language) => ipcRenderer.invoke(
    'hamartia:restore-backup',
    language === 'tr' ? 'tr' : 'en',
  ),
}))

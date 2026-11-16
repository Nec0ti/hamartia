const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('hamartiaDesktop', Object.freeze({
  restoreBackup: (language) => ipcRenderer.invoke(
    'hamartia:restore-backup',
    language === 'tr' ? 'tr' : 'en',
  ),
  social: Object.freeze({
    signIn: () => ipcRenderer.invoke('hamartia:social:sign-in'),
    getProfile: () => ipcRenderer.invoke('hamartia:social:get-profile'),
    patchProfile: (patch) => ipcRenderer.invoke('hamartia:social:patch-profile', patch),
    signOut: () => ipcRenderer.invoke('hamartia:social:sign-out'),
  }),
  chatgpt: Object.freeze({
    status: () => ipcRenderer.invoke('hamartia:chatgpt:status'),
    signIn: () => ipcRenderer.invoke('hamartia:chatgpt:sign-in'),
    signOut: () => ipcRenderer.invoke('hamartia:chatgpt:sign-out'),
    forgetAccount: () => ipcRenderer.invoke('hamartia:chatgpt:forget-account'),
    recoverUnreadableCredentials: (confirmed) => ipcRenderer.invoke('hamartia:chatgpt:recover-unreadable-credentials', confirmed),
    models: () => ipcRenderer.invoke('hamartia:chatgpt:models'),
    openUsage: () => ipcRenderer.invoke('hamartia:chatgpt:open-usage'),
    chat: (payload) => ipcRenderer.invoke('hamartia:chatgpt:chat', payload),
    cancel: (requestId) => ipcRenderer.invoke('hamartia:chatgpt:cancel', requestId),
    onDelta: (callback) => {
      const listener = (_event, data) => callback(data)
      ipcRenderer.on('hamartia:chatgpt-delta', listener)
      return () => ipcRenderer.removeListener('hamartia:chatgpt-delta', listener)
    },
  }),
}))

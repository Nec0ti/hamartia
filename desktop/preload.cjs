const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('hamartiaDesktop', Object.freeze({
  restoreBackup: (language) => ipcRenderer.invoke(
    'hamartia:restore-backup',
    language === 'tr' ? 'tr' : 'en',
  ),
  social: Object.freeze({
    signIn: (agreementVersion) => ipcRenderer.invoke('hamartia:social:sign-in', agreementVersion),
    getProfile: (agreementVersion) => ipcRenderer.invoke('hamartia:social:get-profile', agreementVersion),
    patchProfile: (patch, agreementVersion) => ipcRenderer.invoke('hamartia:social:patch-profile', patch, agreementVersion),
    listForumPosts: (agreementVersion) => ipcRenderer.invoke('hamartia:social:list-forum-posts', agreementVersion),
    createForumPost: (post, agreementVersion) => ipcRenderer.invoke('hamartia:social:create-forum-post', post, agreementVersion),
    getModerationQueue: (agreementVersion) => ipcRenderer.invoke('hamartia:social:get-moderation-queue', agreementVersion),
    moderateForumPost: (postId, decision, agreementVersion) => ipcRenderer.invoke('hamartia:social:moderate-forum-post', postId, decision, agreementVersion),
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

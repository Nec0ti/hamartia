const { randomUUID } = require('node:crypto')

const CHATGPT_CHANNEL = 'hamartia:chatgpt'
const CHATGPT_DELTA_CHANNEL = 'hamartia:chatgpt-delta'

function registerChatGPTIpc({ ipcMain, chatgpt, shell, getBackendUrl, createRequestId = randomUUID }) {
  const activeChats = new Map()

  function isTrustedSender(event) {
    try {
      return Boolean(getBackendUrl() && event.senderFrame?.parent === null && new URL(event.senderFrame.url).origin === getBackendUrl())
    } catch {
      return false
    }
  }

  function trustedHandler(name, handler) {
    ipcMain.handle(`${CHATGPT_CHANNEL}:${name}`, async (event, ...args) => {
      if (!isTrustedSender(event)) throw new Error('Untrusted app window.')
      return handler(event, ...args)
    })
  }

  trustedHandler('status', () => chatgpt.status())
  trustedHandler('sign-in', () => chatgpt.signIn())
  trustedHandler('sign-out', () => chatgpt.signOut())
  trustedHandler('forget-account', () => chatgpt.forgetAccount())
  trustedHandler('recover-unreadable-credentials', (_event, confirmed) => chatgpt.recoverUnreadableCredentials(confirmed))
  trustedHandler('models', () => chatgpt.models())
  trustedHandler('open-usage', () => shell.openExternal('https://chatgpt.com/settings/usage'))
  trustedHandler('chat', async (event, payload) => {
    if (!payload || payload.consent !== true) throw new Error('Confirm that this request and a short study summary may be sent to OpenAI.')
    const requestId = typeof payload.requestId === 'string' && /^[\w-]{20,80}$/.test(payload.requestId) ? payload.requestId : createRequestId()
    activeChats.set(requestId, event.sender.id)
    try {
      return await chatgpt.chat({ message: payload.message, model: payload.model, language: payload.language, workflow: payload.workflow, messages: payload.messages, scoring_profile_id: payload.scoring_profile_id, scoring_profile_version: payload.scoring_profile_version, expected_evidence_field: payload.expected_evidence_field, requestId }, (id, delta) => {
        if (activeChats.get(id) === event.sender.id && !event.sender.isDestroyed()) event.sender.send(CHATGPT_DELTA_CHANNEL, { requestId: id, delta })
      })
    } finally {
      activeChats.delete(requestId)
    }
  })
  trustedHandler('cancel', (event, requestId) => {
    if (typeof requestId === 'string' && activeChats.get(requestId) === event.sender.id) chatgpt.cancel(requestId)
    return { cancelled: true }
  })
}

module.exports = { registerChatGPTIpc }

const assert = require('node:assert/strict')
const test = require('node:test')
const { registerChatGPTIpc } = require('../chatgptIpc.cjs')

function setup() {
  const handlers = new Map()
  const calls = { chat: 0, cancel: [], sent: [] }
  const ipcMain = { handle: (name, handler) => handlers.set(name, handler) }
  let completeChat
  const chatgpt = {
    status: async () => ({ connected: false }),
    signIn: async () => ({}),
    signOut: async () => ({}),
    forgetAccount: async () => ({}),
    recoverUnreadableCredentials: async () => ({}),
    models: async () => [],
    chat: async (_payload, onDelta) => {
      calls.chat += 1
      completeChat = () => {
        onDelta('request-012345678901', 'safe delta')
        return { status: 'completed' }
      }
      return await new Promise((resolve) => { completeChat.resolve = resolve; completeChat.onDelta = onDelta })
    },
    cancel: (id) => calls.cancel.push(id),
  }
  registerChatGPTIpc({
    ipcMain,
    chatgpt,
    shell: { openExternal: async () => {} },
    getBackendUrl: () => 'http://127.0.0.1:4455',
    createRequestId: () => 'generated-request-0123456789',
  })
  function event({ origin = 'http://127.0.0.1:4455', isMainFrame = true, senderId = 7 } = {}) {
    return {
      senderFrame: { url: `${origin}/`, parent: isMainFrame ? null : {} },
      sender: { id: senderId, isDestroyed: () => false, send: (...args) => calls.sent.push(args) },
    }
  }
  return { handlers, calls, event, finishChat: () => completeChat.resolve(completeChat()) }
}

test('ChatGPT IPC rejects off-origin and subframe senders before provider access', async () => {
  const testApp = setup()
  const chat = testApp.handlers.get('hamartia:chatgpt:chat')
  await assert.rejects(chat(testApp.event({ origin: 'https://attacker.example' }), { consent: true }), /Untrusted app window/)
  await assert.rejects(chat(testApp.event({ isMainFrame: false }), { consent: true }), /Untrusted app window/)
  assert.equal(testApp.calls.chat, 0)
})

test('ChatGPT IPC requires explicit consent before the provider is called', async () => {
  const testApp = setup()
  const chat = testApp.handlers.get('hamartia:chatgpt:chat')
  await assert.rejects(chat(testApp.event(), { message: 'A question' }), /Confirm that this request/)
  await assert.rejects(chat(testApp.event(), { message: 'A question', consent: false }), /Confirm that this request/)
  assert.equal(testApp.calls.chat, 0)
})

test('only the webContents that started a ChatGPT request can cancel it or receive deltas', async () => {
  const testApp = setup()
  const event = testApp.event({ senderId: 7 })
  const pending = testApp.handlers.get('hamartia:chatgpt:chat')(event, { requestId: 'request-012345678901', consent: true, message: 'A question' })
  await new Promise((resolve) => setImmediate(resolve))
  const cancel = testApp.handlers.get('hamartia:chatgpt:cancel')
  await cancel(testApp.event({ senderId: 9 }), 'request-012345678901')
  assert.deepEqual(testApp.calls.cancel, [])
  await cancel(event, 'request-012345678901')
  assert.deepEqual(testApp.calls.cancel, ['request-012345678901'])
  testApp.finishChat()
  assert.deepEqual(await pending, { status: 'completed' })
  assert.equal(testApp.calls.sent.length, 1)
})

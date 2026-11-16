const assert = require('node:assert/strict')
const test = require('node:test')
const { registerChatGPTIpc } = require('../chatgptIpc.cjs')

function setup() {
  const handlers = new Map()
  const calls = { chat: 0, payload: null, cancel: [], sent: [] }
  const ipcMain = { handle: (name, handler) => handlers.set(name, handler) }
  let completeChat
  const chatgpt = {
    status: async () => ({ connected: false }),
    signIn: async () => ({}),
    signOut: async () => ({}),
    forgetAccount: async () => ({}),
    recoverUnreadableCredentials: async () => ({}),
    models: async () => [],
    chat: async (payload, onDelta) => {
      calls.chat += 1
      calls.payload = payload
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

test('ChatGPT IPC forwards the bounded create-only workflow and canonical language', async () => {
  const testApp = setup()
  const messages = ['date: 2026-11-15']
  const pending = testApp.handlers.get('hamartia:chatgpt:chat')(testApp.event(), {
    requestId: 'request-012345678901', consent: true, message: messages[0], model: 'model-a', language: 'tr',
    workflow: 'practice-entry', messages, scoring_profile_id: 'profile_host-choice', scoring_profile_version: 4,
  })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(testApp.calls.payload.workflow, 'practice-entry')
  assert.equal(testApp.calls.payload.language, 'tr')
  assert.deepEqual(testApp.calls.payload.messages, messages)
  assert.equal(testApp.calls.payload.scoring_profile_id, 'profile_host-choice')
  assert.equal(testApp.calls.payload.scoring_profile_version, 4)
  testApp.finishChat()
  await pending
})

test('ChatGPT IPC forwards the host-selected field hint and opaque signed learning-evidence state', async () => {
  const testApp = setup()
  const messages = ['I completed reading chapter 2.']
  const stateToken = 'opaque-host-signed-state-token'
  const pending = testApp.handlers.get('hamartia:chatgpt:chat')(testApp.event(), {
    requestId: 'request-learning-012345', consent: true, message: messages[0], model: 'model-a', language: 'en',
    workflow: 'learning-evidence-entry', messages, expected_evidence_field: 'subject', state_token: stateToken,
  })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(testApp.calls.payload.workflow, 'learning-evidence-entry')
  assert.equal(testApp.calls.payload.expected_evidence_field, 'subject')
  assert.equal(testApp.calls.payload.state_token, stateToken)
  assert.deepEqual(testApp.calls.payload.messages, messages)
  testApp.finishChat()
  await pending
})

test('ChatGPT IPC forwards the host-selected exam field, profile, and opaque signed state', async () => {
  const testApp = setup()
  const messages = ['2026-11-16']
  const examStateToken = 'opaque-exam-state-token'
  const pending = testApp.handlers.get('hamartia:chatgpt:chat')(testApp.event(), {
    requestId: 'request-exam-0123456789', consent: true, message: messages[0], model: 'model-a', language: 'tr',
    workflow: 'exam-entry', messages, expected_exam_field: 'date', exam_state_token: examStateToken,
    scoring_profile_id: 'profile_host-choice', scoring_profile_version: 7,
  })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(testApp.calls.payload.workflow, 'exam-entry')
  assert.equal(testApp.calls.payload.language, 'tr')
  assert.equal(testApp.calls.payload.expected_exam_field, 'date')
  assert.equal(testApp.calls.payload.exam_state_token, examStateToken)
  assert.equal(testApp.calls.payload.scoring_profile_id, 'profile_host-choice')
  assert.equal(testApp.calls.payload.scoring_profile_version, 7)
  assert.deepEqual(testApp.calls.payload.messages, messages)
  testApp.finishChat()
  await pending
})

test('ChatGPT IPC forwards the sectioned-exam host field and separate opaque state', async () => {
  const testApp = setup()
  const messages = ['TYT']
  const stateToken = 'opaque-sectioned-state-token'
  const pending = testApp.handlers.get('hamartia:chatgpt:chat')(testApp.event(), {
    requestId: 'request-sectioned-0123456789', consent: true, message: 'TYT', model: 'model-a', language: 'en',
    workflow: 'sectioned-exam-entry', messages, expected_sectioned_exam_field: 'exam_type', sectioned_exam_state_token: stateToken,
    scoring_profile_id: 'host-profile', scoring_profile_version: 3,
  })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(testApp.calls.payload.workflow, 'sectioned-exam-entry')
  assert.equal(testApp.calls.payload.expected_sectioned_exam_field, 'exam_type')
  assert.equal(testApp.calls.payload.sectioned_exam_state_token, stateToken)
  assert.deepEqual(testApp.calls.payload.messages, messages)
  testApp.finishChat()
  await pending
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

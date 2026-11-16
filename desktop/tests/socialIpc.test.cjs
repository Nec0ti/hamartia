const assert = require('node:assert/strict')
const http = require('node:http')
const test = require('node:test')
const { registerSocialIpc, parseSocialApiOrigin } = require('../socialIpc.cjs')

const ID_TOKEN = 'header.payload.signature'
const PROFILE = { nickname: 'Mavi', age: 17, nickname_public: false }

function setup({ apiOrigin = 'https://social.example.test', fetchImpl } = {}) {
  const handlers = new Map()
  const requests = []
  const authCalls = { signIn: 0, signOut: 0, getIdToken: 0 }
  const auth = {
    signIn: async () => { authCalls.signIn += 1; return { status: 'signedIn' } },
    signOut: async () => { authCalls.signOut += 1; return { status: 'signedOut' } },
    getIdToken: async () => { authCalls.getIdToken += 1; return ID_TOKEN },
  }
  const ipcMain = { handle: (channel, handler) => handlers.set(channel, handler) }
  registerSocialIpc({
    ipcMain,
    auth,
    apiOrigin,
    allowLoopbackHttp: true,
    getBackendUrl: () => 'http://127.0.0.1:41234/',
    fetchImpl: fetchImpl || (async (url, options) => {
      requests.push({ url: String(url), options })
      return { ok: true, json: async () => PROFILE }
    }),
  })
  const event = ({ origin = 'http://127.0.0.1:41234', mainFrame = true } = {}) => ({
    senderFrame: { url: `${origin}/`, parent: mainFrame ? null : {} },
  })
  return { handlers, requests, authCalls, event }
}

test('social API origin accepts fixed HTTPS or numeric loopback development origins only', () => {
  assert.equal(parseSocialApiOrigin('https://social.example.test'), 'https://social.example.test')
  assert.equal(parseSocialApiOrigin('http://127.0.0.1:8765', { allowLoopbackHttp: true }), 'http://127.0.0.1:8765')
  assert.equal(parseSocialApiOrigin('http://[::1]:8765', { allowLoopbackHttp: true }), 'http://[::1]:8765')
  for (const invalid of [
    'http://social.example.test',
    'http://localhost:8765',
    'http://0.0.0.0:8765',
    'https://user:password@social.example.test',
    'https://social.example.test/path',
    'https://social.example.test/?query=1',
    'https://social.example.test/#fragment',
  ]) assert.equal(parseSocialApiOrigin(invalid, { allowLoopbackHttp: true }), null, invalid)
  assert.equal(parseSocialApiOrigin('http://127.0.0.1:8765'), null)
})

test('social IPC exposes only sign-in, profile GET/PATCH, and sign-out calls to a trusted top-level frame', async () => {
  const app = setup()
  assert.deepEqual([...app.handlers.keys()].sort(), [
    'hamartia:social:get-profile',
    'hamartia:social:patch-profile',
    'hamartia:social:sign-in',
    'hamartia:social:sign-out',
  ])
  assert.deepEqual(await app.handlers.get('hamartia:social:sign-in')(app.event()), { status: 'signedIn' })
  assert.deepEqual(await app.handlers.get('hamartia:social:get-profile')(app.event()), PROFILE)
  assert.deepEqual(await app.handlers.get('hamartia:social:patch-profile')(app.event(), { nickname: 'Mavi', nickname_public: false }), PROFILE)
  assert.deepEqual(await app.handlers.get('hamartia:social:sign-out')(app.event()), { status: 'signedOut' })
  assert.deepEqual(app.requests.map(({ url, options }) => [url, options.method]), [
    ['https://social.example.test/social/me/profile', 'GET'],
    ['https://social.example.test/social/me/profile', 'PATCH'],
  ])
  assert.equal(app.requests[0].options.headers.authorization, `Bearer ${ID_TOKEN}`)
  assert.equal(app.requests[0].options.redirect, 'error')
  assert.equal(app.requests[0].options.cache, 'no-store')
  assert.equal(app.authCalls.getIdToken, 2)
  assert.equal(app.authCalls.signIn, 1)
  assert.equal(app.authCalls.signOut, 1)
})

test('social IPC rejects untrusted, subframe, unexpected-argument, and malformed-patch requests before auth or fetch', async () => {
  const app = setup()
  const get = app.handlers.get('hamartia:social:get-profile')
  const patch = app.handlers.get('hamartia:social:patch-profile')
  for (const event of [app.event({ origin: 'https://attacker.example' }), app.event({ mainFrame: false })]) {
    await assert.rejects(get(event), /Untrusted app window/)
    await assert.rejects(patch(event, { nickname: 'Mavi' }), /Untrusted app window/)
  }
  await assert.rejects(get(app.event(), ID_TOKEN), /Invalid social request/)
  await assert.rejects(patch(app.event()), /Invalid social request/)
  await assert.rejects(patch(app.event(), { uid: 'attacker' }), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { email: 'private@example.test' }), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { age: 17.5 }), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { age: 121 }), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { nickname: 'x'.repeat(81) }), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { nickname_public: 'true' }), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { avatar_preset: 'https://avatar.example/img.png' }), /Invalid profile update/)
  assert.equal(app.authCalls.getIdToken, 0)
  assert.equal(app.requests.length, 0)
})

test('unconfigured or invalid API origins fail closed without requesting Firebase tokens', async () => {
  const absent = setup({ apiOrigin: '' })
  await assert.rejects(absent.handlers.get('hamartia:social:get-profile')(absent.event()), /not configured/)
  const unsafe = setup({ apiOrigin: 'http://social.example.test' })
  await assert.rejects(unsafe.handlers.get('hamartia:social:get-profile')(unsafe.event()), /not configured/)
  assert.equal(absent.authCalls.getIdToken + unsafe.authCalls.getIdToken, 0)
})

test('social API redirects are blocked and cannot forward the Firebase ID token', async (context) => {
  let redirectedRequests = 0
  const target = http.createServer((_request, response) => {
    redirectedRequests += 1
    response.writeHead(200, { 'content-type': 'application/json' }).end('{}')
  })
  await new Promise((resolve) => target.listen(0, '127.0.0.1', resolve))
  const social = http.createServer((_request, response) => {
    response.writeHead(302, { location: `http://127.0.0.1:${target.address().port}/capture` }).end()
  })
  await new Promise((resolve) => social.listen(0, '127.0.0.1', resolve))
  context.after(async () => {
    await new Promise((resolve) => social.close(resolve))
    await new Promise((resolve) => target.close(resolve))
  })

  const app = setup({ apiOrigin: `http://127.0.0.1:${social.address().port}`, fetchImpl: fetch })
  await assert.rejects(app.handlers.get('hamartia:social:get-profile')(app.event()))
  assert.equal(redirectedRequests, 0)
})

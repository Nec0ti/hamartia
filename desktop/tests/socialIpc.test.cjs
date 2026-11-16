const assert = require('node:assert/strict')
const http = require('node:http')
const test = require('node:test')
const { registerSocialIpc, parseSocialApiOrigin } = require('../socialIpc.cjs')

const ID_TOKEN = 'header.payload.signature'
const PROFILE = { nickname: 'Mavi', age: 17, nickname_public: false }
const AGREEMENT_VERSION = 'v1-reviewed-test'

function setup({ apiOrigin = 'https://social.example.test', agreementVersion = AGREEMENT_VERSION, fetchImpl, idToken = ID_TOKEN } = {}) {
  const handlers = new Map()
  const requests = []
  const authCalls = { signIn: 0, signOut: 0, getIdToken: 0 }
  const auth = {
    signIn: async () => { authCalls.signIn += 1; return { status: 'signedIn' } },
    signOut: async () => { authCalls.signOut += 1; return { status: 'signedOut' } },
    getIdToken: async () => { authCalls.getIdToken += 1; return idToken },
  }
  const ipcMain = { handle: (channel, handler) => handlers.set(channel, handler) }
  registerSocialIpc({
    ipcMain,
    auth,
    apiOrigin,
    agreementVersion,
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
    'hamartia:social:create-forum-post',
    'hamartia:social:get-moderation-queue',
    'hamartia:social:get-profile',
    'hamartia:social:list-forum-posts',
    'hamartia:social:moderate-forum-post',
    'hamartia:social:patch-profile',
    'hamartia:social:sign-in',
    'hamartia:social:sign-out',
  ])
  assert.deepEqual(await app.handlers.get('hamartia:social:sign-in')(app.event(), AGREEMENT_VERSION), { status: 'signedIn' })
  assert.deepEqual(await app.handlers.get('hamartia:social:get-profile')(app.event(), AGREEMENT_VERSION), PROFILE)
  assert.deepEqual(await app.handlers.get('hamartia:social:patch-profile')(app.event(), { nickname: 'Mavi', nickname_public: false }, AGREEMENT_VERSION), PROFILE)
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
  await assert.rejects(get(app.event(), AGREEMENT_VERSION, ID_TOKEN), /Invalid social request/)
  await assert.rejects(patch(app.event()), /Invalid social request/)
  await assert.rejects(patch(app.event(), { uid: 'attacker' }, AGREEMENT_VERSION), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { email: 'private@example.test' }, AGREEMENT_VERSION), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { age: 17.5 }, AGREEMENT_VERSION), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { age: 121 }, AGREEMENT_VERSION), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { nickname: 'x'.repeat(81) }, AGREEMENT_VERSION), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { nickname_public: 'true' }, AGREEMENT_VERSION), /Invalid profile update/)
  await assert.rejects(patch(app.event(), { avatar_preset: 'https://avatar.example/img.png' }, AGREEMENT_VERSION), /Invalid profile update/)
  assert.equal(app.authCalls.getIdToken, 0)
  assert.equal(app.requests.length, 0)
})

test('unaccepted or mismatched agreement versions block sign-in and profile calls before OAuth, Firebase, or API access', async () => {
  const app = setup()
  const signIn = app.handlers.get('hamartia:social:sign-in')
  const get = app.handlers.get('hamartia:social:get-profile')
  const patch = app.handlers.get('hamartia:social:patch-profile')
  for (const version of [undefined, '', 'v0.9-old']) {
    await assert.rejects(signIn(app.event(), version), /reviewed agreement/)
    await assert.rejects(get(app.event(), version), /reviewed agreement/)
    await assert.rejects(patch(app.event(), { nickname: 'Mavi' }, version), /reviewed agreement/)
  }
  assert.deepEqual(app.authCalls, { signIn: 0, signOut: 0, getIdToken: 0 })
  assert.equal(app.requests.length, 0)
  assert.deepEqual(await app.handlers.get('hamartia:social:sign-out')(app.event()), { status: 'signedOut' })
  assert.deepEqual(app.authCalls, { signIn: 0, signOut: 1, getIdToken: 0 })
  assert.equal(app.requests.length, 0)
  assert.deepEqual(await signIn(app.event(), AGREEMENT_VERSION), { status: 'signedIn' })
  assert.equal(app.authCalls.signIn, 1)
})

test('unconfigured or invalid API origins fail closed without requesting Firebase tokens', async () => {
  const absent = setup({ apiOrigin: '' })
  await assert.rejects(absent.handlers.get('hamartia:social:get-profile')(absent.event(), AGREEMENT_VERSION), /not configured/)
  const unsafe = setup({ apiOrigin: 'http://social.example.test' })
  await assert.rejects(unsafe.handlers.get('hamartia:social:get-profile')(unsafe.event(), AGREEMENT_VERSION), /not configured/)
  assert.equal(absent.authCalls.getIdToken + unsafe.authCalls.getIdToken, 0)
})

test('forum IPC validates user content and decisions, then uses fixed protected API routes', async () => {
  const app = setup()
  const call = (name, ...args) => app.handlers.get(`hamartia:social:${name}`)(app.event(), ...args)
  assert.deepEqual(await call('list-forum-posts', AGREEMENT_VERSION), PROFILE)
  assert.deepEqual(await call('create-forum-post', { title: 'Question', body: 'Study note' }, AGREEMENT_VERSION), PROFILE)
  assert.deepEqual(await call('get-moderation-queue', AGREEMENT_VERSION), PROFILE)
  assert.deepEqual(await call('moderate-forum-post', '00000000-0000-0000-0000-000000000001', { decision: 'approved' }, AGREEMENT_VERSION), PROFILE)
  assert.deepEqual(app.requests.map(({ url, options }) => [url, options.method]), [
    ['https://social.example.test/social/forum/posts?limit=50', 'GET'],
    ['https://social.example.test/social/forum/posts', 'POST'],
    ['https://social.example.test/social/forum/moderation?limit=50', 'GET'],
    ['https://social.example.test/social/forum/posts/00000000-0000-0000-0000-000000000001/moderation', 'PATCH'],
  ])
  assert.deepEqual(JSON.parse(app.requests[1].options.body), { title: 'Question', body: 'Study note' })
  for (const invalid of [
    { title: 'Title', body: 'Body', uid: 'attacker' },
    { title: ' ', body: 'Body' },
    { title: 'x'.repeat(121), body: 'Body' },
    { title: 'Title', body: 'x'.repeat(5001) },
  ]) await assert.rejects(call('create-forum-post', invalid, AGREEMENT_VERSION), /Invalid forum post/)
  await assert.rejects(call('moderate-forum-post', 'not-a-uuid', { decision: 'approved' }, AGREEMENT_VERSION), /Invalid moderation request/)
  await assert.rejects(call('moderate-forum-post', '00000000-0000-0000-0000-000000000001', { decision: 'pending' }, AGREEMENT_VERSION), /Invalid moderation request/)
})

test('social profile requests stop before fetch when the in-memory Firebase session is signed out', async () => {
  const app = setup({ idToken: null })
  assert.deepEqual(await app.handlers.get('hamartia:social:get-profile')(app.event(), AGREEMENT_VERSION), { status: 'signedOut' })
  assert.equal(app.requests.length, 0)
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
  await assert.rejects(app.handlers.get('hamartia:social:get-profile')(app.event(), AGREEMENT_VERSION))
  assert.equal(redirectedRequests, 0)
})

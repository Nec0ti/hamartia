const assert = require('node:assert/strict')
const http = require('node:http')
const test = require('node:test')
const { createSocialFirebaseAuth, firebaseConfigFromEnvironment, loadFirebaseSdk } = require('../socialFirebase.cjs')

const ENVIRONMENT = {
  HAMARTIA_FIREBASE_API_KEY: 'test-api-key',
  HAMARTIA_FIREBASE_AUTH_DOMAIN: 'social-test.firebaseapp.com',
  HAMARTIA_FIREBASE_PROJECT_ID: 'social-test',
  HAMARTIA_FIREBASE_APP_ID: '1:123:web:abc',
}

function fakeSdk() {
  const calls = []
  const auth = { currentUser: null }
  const inMemoryPersistence = { type: 'NONE' }
  const sdk = {
    inMemoryPersistence,
    initializeApp: (config, name) => { calls.push(['initializeApp', config, name]); return { config, name } },
    initializeAuth: (app, dependencies) => { calls.push(['initializeAuth', app, dependencies]); return auth },
    GoogleAuthProvider: { credential: (idToken) => { calls.push(['credential', idToken]); return { providerId: 'google.com', idToken } } },
    signInWithCredential: async (_auth, credential) => {
      calls.push(['signInWithCredential', credential])
      auth.currentUser = { uid: 'private-user-id', getIdToken: async () => 'firebase-id-token' }
      return { user: auth.currentUser }
    },
    signOut: async () => { calls.push(['signOut']); auth.currentUser = null },
  }
  return { sdk, auth, calls }
}

test('Firebase public config is accepted only when all required public identifiers are present', () => {
  assert.deepEqual(firebaseConfigFromEnvironment(ENVIRONMENT), {
    apiKey: 'test-api-key',
    authDomain: 'social-test.firebaseapp.com',
    projectId: 'social-test',
    appId: '1:123:web:abc',
  })
  assert.equal(firebaseConfigFromEnvironment({ ...ENVIRONMENT, HAMARTIA_FIREBASE_APP_ID: '' }), null)
})

test('Electron Firebase sign-in exchanges the Google token in main with explicit in-memory persistence', async () => {
  const probe = fakeSdk()
  const oauthCalls = []
  const auth = createSocialFirebaseAuth({
    environment: ENVIRONMENT,
    oauth: { signIn: async () => { oauthCalls.push('signIn'); return 'google-id-token' }, cancel: () => oauthCalls.push('cancel') },
    loadSdk: async () => probe.sdk,
  })
  const signedIn = await auth.signIn()
  assert.deepEqual(signedIn, { status: 'signedIn' })
  assert.equal(JSON.stringify(signedIn).includes('google-id-token'), false)
  assert.equal(JSON.stringify(signedIn).includes('firebase-id-token'), false)
  assert.deepEqual(probe.calls[0], ['initializeApp', firebaseConfigFromEnvironment(ENVIRONMENT), 'hamartia-social'])
  assert.equal(probe.calls[1][0], 'initializeAuth')
  assert.deepEqual(probe.calls[1][2], { persistence: probe.sdk.inMemoryPersistence, popupRedirectResolver: undefined })
  assert.deepEqual(probe.calls.find(([name]) => name === 'credential'), ['credential', 'google-id-token'])
  assert.deepEqual(await auth.getIdToken(), 'firebase-id-token')
  assert.deepEqual(await auth.signOut(), { status: 'signedOut' })
  await assert.rejects(auth.getIdToken(), /Sign in to access/)
  assert.deepEqual(oauthCalls, ['signIn', 'cancel'])
})

test('Firebase sign-in cancellation is normal and incomplete configuration opens no OAuth flow', async () => {
  const probe = fakeSdk()
  let attempts = 0
  const oauth = { signIn: async () => { attempts += 1; return null }, cancel: () => {} }
  const configured = createSocialFirebaseAuth({ environment: ENVIRONMENT, oauth, loadSdk: async () => probe.sdk })
  assert.deepEqual(await configured.signIn(), { status: 'cancelled' })
  assert.equal(probe.calls.some(([name]) => name === 'signInWithCredential'), false)

  const unconfigured = createSocialFirebaseAuth({ environment: {}, oauth, loadSdk: async () => probe.sdk })
  await assert.rejects(unconfigured.signIn(), /not configured/)
  assert.equal(attempts, 1)
})

test('installed Firebase Node SDK supports memory-only Google credential sign-in through a local auth emulator endpoint', async (context) => {
  const requests = []
  const server = http.createServer(async (request, response) => {
    let body = ''
    for await (const chunk of request) body += chunk
    requests.push({ url: request.url, body: JSON.parse(body) })
    const result = request.url.includes('accounts:lookup')
      ? { users: [{ localId: 'node-emulator-user', email: 'private@example.test', displayName: 'Private Name', emailVerified: true }] }
      : { localId: 'node-emulator-user', email: 'private@example.test', displayName: 'Private Name', idToken: 'firebase-emulator-id-token', refreshToken: 'emulator-refresh', expiresIn: '3600', registered: true }
    response.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(result))
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  context.after(async () => {
    const sdk = await loadFirebaseSdk()
    const app = sdk.getApps().find((item) => item.name === 'hamartia-social')
    if (app) await sdk.deleteApp(app)
    await new Promise((resolve) => server.close(resolve))
  })

  const sdk = await loadFirebaseSdk()
  const authModule = await import('firebase/auth')
  const loadSdk = async () => ({
    ...sdk,
    initializeAuth(app, dependencies) {
      const auth = sdk.initializeAuth(app, dependencies)
      authModule.connectAuthEmulator(auth, `http://127.0.0.1:${server.address().port}`, { disableWarnings: true })
      return auth
    },
  })
  const auth = createSocialFirebaseAuth({
    environment: ENVIRONMENT,
    oauth: { signIn: async () => 'mock-google-id-token', cancel: () => {} },
    loadSdk,
  })
  assert.deepEqual(await auth.signIn(), { status: 'signedIn' })
  assert.equal(await auth.getIdToken(), 'firebase-emulator-id-token')
  assert.ok(requests.length >= 1)
  assert.match(requests[0].url, /accounts:signInWithIdp/)
  assert.equal(requests[0].body.postBody, '&id_token=mock-google-id-token&providerId=google.com')
  await auth.signOut()
  await assert.rejects(auth.getIdToken(), /Sign in to access/)
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { createSocialClient } from './socialClient.js'

const ENVIRONMENT = {
  VITE_FIREBASE_API_KEY: 'public-api-key',
  VITE_FIREBASE_AUTH_DOMAIN: 'social-test.firebaseapp.com',
  VITE_FIREBASE_PROJECT_ID: 'social-test',
  VITE_FIREBASE_APP_ID: '1:123:web:abc',
}

function fakeSdk() {
  const calls = []
  const auth = { currentUser: null, emulatorConfig: null }
  const inMemoryPersistence = { type: 'NONE' }
  class GoogleAuthProvider {
    setCustomParameters(parameters) { calls.push(['providerParameters', parameters]) }
  }
  const sdk = {
    inMemoryPersistence,
    browserPopupRedirectResolver: { name: 'browser-popup-resolver' },
    getApps: () => [],
    initializeApp: (config, name) => { calls.push(['initializeApp', config, name]); return { config, name } },
    initializeAuth: (app, dependencies) => { calls.push(['initializeAuth', app, dependencies]); return auth },
    connectAuthEmulator: (instance, url, options) => { calls.push(['connectAuthEmulator', url, options]); instance.emulatorConfig = { url } },
    GoogleAuthProvider,
    signInWithPopup: async (instance, provider) => {
      calls.push(['signInWithPopup', instance, provider])
      instance.currentUser = { email: 'private@example.test', getIdToken: async () => 'firebase-id-token' }
      return { user: instance.currentUser }
    },
    signOut: async (instance) => { calls.push(['signOut']); instance.currentUser = null },
  }
  return { sdk, auth, calls }
}

test('social browser feature remains disabled until explicit public configuration is complete', async () => {
  const client = createSocialClient({ desktopBridge: null, environment: {}, buildEnabled: false })
  assert.equal(client.isEnabled(), false)
  assert.deepEqual(await client.signIn(), { status: 'disabled' })
  assert.deepEqual(await client.getProfile(), { status: 'disabled' })
})

test('web sign-in uses Firebase popup with in-memory persistence and keeps identity tokens out of return values', async () => {
  const probe = fakeSdk()
  const requests = []
  const client = createSocialClient({
    desktopBridge: null,
    environment: ENVIRONMENT,
    buildEnabled: true,
    browserAgreementVersion: 'v1-reviewed-test',
    loadSdk: async () => probe.sdk,
    fetchImpl: async (url, options) => {
      requests.push({ url, options })
      return { ok: true, status: 200, json: async () => ({ nickname: 'Aylin', nickname_public: false }) }
    },
  })

  assert.deepEqual(await client.getProfile(), { status: 'disabled' })
  assert.deepEqual(await client.signIn(), { status: 'disabled' })
  assert.deepEqual(await client.patchProfile({ nickname: 'Aylin' }), { status: 'disabled' })
  assert.deepEqual(await client.signOut(), { status: 'signedOut' })
  assert.equal(probe.calls.length, 0)
  assert.equal(requests.length, 0)
  client.setAgreementAccepted(true)
  assert.deepEqual(await client.getProfile(), { status: 'signedOut' })
  const signIn = await client.signIn()
  assert.deepEqual(signIn, { status: 'signedIn' })
  assert.equal(JSON.stringify(signIn).includes('firebase-id-token'), false)
  assert.deepEqual(probe.calls.find(([name]) => name === 'initializeAuth')[2], {
    persistence: probe.sdk.inMemoryPersistence,
    popupRedirectResolver: probe.sdk.browserPopupRedirectResolver,
  })
  assert.deepEqual(probe.calls.find(([name]) => name === 'providerParameters'), ['providerParameters', { prompt: 'select_account' }])

  const profile = await client.getProfile()
  assert.deepEqual(profile, { status: 'signedIn', profile: { nickname: 'Aylin', nickname_public: false } })
  assert.equal(requests[0].url, '/social/me/profile')
  assert.equal(requests[0].options.method, 'GET')
  assert.equal(requests[0].options.headers.authorization, 'Bearer firebase-id-token')
  assert.equal(requests[0].options.redirect, 'error')
  assert.equal(requests[0].options.cache, 'no-store')

  const patch = { nickname: 'Aylin', nickname_public: false }
  await client.patchProfile(patch)
  assert.equal(requests[1].options.method, 'PATCH')
  assert.deepEqual(JSON.parse(requests[1].options.body), patch)
  assert.deepEqual(await client.signOut(), { status: 'signedOut' })
  assert.equal(probe.auth.currentUser, null)
})

test('web emulator is connected before popup use and unsafe emulator origins fail closed', async () => {
  const probe = fakeSdk()
  const client = createSocialClient({
    desktopBridge: null,
    environment: { ...ENVIRONMENT, VITE_FIREBASE_AUTH_EMULATOR_URL: 'http://127.0.0.1:9099' },
    buildEnabled: true,
    browserAgreementVersion: 'v1-reviewed-test',
    loadSdk: async () => probe.sdk,
  })
  client.setAgreementAccepted(true)
  await client.signIn()
  assert.deepEqual(probe.calls.slice(0, 3).map(([name]) => name), ['initializeApp', 'initializeAuth', 'connectAuthEmulator'])

  assert.throws(() => createSocialClient({
    desktopBridge: null,
    environment: { ...ENVIRONMENT, VITE_FIREBASE_AUTH_EMULATOR_URL: 'http://remote.example:9099' },
    buildEnabled: true,
  }), /loopback HTTP origin/)
})

test('Electron client uses only the four fixed preload methods and never sends an ID token from renderer', async () => {
  const calls = []
  const bridge = {
    signIn: async (...args) => { calls.push(['signIn', ...args]); return { status: 'signedIn' } },
    getProfile: async (...args) => { calls.push(['getProfile', ...args]); return { nickname: 'Aylin' } },
    patchProfile: async (...args) => { calls.push(['patchProfile', ...args]); return { nickname: 'Aylin' } },
    signOut: async (...args) => { calls.push(['signOut', ...args]); return { status: 'signedOut' } },
  }
  const client = createSocialClient({ desktopBridge: bridge, environment: {}, buildEnabled: true, desktopAgreementVersion: 'v1-reviewed-test' })
  assert.deepEqual(await client.signIn(), { status: 'disabled' })
  assert.deepEqual(await client.getProfile(), { status: 'disabled' })
  assert.deepEqual(await client.patchProfile({ nickname: 'Aylin' }), { status: 'disabled' })
  assert.deepEqual(await client.signOut(), { status: 'signedOut' })
  assert.equal(calls.length, 0)
  client.setAgreementAccepted(true)
  assert.deepEqual(await client.signIn(), { status: 'signedIn' })
  assert.deepEqual(await client.getProfile(), { status: 'signedIn', profile: { nickname: 'Aylin' } })
  await client.patchProfile({ nickname: 'Aylin', nickname_public: false })
  await client.signOut()
  assert.deepEqual(calls.map(([name, ...args]) => [name, args.length]), [
    ['signIn', 1], ['getProfile', 1], ['patchProfile', 2], ['signOut', 0],
  ])
  assert.deepEqual(calls.slice(0, 3).map(([name, ...args]) => [name, args.at(-1)]), [
    ['signIn', 'v1-reviewed-test'],
    ['getProfile', 'v1-reviewed-test'],
    ['patchProfile', 'v1-reviewed-test'],
  ])
})

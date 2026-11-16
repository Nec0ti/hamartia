const assert = require('node:assert/strict')
const dns = require('node:dns')
const dgram = require('node:dgram')
const http = require('node:http')
const net = require('node:net')
const { performance } = require('node:perf_hooks')
const tls = require('node:tls')
const { createGoogleDesktopOAuth, TOKEN_URL } = require('../googleDesktopOAuth.cjs')
const { createSocialFirebaseAuth } = require('../socialFirebase.cjs')
const { registerSocialIpc } = require('../socialIpc.cjs')

const PROJECT = 'hamartia-offline-benchmark'
const ENVIRONMENT = {
  HAMARTIA_FIREBASE_API_KEY: 'offline-test-key',
  HAMARTIA_FIREBASE_AUTH_DOMAIN: 'offline.test',
  HAMARTIA_FIREBASE_PROJECT_ID: PROJECT,
  HAMARTIA_FIREBASE_APP_ID: '1:123:web:offline',
}
const REPEATS = 30
const PROFILE_REPEATS = 48
const CONCURRENCY = 12
const CONCURRENT_REPEATS = 8
const UID = 'offline-benchmark-user'
const AGREEMENT_VERSION = 'benchmark-v1'
const GOOGLE_ID_TOKEN = 'google.header.signature'
const FIREBASE_ID_TOKEN = 'firebase.header.signature'
const profile = () => ({
  nickname: null, age: null, school_grade: null, school_class: null, curriculum: null,
  study_preferences: null, study_goals: null, avatar_preset: null,
  nickname_public: false, age_public: false, school_grade_public: false,
  school_class_public: false, curriculum_public: false, study_preferences_public: false,
  study_goals_public: false, avatar_preset_public: false,
})
const isPrivateProfile = (value) => value && value.age === 17
  && typeof value.nickname === 'string'
  && typeof value.study_goals === 'string'
  && value.nickname_public === false
  && Object.entries(value).filter(([key]) => key.endsWith('_public')).every(([, visible]) => visible === false)

function percentile(samples, p) {
  const sorted = [...samples].sort((a, b) => a - b)
  return Number(sorted[Math.ceil(p * sorted.length) - 1].toFixed(3))
}

function summarize(samples) {
  return { p50_ms: percentile(samples, 0.50), p95_ms: percentile(samples, 0.95), p99_ms: percentile(samples, 0.99) }
}

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      server.removeListener('error', reject)
      resolve(server.address().port)
    })
  })
}

function close(server) {
  return new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()))
}

function json(response, status, body) {
  response.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' })
  response.end(JSON.stringify(body))
}

async function requestBody(request) {
  let raw = ''
  for await (const chunk of request) raw += chunk
  return raw ? JSON.parse(raw) : null
}

async function main() {
  const attemptedConnections = []
  const originalConnect = net.Socket.prototype.connect
  const originalDnsLookup = dns.lookup
  const originalTlsConnect = tls.connect
  const originalUdpConnect = dgram.Socket.prototype.connect
  const originalUdpSend = dgram.Socket.prototype.send
  net.Socket.prototype.connect = function guardedConnect(...args) {
    const target = Array.isArray(args[0]) ? args[0][0] : args[0]
    const address = typeof target === 'object' ? target.host || target.hostname || target.path : args[1]
    const ip = typeof address === 'string' && net.isIP(address)
    attemptedConnections.push(address)
    assert.equal(ip, 4, `network guard rejected non-IPv4-loopback destination: ${address}`)
    assert.equal(address, '127.0.0.1', `network guard rejected non-loopback destination: ${address}`)
    return originalConnect.apply(this, args)
  }
  const originalFetch = global.fetch
  global.fetch = (input, ...args) => {
    const url = new URL(typeof input === 'string' ? input : input.url)
    assert.equal(url.protocol, 'http:')
    assert.equal(url.hostname, '127.0.0.1', `network guard rejected fetch destination: ${url.origin}`)
    return originalFetch(input, ...args)
  }
  dns.lookup = (hostname, ...args) => {
    assert.equal(hostname, '127.0.0.1', `network guard rejected DNS name: ${hostname}`)
    return originalDnsLookup(hostname, ...args)
  }
  tls.connect = () => { throw new Error('network guard forbids TLS sockets') }
  dgram.Socket.prototype.connect = () => { throw new Error('network guard forbids UDP sockets') }
  dgram.Socket.prototype.send = () => { throw new Error('network guard forbids UDP sockets') }

  let authRequests = 0
  let authSignIns = 0
  const authServer = http.createServer(async (request, response) => {
    authRequests += 1
    const body = await requestBody(request)
    if (request.method !== 'POST' || !request.url.includes('/identitytoolkit.googleapis.com/v1/accounts:')) {
      return json(response, 404, { error: { message: 'NOT_FOUND' } })
    }
    if (request.url.includes('accounts:signInWithIdp')) {
      authSignIns += 1
      assert.equal(body.postBody, '&id_token=google.header.signature&providerId=google.com')
      return json(response, 200, {
        localId: UID, email: 'private-user@example.invalid', displayName: 'Private Benchmark User',
        idToken: FIREBASE_ID_TOKEN, refreshToken: 'offline-refresh-token', expiresIn: '3600', registered: true,
      })
    }
    if (request.url.includes('accounts:lookup')) {
      return json(response, 200, { users: [{ localId: UID, email: 'private-user@example.invalid', displayName: 'Private Benchmark User', emailVerified: true }] })
    }
    return json(response, 404, { error: { message: 'NOT_FOUND' } })
  })

  const profiles = new Map([[UID, profile()]])
  let profileGets = 0
  let profilePatches = 0
  const profileServer = http.createServer(async (request, response) => {
    if (request.url !== '/social/me/profile' || request.headers.authorization !== `Bearer ${FIREBASE_ID_TOKEN}`) {
      return json(response, 401, { detail: 'Invalid identity' })
    }
    if (request.method === 'GET') {
      profileGets += 1
      return json(response, 200, profiles.get(UID))
    }
    if (request.method !== 'PATCH') return json(response, 405, { detail: 'Method not allowed' })
    profilePatches += 1
    const patch = await requestBody(request)
    if (!patch || Object.keys(patch).some((key) => !['nickname', 'age', 'study_goals', 'nickname_public'].includes(key))) {
      return json(response, 422, { detail: 'Invalid profile update' })
    }
    profiles.set(UID, { ...profiles.get(UID), ...patch })
    return json(response, 200, profiles.get(UID))
  })

  let authPort
  let profilePort
  try {
    authPort = await listen(authServer)
    profilePort = await listen(profileServer)

    let browserCallbacks = 0
    const oauth = createGoogleDesktopOAuth({
      clientId: 'offline-benchmark.apps.googleusercontent.com',
      shell: {
        async openExternal(value) {
          const authorize = new URL(value)
          assert.equal(authorize.origin, 'https://accounts.google.com')
          assert.equal(authorize.searchParams.get('code_challenge_method'), 'S256')
          assert.ok(authorize.searchParams.get('code_challenge'))
          const callback = new URL(authorize.searchParams.get('redirect_uri'))
          assert.equal(callback.hostname, '127.0.0.1')
          const callbackUrl = new URL(callback)
          callbackUrl.search = new URLSearchParams({ state: authorize.searchParams.get('state'), code: 'offline-authorization-code' }).toString()
          await new Promise((resolve, reject) => http.get(callbackUrl, (res) => {
            res.resume()
            res.on('end', () => {
              assert.equal(res.statusCode, 200)
              browserCallbacks += 1
              resolve()
            })
          }).on('error', reject))
        },
      },
      fetchImpl: async (url, options) => {
        assert.equal(url, TOKEN_URL)
        assert.equal(options.method, 'POST')
        const form = new URLSearchParams(options.body)
        assert.equal(form.get('grant_type'), 'authorization_code')
        assert.equal(form.get('code_verifier')?.length, 43)
        return { ok: true, json: async () => ({ id_token: GOOGLE_ID_TOKEN }) }
      },
    })

    const { loadFirebaseSdk } = require('../socialFirebase.cjs')
    const sdk = await loadFirebaseSdk()
    const authModule = await import('firebase/auth')
    const loadSdk = async () => ({
      ...sdk,
      initializeAuth(app, dependencies) {
        const auth = sdk.initializeAuth(app, dependencies)
        authModule.connectAuthEmulator(auth, `http://127.0.0.1:${authPort}`, { disableWarnings: true })
        return auth
      },
    })
    const firebaseAuth = createSocialFirebaseAuth({ environment: ENVIRONMENT, oauth, loadSdk })
    const ipcHandlers = new Map()
    const api = `http://127.0.0.1:${profilePort}`
    registerSocialIpc({
      ipcMain: { handle: (channel, handler) => ipcHandlers.set(channel, handler) },
      auth: firebaseAuth,
      apiOrigin: api,
      agreementVersion: AGREEMENT_VERSION,
      allowLoopbackHttp: true,
      getBackendUrl: () => 'http://127.0.0.1:4173/',
    })
    const event = { senderFrame: { url: 'http://127.0.0.1:4173/', parent: null } }
    const call = (name, ...args) => ipcHandlers.get(`hamartia:social:${name}`)(event, ...args)

    await assert.rejects(call('sign-in'), /Invalid social request/)
    await assert.rejects(call('sign-in', 'stale-benchmark-version'), /reviewed agreement/)
    await assert.rejects(call('get-profile'), /Invalid social request/)
    await assert.rejects(call('patch-profile', { nickname: 'must-not-run' }), /Invalid social request/)
    assert.equal(authSignIns, 0, 'unaccepted agreement must not start OAuth or Firebase')
    assert.equal(authRequests, 0, 'unaccepted agreement must not contact the local Auth Emulator')
    assert.equal(profileGets + profilePatches, 0, 'unaccepted agreement must not access the profile service')

    assert.deepEqual(await call('sign-in', AGREEMENT_VERSION), { status: 'signedIn' })
    assert.equal(await firebaseAuth.getIdToken(), FIREBASE_ID_TOKEN)
    const initial = await call('get-profile', AGREEMENT_VERSION)
    assert.deepEqual(initial, profile())
    assert.equal(JSON.stringify(initial).includes(UID), false)
    assert.equal(JSON.stringify(initial).includes('private-user@example.invalid'), false)

    const signInSamples = []
    for (let index = 0; index < REPEATS + 5; index += 1) {
      const started = performance.now()
      assert.deepEqual(await call('sign-in', AGREEMENT_VERSION), { status: 'signedIn' })
      const elapsed = performance.now() - started
      if (index >= 5) signInSamples.push(elapsed)
    }

    const profileSamples = []
    for (let index = 0; index < PROFILE_REPEATS + 8; index += 1) {
      const expectedNickname = `profile-${index}`
      const started = performance.now()
      const patched = await call('patch-profile', { nickname: expectedNickname, age: 17, nickname_public: false }, AGREEMENT_VERSION)
      assert.equal(patched.nickname, expectedNickname)
      assert.equal(patched.age, 17)
      assert.equal(patched.nickname_public, false)
      const fetched = await call('get-profile', AGREEMENT_VERSION)
      const elapsed = performance.now() - started
      assert.deepEqual(fetched, patched)
      assert.equal(JSON.stringify(fetched).includes(UID), false)
      if (index >= 8) profileSamples.push(elapsed)
    }

    const concurrentSamples = []
    const concurrentNicknames = new Set()
    const concurrentGoals = new Set()
    await Promise.all(Array.from({ length: CONCURRENCY }, async (_, worker) => {
      for (let repeat = 0; repeat < CONCURRENT_REPEATS; repeat += 1) {
        const nickname = `concurrent-${worker}-${repeat}`
        const goal = `goal-${worker}-${repeat}`
        concurrentNicknames.add(nickname)
        concurrentGoals.add(goal)
        const started = performance.now()
        const patched = await call('patch-profile', { nickname, study_goals: goal }, AGREEMENT_VERSION)
        assert.ok(concurrentNicknames.has(patched.nickname) || patched.nickname.startsWith('profile-'))
        assert.ok(concurrentGoals.has(patched.study_goals) || patched.study_goals === null)
        assert.ok(isPrivateProfile(patched))
        const fetched = await call('get-profile', AGREEMENT_VERSION)
        concurrentSamples.push(performance.now() - started)
        assert.ok(concurrentNicknames.has(fetched.nickname) || fetched.nickname.startsWith('profile-'))
        assert.ok(concurrentGoals.has(fetched.study_goals) || fetched.study_goals === null)
        assert.ok(isPrivateProfile(fetched))
      }
    }))

    const finalProfile = await call('get-profile', AGREEMENT_VERSION)
    assert.deepEqual(finalProfile, profiles.get(UID))
    assert.ok(concurrentNicknames.has(finalProfile.nickname))
    assert.ok(concurrentGoals.has(finalProfile.study_goals))
    assert.equal(finalProfile.age, 17)
    assert.ok(authRequests >= authSignIns * 2)
    assert.equal(authSignIns, REPEATS + 6)
    assert.equal(browserCallbacks, authSignIns)
    assert.equal(profileGets, 1 + (PROFILE_REPEATS + 8) + (CONCURRENCY * CONCURRENT_REPEATS) + 1)
    assert.equal(profilePatches, (PROFILE_REPEATS + 8) + (CONCURRENCY * CONCURRENT_REPEATS))

    await call('sign-out')
    assert.equal(await firebaseAuth.getIdToken(), null)
    const apps = sdk.getApps().filter((app) => app.name === 'hamartia-social')
    for (const app of apps) await sdk.deleteApp(app)
    assert.ok(attemptedConnections.length > 0)
    assert.ok(attemptedConnections.every((address) => address === '127.0.0.1'))
    console.log(JSON.stringify({
      benchmark: 'social-auth-offline-client-path',
      firebase_sdk: require('firebase/package.json').version,
      warmup_signins: 5,
      measured_signins: signInSamples.length,
      sign_in_with_credential: summarize(signInSamples),
      warmup_profile_roundtrips: 8,
      measured_profile_roundtrips: profileSamples.length,
      profile_patch_get_roundtrip: summarize(profileSamples),
      concurrent_workers: CONCURRENCY,
      concurrent_patch_get_roundtrips_per_worker: CONCURRENT_REPEATS,
      concurrent_patch_get_roundtrip: summarize(concurrentSamples),
      auth_emulator_requests: authRequests,
      auth_credential_exchanges: authSignIns,
      mock_browser_callbacks: browserCallbacks,
      profile_gets: profileGets,
      profile_patches: profilePatches,
      guarded_loopback_connections: attemptedConnections.length,
      non_loopback_network_attempts: 0,
      real_google_provider_included: false,
      local_ai_included: false,
    }, null, 2))
  } finally {
    global.fetch = originalFetch
    net.Socket.prototype.connect = originalConnect
    dns.lookup = originalDnsLookup
    tls.connect = originalTlsConnect
    dgram.Socket.prototype.connect = originalUdpConnect
    dgram.Socket.prototype.send = originalUdpSend
    if (authServer.listening) await close(authServer)
    if (profileServer.listening) await close(profileServer)
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})

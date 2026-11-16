const assert = require('node:assert/strict')
const test = require('node:test')
const { createHash } = require('node:crypto')
const { createGoogleDesktopOAuth, TOKEN_URL } = require('../googleDesktopOAuth.cjs')

const CLIENT_ID = '1234567890-test.apps.googleusercontent.com'

function setup({ tokenResponse = { id_token: 'header.payload.signature' }, timeoutMs = 3000 } = {}) {
  let authorizeUrl
  const tokenRequests = []
  const oauth = createGoogleDesktopOAuth({
    clientId: CLIENT_ID,
    shell: { openExternal: async (url) => { authorizeUrl = new URL(url) } },
    fetchImpl: async (url, options) => {
      tokenRequests.push({ url: String(url), options })
      return { ok: true, json: async () => tokenResponse }
    },
    timeoutMs,
  })
  return { oauth, tokenRequests, getAuthorizeUrl: () => authorizeUrl }
}

async function waitForAuthorizeUrl(testApp) {
  for (let i = 0; i < 100; i += 1) {
    const url = testApp.getAuthorizeUrl()
    if (url) return url
    await new Promise((resolve) => setTimeout(resolve, 5))
  }
  throw new Error('OAuth authorize URL was not opened')
}

async function callback(url, params, pathname = '/oauth/callback') {
  const target = new URL(pathname, url.searchParams.get('redirect_uri'))
  target.search = new URLSearchParams(params).toString()
  return fetch(target)
}

test('desktop Google OAuth uses loopback, state, PKCE S256, and exchanges only after a matching callback', async () => {
  const testApp = setup()
  const pending = testApp.oauth.signIn()
  const url = await waitForAuthorizeUrl(testApp)
  const redirect = new URL(url.searchParams.get('redirect_uri'))
  assert.equal(url.origin, 'https://accounts.google.com')
  assert.equal(redirect.hostname, '127.0.0.1')
  assert.equal(redirect.pathname, '/oauth/callback')
  assert.match(redirect.port, /^\d+$/)
  assert.equal(url.searchParams.get('code_challenge_method'), 'S256')
  assert.equal(url.searchParams.get('response_type'), 'code')
  assert.equal(url.searchParams.has('client_secret'), false)

  const state = url.searchParams.get('state')
  const challenge = url.searchParams.get('code_challenge')
  const response = await callback(url, { state, code: 'one-time-code' })
  assert.equal(response.status, 200)
  assert.equal(await pending, 'header.payload.signature')
  assert.equal(testApp.tokenRequests.length, 1)
  const { url: tokenUrl, options } = testApp.tokenRequests[0]
  assert.equal(tokenUrl, TOKEN_URL)
  assert.equal(options.redirect, 'error')
  assert.equal(options.cache, 'no-store')
  assert.equal(options.headers['content-type'], 'application/x-www-form-urlencoded')
  const body = new URLSearchParams(options.body)
  assert.equal(body.get('client_id'), CLIENT_ID)
  assert.equal(body.get('code'), 'one-time-code')
  assert.equal(body.get('grant_type'), 'authorization_code')
  assert.equal(body.get('redirect_uri'), redirect.toString())
  assert.equal(body.has('client_secret'), false)
  assert.equal(createHash('sha256').update(body.get('code_verifier')).digest('base64url'), challenge)
  assert.equal(body.get('code_verifier').length, 43)
})

test('desktop Google OAuth cancellation closes the listener without exchanging a code', async () => {
  const testApp = setup()
  const pending = testApp.oauth.signIn()
  const url = await waitForAuthorizeUrl(testApp)
  const callbackUrl = url.searchParams.get('redirect_uri')
  const response = await callback(url, { state: url.searchParams.get('state'), error: 'access_denied' })
  assert.equal(response.status, 200)
  assert.equal(await pending, null)
  assert.equal(testApp.tokenRequests.length, 0)
  await assert.rejects(fetch(new URL(`/oauth/callback?state=${url.searchParams.get('state')}&code=replay`, callbackUrl)))
})

test('desktop Google OAuth rejects wrong state before token exchange', async () => {
  const testApp = setup()
  const pending = testApp.oauth.signIn()
  const rejected = assert.rejects(pending, /state did not match/)
  const url = await waitForAuthorizeUrl(testApp)
  const response = await callback(url, { state: 'attacker-state', code: 'attacker-code' })
  assert.equal(response.status, 400)
  await rejected
  assert.equal(testApp.tokenRequests.length, 0)
})

test('desktop Google OAuth rejects invalid callback paths and repeated code parameters', async () => {
  const badPath = setup()
  const badPathPending = badPath.oauth.signIn()
  const badPathRejected = assert.rejects(badPathPending, /invalid callback/)
  const badPathUrl = await waitForAuthorizeUrl(badPath)
  const badPathResponse = await callback(badPathUrl, { state: badPathUrl.searchParams.get('state'), code: 'code' }, '/wrong')
  assert.equal(badPathResponse.status, 400)
  await badPathRejected
  assert.equal(badPath.tokenRequests.length, 0)

  const repeated = setup()
  const repeatedPending = repeated.oauth.signIn()
  const repeatedRejected = assert.rejects(repeatedPending, /invalid callback/)
  const repeatedUrl = await waitForAuthorizeUrl(repeated)
  const target = new URL(repeatedUrl.searchParams.get('redirect_uri'))
  target.searchParams.set('state', repeatedUrl.searchParams.get('state'))
  target.searchParams.append('code', 'first')
  target.searchParams.append('code', 'second')
  const repeatedResponse = await fetch(target)
  assert.equal(repeatedResponse.status, 400)
  await repeatedRejected
  assert.equal(repeated.tokenRequests.length, 0)

  const mixed = setup()
  const mixedPending = mixed.oauth.signIn()
  const mixedRejected = assert.rejects(mixedPending, /invalid callback/)
  const mixedUrl = await waitForAuthorizeUrl(mixed)
  const mixedResponse = await callback(mixedUrl, { state: mixedUrl.searchParams.get('state'), code: 'code', error: 'access_denied' })
  assert.equal(mixedResponse.status, 400)
  await mixedRejected
  assert.equal(mixed.tokenRequests.length, 0)
})

test('desktop Google OAuth rejects duplicate attempts and can cancel the active listener', async () => {
  const testApp = setup()
  const pending = testApp.oauth.signIn()
  await waitForAuthorizeUrl(testApp)
  await assert.rejects(testApp.oauth.signIn(), /already in progress/)
  testApp.oauth.cancel()
  assert.equal(await pending, null)
  assert.equal(testApp.tokenRequests.length, 0)
})

test('desktop Google OAuth is unavailable without a valid public desktop client ID', async () => {
  let opened = false
  const oauth = createGoogleDesktopOAuth({
    clientId: 'not-a-client-secret',
    shell: { openExternal: async () => { opened = true } },
    fetchImpl: async () => { throw new Error('network must not be called') },
  })
  await assert.rejects(oauth.signIn(), /not configured/)
  assert.equal(opened, false)
})

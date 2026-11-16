const { createHash, randomBytes } = require('node:crypto')
const http = require('node:http')

const AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
const TOKEN_URL = 'https://oauth2.googleapis.com/token'
const CALLBACK_PATH = '/oauth/callback'
const CALLBACK_TIMEOUT_MS = 5 * 60 * 1000

function publicClientId(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9._-]{10,255}\.apps\.googleusercontent\.com$/.test(value)) return null
  return value
}

function createGoogleDesktopOAuth({
  clientId,
  shell,
  fetchImpl = fetch,
  createServer = http.createServer,
  randomBytesImpl = randomBytes,
  timeoutMs = CALLBACK_TIMEOUT_MS,
}) {
  const configuredClientId = publicClientId(clientId)
  let activeAttempt = null

  function cancel() {
    const attempt = activeAttempt
    if (!attempt) return
    activeAttempt = null
    attempt.cancel()
  }

  async function signIn() {
    if (!configuredClientId) throw new Error('Google sign-in is not configured.')
    if (activeAttempt) throw new Error('Google sign-in is already in progress.')

    const state = randomBytesImpl(32).toString('base64url')
    const verifier = randomBytesImpl(32).toString('base64url')
    const challenge = createHash('sha256').update(verifier).digest('base64url')
    let cancellationRequested = false
    let attempt
    activeAttempt = { cancel: () => { cancellationRequested = true; attempt?.cancel() } }
    let result
    try {
      result = await waitForAuthorization({
        state,
        clientId: configuredClientId,
        challenge,
        shell,
        createServer,
        timeoutMs,
        onAttempt: (startedAttempt) => {
          attempt = startedAttempt
          if (cancellationRequested) attempt.cancel()
        },
      })
    } finally {
      activeAttempt = null
    }
    if (result.cancelled) return null

    const body = new URLSearchParams({
      client_id: configuredClientId,
      code: result.code,
      code_verifier: verifier,
      grant_type: 'authorization_code',
      redirect_uri: result.redirectUri,
    })
    const response = await fetchImpl(TOKEN_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body,
      redirect: 'error',
      cache: 'no-store',
      signal: AbortSignal.timeout(15_000),
    })
    if (!response.ok) throw new Error('Google sign-in could not be completed.')
    const tokens = await response.json()
    if (typeof tokens?.id_token !== 'string' || tokens.id_token.length < 16 || tokens.id_token.length > 8192) {
      throw new Error('Google sign-in did not return a valid identity token.')
    }
    return tokens.id_token
  }

  return Object.freeze({ signIn, cancel })
}

function waitForAuthorization({ state, clientId, challenge, shell, createServer, timeoutMs, onAttempt }) {
  return new Promise((resolve, reject) => {
    let settled = false
    let server
    let timer
    let redirectUri

    const cleanup = () => {
      if (timer) clearTimeout(timer)
      if (server?.listening) server.close()
    }
    const finish = (result, error) => {
      if (settled) return false
      settled = true
      cleanup()
      if (error) reject(error)
      else resolve({ ...result, redirectUri })
      return true
    }
    const attempt = {
      cancel: () => finish({ cancelled: true }),
    }

    server = createServer((request, response) => {
      if (settled) {
        response.writeHead(410, { 'cache-control': 'no-store' }).end()
        return
      }
      const host = `127.0.0.1:${server.address()?.port}`
      let callback
      try {
        callback = new URL(request.url, `http://${host}`)
      } catch {
        response.writeHead(400, { 'cache-control': 'no-store' }).end('Invalid sign-in callback.')
        finish(null, new Error('Google sign-in returned an invalid callback.'))
        return
      }
      if (request.method !== 'GET' || request.headers.host !== host || request.socket.remoteAddress !== '127.0.0.1' || callback.pathname !== CALLBACK_PATH) {
        response.writeHead(400, { 'cache-control': 'no-store' }).end('Invalid sign-in callback.')
        finish(null, new Error('Google sign-in returned an invalid callback.'))
        return
      }
      const allowedParameters = new Set(['state', 'code', 'error'])
      if ([...callback.searchParams.keys()].some((key) => !allowedParameters.has(key))
        || [...allowedParameters].some((key) => callback.searchParams.getAll(key).length > 1)
        || (callback.searchParams.has('code') && callback.searchParams.has('error'))) {
        response.writeHead(400, { 'cache-control': 'no-store' }).end('Invalid sign-in response.')
        finish(null, new Error('Google sign-in returned an invalid callback.'))
        return
      }
      if (callback.searchParams.getAll('state').length !== 1 || callback.searchParams.get('state') !== state) {
        response.writeHead(400, { 'cache-control': 'no-store' }).end('Sign-in state did not match.')
        finish(null, new Error('Google sign-in state did not match.'))
        return
      }
      if (callback.searchParams.has('error')) {
        response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' })
          .end('<!doctype html><title>Hamartia</title><p>Sign-in was cancelled. Return to Hamartia.</p>')
        if (callback.searchParams.get('error') === 'access_denied') finish({ cancelled: true })
        else finish(null, new Error('Google sign-in was not completed.'))
        return
      }
      const codes = callback.searchParams.getAll('code')
      if (codes.length !== 1 || !codes[0] || codes[0].length > 4096) {
        response.writeHead(400, { 'cache-control': 'no-store' }).end('Invalid sign-in response.')
        finish(null, new Error('Google sign-in returned an invalid callback.'))
        return
      }
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' })
        .end('<!doctype html><title>Hamartia</title><p>Sign-in is complete. You can return to Hamartia.</p>')
      finish({ code: codes[0], cancelled: false })
    })

    server.once('error', (error) => finish(null, error))
    server.listen(0, '127.0.0.1', async () => {
      const port = server.address().port
      redirectUri = `http://127.0.0.1:${port}${CALLBACK_PATH}`
      const attemptUrl = new URL(AUTHORIZE_URL)
      attemptUrl.search = new URLSearchParams({
        client_id: clientId,
        code_challenge: challenge,
        code_challenge_method: 'S256',
        redirect_uri: redirectUri,
        response_type: 'code',
        scope: 'openid email profile',
        state,
      }).toString()
      timer = setTimeout(() => finish(null, new Error('Google sign-in timed out.')), timeoutMs)
      timer.unref?.()
      onAttempt(attempt)
      if (settled) return
      try {
        await shell.openExternal(attemptUrl.toString())
      } catch {
        finish(null, new Error('Could not open the system browser for Google sign-in.'))
      }
    })
  })
}

module.exports = { AUTHORIZE_URL, CALLBACK_PATH, TOKEN_URL, createGoogleDesktopOAuth, publicClientId }

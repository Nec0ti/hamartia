const crypto = require('node:crypto')
const fs = require('node:fs/promises')
const http = require('node:http')
const path = require('node:path')

const ISSUER = 'https://auth.openai.com'
const AUTHORIZE_URL = `${ISSUER}/api/accounts/authorize`
const TOKEN_URL = `${ISSUER}/api/accounts/oauth/token`
const OIDC_CONFIG_URL = `${ISSUER}/.well-known/openid-configuration`
const API_URL = 'https://api.openai.com/v1'
const JWKS_URL = `${ISSUER}/.well-known/jwks.json`
const CALLBACK_PATH = '/auth/callback'
const SCOPES = ['openid', 'profile', 'email', 'offline_access', 'resource.invoke', 'chatgpt.tokens.use.direct']
const REQUIRED_SCOPES = ['openid', 'offline_access', 'resource.invoke', 'chatgpt.tokens.use.direct']
const RESOURCE = `${API_URL}`
const MAX_MESSAGE_LENGTH = 4000
const MAX_CONTEXT_LENGTH = 6000

function randomValue(bytes = 32) {
  return crypto.randomBytes(bytes).toString('base64url')
}

function buildAuthorizationUrl({ clientId, redirectUri, state, nonce, verifier, hostId, email, idToken }) {
  const url = new URL(AUTHORIZE_URL)
  const params = new URLSearchParams({
    client_id: clientId,
    response_type: 'code',
    redirect_uri: redirectUri,
    scope: SCOPES.join(' '),
    resource: RESOURCE,
    state,
    nonce,
    code_challenge_method: 'S256',
    code_challenge: crypto.createHash('sha256').update(verifier).digest('base64url'),
    ext_agent_host_id: hostId,
  })
  if (clientId === 'dynamic_agent_client') params.set('agent_name_hint', 'Hamartia')
  if (email) params.set('login_hint', email)
  if (idToken) params.set('id_token_hint', idToken)
  url.search = params.toString()
  return url.toString()
}

function grantedScopes(value) {
  return new Set(typeof value === 'string' ? value.split(/\s+/).filter(Boolean) : [])
}

function summarizeStudyContext(insights, sessions) {
  const text = (value, maxLength = 120) => String(value || '').slice(0, maxLength)
  const referenceFields = ['framework', 'source', 'version', 'grade_year', 'unit_theme', 'learning_outcome', 'process_component', 'source_url']
  const summary = {
    pending_questions: insights?.pending_questions ?? 0,
    scheduled_questions: insights?.scheduled_questions ?? 0,
    topics: (Array.isArray(insights?.topics) ? insights.topics : []).slice(0, 8).map(({ subject, topic, pending_count, tags }) => ({
      subject: text(subject), topic: text(topic), pending_count: Number(pending_count) || 0,
      tags: Object.fromEntries(Object.entries(tags || {}).slice(0, 8).map(([tag, count]) => [text(tag, 80), Number(count) || 0])),
    })),
    topic_practice: (Array.isArray(sessions) ? sessions : []).slice(0, 8).map(({ subject, topic, session_count, net, accuracy }) => ({
      subject: text(subject), topic: text(topic), session_count: Number(session_count) || 0, net, accuracy,
    })),
    curriculum_references: [],
  }
  while (JSON.stringify(summary).length > MAX_CONTEXT_LENGTH && summary.topic_practice.length) summary.topic_practice.pop()
  while (JSON.stringify(summary).length > MAX_CONTEXT_LENGTH && summary.topics.length) summary.topics.pop()
  for (const reference of (Array.isArray(insights?.curriculum_references) ? insights.curriculum_references : []).slice(0, 8)) {
    const row = { subject: text(reference.subject) }
    for (const field of referenceFields) row[field] = text(reference[field], field === 'learning_outcome' ? 500 : field === 'source_url' ? 2048 : 200)
    const candidate = [...summary.curriculum_references, row]
    if (JSON.stringify({ ...summary, curriculum_references: candidate }).length > MAX_CONTEXT_LENGTH) break
    summary.curriculum_references = candidate
  }
  return JSON.stringify(summary)
}

function safeError(status, code) {
  if (code === 'subscription_sharing_usage_limit_exceeded' || code === 'subscription_sharing_usage_unavailable') {
    return 'Your ChatGPT plan usage is unavailable or has reached its limit. Manage usage in ChatGPT settings.'
  }
  if (status === 401) return 'ChatGPT authorization expired. Sign in again to continue.'
  if (status === 403) return 'OpenAI did not allow this request for the selected ChatGPT account.'
  if (status === 429) return 'The ChatGPT service is busy or has reached a limit. Try again later.'
  return 'The ChatGPT study agent could not complete this request. Please try again.'
}

function createChatGPT({ app, safeStorage, shell, fetchImpl = fetch, now = () => Date.now(), getBackendUrl, sendDelta, platform = process.platform }) {
  const file = path.join(app.getPath('userData'), 'chatgpt-credentials.bin')
  const hostFile = path.join(app.getPath('userData'), 'chatgpt-host-id')
  let refreshInFlight
  let signingOut = false
  let storageBlocked = false
  let revocationEndpointPromise
  const chats = new Map()

  function storageAvailable() {
    try {
      if (storageBlocked || !safeStorage.isEncryptionAvailable()) return false
      if (platform === 'linux') return ['gnome_libsecret', 'kwallet', 'kwallet5', 'kwallet6'].includes(safeStorage.getSelectedStorageBackend())
      return true
    } catch {
      return false
    }
  }

  async function readCredentials() {
    if (!storageAvailable()) throw new Error('Protected credential storage is unavailable. Sign-in is disabled on this device.')
    try {
      const encrypted = await fs.readFile(file)
      return JSON.parse(safeStorage.decryptString(encrypted))
    } catch (error) {
      if (error.code === 'ENOENT') return null
      const unreadable = new Error('The saved ChatGPT connection could not be opened. No request was sent.')
      unreadable.code = 'CHATGPT_CREDENTIALS_UNREADABLE'
      throw unreadable
    }
  }

  async function writeCredentials(credentials) {
    if (!storageAvailable()) throw new Error('Protected credential storage is unavailable. The ChatGPT connection was not saved.')
    const temporary = `${file}.${process.pid}.${randomValue(8)}.tmp`
    try {
      await fs.writeFile(temporary, safeStorage.encryptString(JSON.stringify(credentials)), { mode: 0o600, flag: 'wx' })
      await fs.rename(temporary, file)
      await fs.chmod(file, 0o600)
    } catch (error) {
      await fs.rm(temporary, { force: true })
      throw error
    }
  }

  async function hostId() {
    try {
      return (await fs.readFile(hostFile, 'utf8')).trim()
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
      const id = `urn:uuid:${crypto.randomUUID()}`
      await fs.writeFile(hostFile, id, { mode: 0o600, flag: 'wx' })
      return id
    }
  }

  async function getJwks() {
    const response = await fetchImpl(JWKS_URL, { signal: AbortSignal.timeout(10_000) })
    if (!response.ok) throw new Error('Could not verify the ChatGPT identity token.')
    return (await response.json()).keys
  }

  async function verifyIdentity(idToken, clientId, nonce) {
    const { importJWK, jwtVerify } = await import('jose')
    const keys = await getJwks()
    const header = JSON.parse(Buffer.from(idToken.split('.')[0], 'base64url').toString())
    const jwk = keys.find((key) => key.kid === header.kid && key.use === 'sig')
    if (!jwk) throw new Error('Could not verify the ChatGPT identity token.')
    if (header.alg !== 'RS256') throw new Error('Could not verify the ChatGPT identity token.')
    const key = await importJWK(jwk, 'RS256')
    const { payload } = await jwtVerify(idToken, key, {
      issuer: ISSUER,
      audience: clientId,
      requiredClaims: ['sub', 'exp', 'iat'],
      clockTolerance: 5,
      algorithms: ['RS256'],
    })
    if (payload.nonce !== nonce || typeof payload.sub !== 'string' || !payload.sub) {
      throw new Error('ChatGPT identity validation failed. Try signing in again.')
    }
    return payload
  }

  async function exchange(body) {
    const response = await fetchImpl(TOKEN_URL, {
      method: 'POST',
      headers: { accept: 'application/json', 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(body),
      signal: AbortSignal.timeout(20_000),
    })
    if (!response.ok) throw new Error('ChatGPT sign-in could not be completed. Please try again.')
    return response.json()
  }

  function validatedEndpoint(value) {
    if (typeof value !== 'string' || !value) throw new Error('OpenAI sign-out metadata is invalid.')
    let endpoint
    try {
      endpoint = new URL(value)
    } catch {
      throw new Error('OpenAI sign-out metadata is invalid.')
    }
    if (endpoint.origin !== ISSUER || endpoint.protocol !== 'https:' || endpoint.username || endpoint.password || endpoint.search || endpoint.hash || endpoint.pathname === '/') {
      throw new Error('OpenAI sign-out metadata is invalid.')
    }
    return endpoint.toString()
  }

  async function getRevocationEndpoint() {
    if (!revocationEndpointPromise) {
      revocationEndpointPromise = (async () => {
        const response = await fetchImpl(OIDC_CONFIG_URL, { signal: AbortSignal.timeout(10_000) })
        if (!response.ok) throw new Error('Could not read OpenAI sign-out metadata.')
        const metadata = await response.json()
        if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata) || metadata.issuer !== ISSUER) {
          throw new Error('OpenAI sign-out metadata is invalid.')
        }
        return validatedEndpoint(metadata.revocation_endpoint)
      })().catch((error) => {
        revocationEndpointPromise = null
        throw error
      })
    }
    return revocationEndpointPromise
  }

  async function startListener() {
    const server = http.createServer()
    await new Promise((resolve, reject) => {
      server.once('error', reject)
      server.listen(0, '127.0.0.1', resolve)
    })
    const port = server.address().port
    const redirectUri = `http://127.0.0.1:${port}${CALLBACK_PATH}`
    return { server, redirectUri }
  }

  async function signIn() {
    if (!storageAvailable()) throw new Error('Protected credential storage is unavailable. Sign-in is disabled on this device.')
    const previous = await readCredentials()
    const listener = await startListener()
    const state = randomValue()
    const nonce = randomValue()
    const verifier = randomValue(48)
    let timeout
    const clientId = previous?.client_id || 'dynamic_agent_client'
    const id = { promise: null }
    id.promise = new Promise((resolve, reject) => {
      timeout = setTimeout(() => reject(new Error('Sign-in timed out. Try again.')), 5 * 60 * 1000)
      listener.server.on('request', (request, response) => {
        const callback = new URL(request.url, listener.redirectUri)
        if (request.method !== 'GET' || callback.pathname !== CALLBACK_PATH) {
          response.writeHead(404).end()
          return
        }
        if (callback.searchParams.get('state') !== state) {
          response.writeHead(400).end('Sign-in could not be verified. You can close this window.')
          clearTimeout(timeout)
          reject(new Error('ChatGPT sign-in could not be verified. Try again.'))
          return
        }
        clearTimeout(timeout)
        const error = callback.searchParams.get('error')
        const code = callback.searchParams.get('code')
        const issuedClientId = callback.searchParams.get('client_id')
        if (error || !code || (clientId !== 'dynamic_agent_client' && issuedClientId && issuedClientId !== clientId) || (clientId === 'dynamic_agent_client' && !issuedClientId)) {
          response.writeHead(400, { 'content-type': 'text/plain; charset=utf-8' }).end('ChatGPT sign-in was cancelled or could not be completed. You can close this window.')
          reject(new Error(error === 'access_denied' ? 'ChatGPT plan usage permission was not granted.' : 'ChatGPT sign-in was cancelled or could not be completed.'))
          return
        }
        response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' }).end('<!doctype html><title>Hamartia</title><p>You can return to Hamartia.</p>')
        resolve({ code, clientId: issuedClientId || clientId })
      })
    })
    id.promise.catch(() => {})
    try {
      const url = buildAuthorizationUrl({ clientId, redirectUri: listener.redirectUri, state, nonce, verifier, hostId: await hostId(), email: previous?.email, idToken: previous?.id_token })
      await shell.openExternal(url)
      const callback = await id.promise
      if (!previous?.client_id) await writeCredentials({ client_id: callback.clientId })
      const tokens = await exchange({
        grant_type: 'authorization_code',
        client_id: callback.clientId,
        code: callback.code,
        code_verifier: verifier,
        redirect_uri: listener.redirectUri,
        resource: RESOURCE,
      })
      if (!tokens.id_token || !tokens.access_token || !tokens.refresh_token) throw new Error('ChatGPT did not return the required credentials. Sign-in was not saved.')
      const identity = await verifyIdentity(tokens.id_token, callback.clientId, nonce)
      const scopes = [...grantedScopes(tokens.scope)]
      if (!REQUIRED_SCOPES.every((scope) => scopes.includes(scope))) throw new Error('ChatGPT did not grant the required identity and plan-use permissions. No ChatGPT request was sent.')
      if (previous?.subject && (previous.client_id !== callback.clientId || previous.subject !== identity.sub)) throw new Error('The ChatGPT account changed during sign-in. Existing credentials were kept.')
      const credentials = {
        client_id: callback.clientId,
        subject: identity.sub,
        email: typeof identity.email === 'string' ? identity.email : '',
        id_token: tokens.id_token,
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        scopes,
        expires_at: now() + Number(tokens.expires_in || 3600) * 1000,
      }
      await writeCredentials(credentials)
      return { connected: true, email: credentials.email, planUse: true }
    } finally {
      clearTimeout(timeout)
      listener.server.close()
    }
  }

  async function validAccessToken() {
    if (signingOut) throw new Error('ChatGPT is signing out. Try again when it has finished.')
    const credentials = await readCredentials()
    if (!credentials) throw new Error('Sign in with ChatGPT before sending a study question.')
    if (!credentials.access_token || !credentials.refresh_token) throw new Error('Sign in with ChatGPT before sending a study question.')
    if (!REQUIRED_SCOPES.every((scope) => credentials.scopes.includes(scope))) throw new Error('ChatGPT plan usage permission is missing. Sign in again and grant it before continuing.')
    if (credentials.expires_at > now() + 30_000) return { credentials, accessToken: credentials.access_token }
    if (!refreshInFlight) {
      refreshInFlight = (async () => {
        const updated = await exchange({ grant_type: 'refresh_token', client_id: credentials.client_id, refresh_token: credentials.refresh_token, resource: RESOURCE })
        if (!updated.access_token || !updated.refresh_token) throw new Error('ChatGPT could not refresh its authorization. Sign in again.')
        const refreshed = { ...credentials, access_token: updated.access_token, refresh_token: updated.refresh_token, expires_at: now() + Number(updated.expires_in || 3600) * 1000 }
        await writeCredentials(refreshed)
        return refreshed
      })().finally(() => { refreshInFlight = null })
    }
    const refreshed = await refreshInFlight
    return { credentials: refreshed, accessToken: refreshed.access_token }
  }

  async function status() {
    if (!storageAvailable()) return { connected: false, unavailable: true }
    let credentials
    try {
      credentials = await readCredentials()
    } catch (error) {
      if (error.code === 'CHATGPT_CREDENTIALS_UNREADABLE') return { connected: false, recoveryRequired: true }
      throw error
    }
    return credentials?.access_token ? { connected: true, savedAccount: true, email: credentials.email, planUse: credentials.scopes?.includes('chatgpt.tokens.use.direct') && credentials.scopes?.includes('resource.invoke') } : { connected: false, savedAccount: Boolean(credentials?.client_id), email: credentials?.email || '' }
  }

  async function signOut() {
    signingOut = true
    for (const controller of chats.values()) controller.abort()
    if (refreshInFlight) await refreshInFlight.catch(() => {})
    const credentials = await readCredentials().catch(() => null)
    let revocationConfirmed = false
    try {
      if (credentials?.refresh_token && credentials.client_id) {
        let endpoint
        try {
          endpoint = await getRevocationEndpoint()
        } catch {}
        if (endpoint) {
          for (let attempt = 0; attempt < 3; attempt += 1) {
            try {
              const response = await fetchImpl(endpoint, {
                method: 'POST',
                headers: { accept: 'application/json', 'content-type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ token: credentials.refresh_token, token_type_hint: 'refresh_token', client_id: credentials.client_id }),
                signal: AbortSignal.timeout(10_000),
              })
              if (response.status === 200) {
                revocationConfirmed = true
                break
              }
              if (response.status < 500) break
            } catch {}
            if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, [100, 300, 900][attempt]))
          }
        }
      }
    } finally {
      try {
        if (credentials) await writeCredentials({ client_id: credentials.client_id, subject: credentials.subject, email: credentials.email })
        else await fs.rm(file, { force: true })
      } catch (error) {
        storageBlocked = true
        throw new Error('ChatGPT tokens could not be removed from this device. Close the app and try again.')
      }
      signingOut = false
    }
    return { connected: false, savedAccount: Boolean(credentials?.client_id), email: credentials?.email || '', revocationConfirmed }
  }

  async function forgetAccount() {
    const credentials = await readCredentials()
    if (credentials?.access_token || credentials?.refresh_token) throw new Error('Sign out before switching the saved ChatGPT account.')
    await fs.rm(file, { force: true })
    return { connected: false, savedAccount: false }
  }

  async function recoverUnreadableCredentials(confirmed) {
    if (confirmed !== true) throw new Error('Confirm local credential removal before continuing.')
    try {
      const credentials = await readCredentials()
      if (credentials?.access_token || credentials?.refresh_token) throw new Error('Sign out before recovering the saved ChatGPT connection.')
      throw new Error('The saved ChatGPT connection is readable; use the account controls instead.')
    } catch (error) {
      if (error.code !== 'CHATGPT_CREDENTIALS_UNREADABLE') throw error
    }
    await fs.rm(file, { force: true })
    return { connected: false, savedAccount: false, recoveredUnreadableCredentials: true, revocationConfirmed: false }
  }

  async function models(signal) {
    const { accessToken } = await validAccessToken()
    const response = await fetchImpl(`${API_URL}/models`, { headers: { authorization: `Bearer ${accessToken}` }, signal: signal || AbortSignal.timeout(15_000) })
    if (!response.ok) throw new Error(safeError(response.status))
    const data = await response.json()
    return (data.models || []).filter((model) => model.visibility === 'list' && model.slug && model.display_name).map(({ slug, display_name }) => ({ slug, display_name }))
  }

  async function studyContext(signal) {
    const backendUrl = getBackendUrl()
    const [insightsResponse, sessionsResponse] = await Promise.all([
      fetchImpl(`${backendUrl}/questions/insights`, { signal }),
      fetchImpl(`${backendUrl}/practice/insights`, { signal }),
    ])
    if (!insightsResponse.ok || !sessionsResponse.ok) throw new Error('Could not read local study priorities. No study request was sent.')
    return summarizeStudyContext(await insightsResponse.json(), await sessionsResponse.json())
  }

  async function chat({ requestId, message, model, language }, onDelta) {
    if (typeof message !== 'string' || !message.trim() || message.length > MAX_MESSAGE_LENGTH) throw new Error('Enter a question under 4,000 characters.')
    const controller = new AbortController()
    chats.set(requestId, controller)
    try {
      const { accessToken } = await validAccessToken()
      const context = await studyContext(controller.signal)
      if (!(await models(controller.signal)).some((item) => item.slug === model)) throw new Error('Choose a model available to the signed-in ChatGPT account.')
      const response = await fetchImpl(`${API_URL}/responses`, {
        method: 'POST',
        headers: { authorization: `Bearer ${accessToken}`, 'content-type': 'application/json', accept: 'text/event-stream' },
        body: JSON.stringify({
          model,
          instructions: `You are Hamartia's study assistant. Answer in ${language === 'tr' ? 'Turkish' : 'English'}. Use only the student message and supplied study summary; do not claim to have seen specific question text, images, or conversations. Identify mistake patterns only when the summary supports them; say when evidence is insufficient. Curriculum references are user-entered and unverified, not official alignment. If one is present, relate it cautiously and label it as user-provided. Suggest a concrete next learning activity and a separate evidence-of-learning task with observable success criteria. Use short, localized sections for supported pattern, next activity, evidence task, and criteria. Do not infer mastery from one response, equate learning evidence with exam net/XP, or claim the evidence task has been completed. Without a reference, do not invent a curriculum mapping. Be clear and concise.`,
          input: [{ role: 'user', content: `Local study summary (may be empty):\n${context}\n\nStudent question:\n${message}` }],
          store: false,
          stream: true,
        }),
        signal: controller.signal,
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(safeError(response.status, data.error?.code))
      }
      if (!response.body) throw new Error('The ChatGPT response did not include a stream.')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let completed = false
      while (true) {
        const { value, done } = await reader.read()
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r\n/g, '\n')
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''
        for (const event of events) {
          const line = event.split('\n').find((part) => part.startsWith('data:'))
          if (!line) continue
          const data = JSON.parse(line.slice(5).trim())
          if (data.type === 'response.output_text.delta' && data.delta) onDelta(requestId, data.delta)
          if (data.type === 'response.failed') throw new Error(safeError(0, data.response?.error?.code))
          if (data.type === 'response.incomplete') throw new Error('ChatGPT returned an incomplete response. Please try again.')
          if (data.type === 'response.completed') completed = true
        }
        if (done) break
      }
      if (!completed) throw new Error('ChatGPT stream ended before the response was complete.')
      return { status: 'completed' }
    } catch (error) {
      if (controller.signal.aborted || error.name === 'AbortError') return { status: 'cancelled' }
      return { status: 'failed', detail: error.message || 'ChatGPT request failed.' }
    } finally {
      chats.delete(requestId)
    }
  }

  function cancel(requestId) {
    chats.get(requestId)?.abort()
  }

  return { status, signIn, signOut, forgetAccount, recoverUnreadableCredentials, models, chat, cancel }
}

module.exports = { API_URL, CALLBACK_PATH, ISSUER, MAX_CONTEXT_LENGTH, MAX_MESSAGE_LENGTH, REQUIRED_SCOPES, RESOURCE, SCOPES, buildAuthorizationUrl, createChatGPT, grantedScopes, safeError, summarizeStudyContext }

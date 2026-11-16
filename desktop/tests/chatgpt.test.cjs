const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')
const crypto = require('node:crypto')
const { exportJWK, generateKeyPair, SignJWT } = require('jose')
const { API_URL, CALLBACK_PATH, MAX_CONTEXT_LENGTH, REQUIRED_SCOPES, SCOPES, buildAuthorizationUrl, createChatGPT, grantedScopes, summarizeStudyContext } = require('../chatgpt.cjs')

test('authorization uses fresh PKCE-bound OSS plan-use scopes and exact loopback callback', () => {
  const url = new URL(buildAuthorizationUrl({
    clientId: 'dynamic_agent_client', redirectUri: `http://127.0.0.1:1234${CALLBACK_PATH}`,
    state: 'fresh-state', nonce: 'fresh-nonce', verifier: 'fresh-verifier', hostId: 'urn:uuid:test-host',
  }))
  assert.equal(url.origin, 'https://auth.openai.com')
  assert.equal(url.searchParams.get('client_id'), 'dynamic_agent_client')
  assert.equal(url.searchParams.get('scope'), SCOPES.join(' '))
  assert.deepEqual(grantedScopes(url.searchParams.get('scope')).has('chatgpt.tokens.use.direct'), true)
  assert.equal(url.searchParams.get('resource'), API_URL)
  assert.equal(url.searchParams.get('redirect_uri'), `http://127.0.0.1:1234${CALLBACK_PATH}`)
  assert.equal(url.searchParams.get('code_challenge_method'), 'S256')
  assert.equal(url.searchParams.get('code_challenge'), require('node:crypto').createHash('sha256').update('fresh-verifier').digest('base64url'))
  assert.equal(url.searchParams.get('state'), 'fresh-state')
  assert.equal(url.searchParams.get('nonce'), 'fresh-nonce')
  assert.equal(url.searchParams.get('ext_agent_host_id'), 'urn:uuid:test-host')
  assert.equal(REQUIRED_SCOPES.includes('chatgpt.tokens.use.direct'), true)
})

test('local study context is summarized and bounded without question text', () => {
  const result = summarizeStudyContext({
    pending_questions: 9,
    topics: [{ subject: 'Math', topic: 'Functions', pending_count: 2, tags: { gap: 1 }, ocr_text: 'secret question text' }],
    curriculum_references: [{ subject: 'Math', framework: 'Synthetic framework', learning_outcome: 'Explain an invented pattern', source_url: 'https://example.invalid/reference' }],
  }, [{ subject: 'Math', topic: 'Functions', session_count: 3, net: 7, accuracy: 0.8 }])
  assert.ok(result.length <= MAX_CONTEXT_LENGTH)
  assert.match(result, /Functions/)
  assert.doesNotMatch(result, /secret question text/)
  assert.deepEqual(JSON.parse(result).topic_practice, [{ subject: 'Math', topic: 'Functions', session_count: 3, net: 7, accuracy: 0.8 }])
  assert.equal(JSON.parse(result).curriculum_references[0].learning_outcome, 'Explain an invented pattern')
  assert.equal(JSON.parse(result).curriculum_references[0].source_url, 'https://example.invalid/reference')
})

async function setup({ backend = 'gnome_libsecret', encryptionAvailable = true, platform = process.platform } = {}) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'hamartia-siwc-'))
  const { publicKey, privateKey } = await generateKeyPair('RS256')
  const jwk = await exportJWK(publicKey)
  jwk.kid = 'test-key'
  jwk.use = 'sig'
  jwk.alg = 'RS256'
  let nonceForToken = ''
  let tokenResponse = null
  let callbackError = ''
  let callbackMutator = (url) => url
  let responseStatus = 200
  let responseErrorCode = ''
  let refreshGate = null
  let revocationStatus = 200
  let revocationRequests = 0
  let oidcMetadata = { issuer: 'https://auth.openai.com', revocation_endpoint: 'https://auth.openai.com/api/accounts/oauth/revoke' }
  let oidcRequests = 0
  let openExternalError = null
  const authorizationUrls = []
  let streamMode = 'complete'
  let responseRequest
  const responseRequests = []
  const responseStreams = []
  let practiceDraft = {
    status: 'incomplete', fields: { subject: 'Mathematics' }, proposal: { subject: 'Mathematics' },
    proposal_mismatch: false, evidence: { subject: { value: 'Mathematics', message_index: 0, quote: 'subject: Mathematics', start: 0, end: 19 } },
    evidence_claims: [{ field: 'subject', quote: 'subject: Mathematics' }], missing: ['date'], ambiguous: {},
    questions: ['Which date did you complete this set?'], preview_digest: null, conflicts: [],
  }
  const practiceDraftRequests = []
  let learningEvidenceDraft = { status: 'incomplete', fields: {}, verified_evidence: {}, evidence_claims: [], missing: ['activity'], ambiguous: {}, questions: ['What activity have you already completed?'], expected_field: 'activity', preview_digest: null, write_allowed: false }
  const learningEvidenceDraftRequests = []
  const tokenBodies = []
  const calls = []
  const encryptionKey = crypto.randomBytes(32)
  const safeStorage = {
    isEncryptionAvailable: () => encryptionAvailable,
    getSelectedStorageBackend: () => backend,
    encryptString: (value) => {
      const iv = crypto.randomBytes(12)
      const cipher = crypto.createCipheriv('aes-256-gcm', encryptionKey, iv)
      const encrypted = Buffer.concat([cipher.update(value), cipher.final()])
      return Buffer.concat([iv, cipher.getAuthTag(), encrypted])
    },
    decryptString: (value) => {
      const encrypted = Buffer.from(value)
      const decipher = crypto.createDecipheriv('aes-256-gcm', encryptionKey, encrypted.subarray(0, 12))
      decipher.setAuthTag(encrypted.subarray(12, 28))
      return Buffer.concat([decipher.update(encrypted.subarray(28)), decipher.final()]).toString()
    },
  }
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url: String(url), options })
    if (String(url).includes('.well-known/openid-configuration')) {
      oidcRequests += 1
      if (oidcMetadata instanceof Error) throw oidcMetadata
      return Response.json(oidcMetadata)
    }
    if (String(url).endsWith('/oauth/revoke')) {
      revocationRequests += 1
      return new Response(null, { status: revocationStatus })
    }
    if (String(url).includes('.well-known/jwks.json')) return Response.json({ keys: [jwk] })
    if (String(url).includes('/oauth/token')) {
      const body = new URLSearchParams(options.body)
      tokenBodies.push(body)
      if (body.get('grant_type') === 'refresh_token' && refreshGate) await refreshGate
      if (typeof tokenResponse === 'function') return Response.json(await tokenResponse(body, { nonce: nonceForToken, privateKey }))
      return Response.json(tokenResponse || {
        access_token: 'access-secret', refresh_token: 'refresh-secret', id_token: await new SignJWT({ nonce: nonceForToken, email: 'student@example.test' }).setProtectedHeader({ alg: 'RS256', kid: 'test-key' }).setIssuer('https://auth.openai.com').setAudience('oaiapp_test').setSubject('student-123').setIssuedAt().setExpirationTime('1h').sign(privateKey),
        expires_in: 3600, scope: SCOPES.join(' '),
      })
    }
    if (String(url) === `${API_URL}/models`) return Response.json({ models: [{ slug: 'model-a', display_name: 'Model A', visibility: 'list' }, { slug: 'hidden', display_name: 'Hidden', visibility: 'private' }] })
    if (String(url) === `${API_URL}/responses`) {
      responseRequest = JSON.parse(options.body)
      responseRequests.push(responseRequest)
      if (responseStatus !== 200) return Response.json({ error: { code: responseErrorCode } }, { status: responseStatus })
      if (streamMode === 'cancel') return new Response(new ReadableStream({ start(controller) {
        options.signal.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')))
      } }), { headers: { 'content-type': 'text/event-stream' } })
      const events = (responseStreams.shift() || [
        { type: 'response.output_text.delta', delta: 'Review this topic.' },
        { type: 'response.completed', response: { id: 'response-1', output: [{ type: 'message', role: 'assistant', content: [] }] } },
      ]).map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')
      return new Response(events, { headers: { 'content-type': 'text/event-stream' } })
    }
    if (String(url) === 'http://127.0.0.1:43210/practice/agent-draft') {
      practiceDraftRequests.push(JSON.parse(options.body))
      return Response.json(practiceDraft)
    }
    if (String(url) === 'http://127.0.0.1:43210/learning-evidence/agent-draft') {
      learningEvidenceDraftRequests.push(JSON.parse(options.body))
      return Response.json(learningEvidenceDraft)
    }
    if (String(url) === 'http://127.0.0.1:43210/questions/insights') return Response.json({
      pending_questions: 3, scheduled_questions: 2,
      topics: [{ subject: 'Math', topic: 'Functions', pending_count: 2, tags: {} }],
      curriculum_references: [{ subject: 'Math', framework: 'Synthetic framework', learning_outcome: 'Explain an invented pattern' }],
    })
    if (String(url) === 'http://127.0.0.1:43210/practice/insights') return Response.json([])
    throw new Error(`Unexpected mock request: ${url}`)
  }
  const client = createChatGPT({
    app: { getPath: () => directory }, safeStorage, fetchImpl, platform, getBackendUrl: () => 'http://127.0.0.1:43210',
    shell: { openExternal: async (value) => {
      if (openExternalError) throw openExternalError
      authorizationUrls.push(value)
      const url = new URL(value)
      nonceForToken = url.searchParams.get('nonce')
      const callback = `${url.searchParams.get('redirect_uri')}?${callbackError ? `error=${callbackError}&` : 'code=one-time&'}state=${url.searchParams.get('state')}&client_id=oaiapp_test`
      await fetch(callbackMutator(callback))
    } },
  })
  return {
    client, directory, safeStorage, calls, tokenBodies, getResponseRequest: () => responseRequest,
    getResponseRequests: () => responseRequests,
    setResponseStreams: (values) => { responseStreams.push(...values) },
    setPracticeDraft: (value) => { practiceDraft = value },
    setLearningEvidenceDraft: (value) => { learningEvidenceDraft = value },
    getLearningEvidenceDraftRequests: () => learningEvidenceDraftRequests,
    getPracticeDraft: () => practiceDraft,
    getPracticeDraftRequests: () => practiceDraftRequests,
    setStreamMode: (value) => { streamMode = value }, setTokenResponse: (value) => { tokenResponse = value },
    setCallbackError: (value) => { callbackError = value }, setCallbackMutator: (value) => { callbackMutator = value },
    setResponseError: (status, code) => { responseStatus = status; responseErrorCode = code },
    setRevocationStatus: (value) => { revocationStatus = value },
    setOidcMetadata: (value) => { oidcMetadata = value },
    setOpenExternalError: (value) => { openExternalError = value },
    getRevocationRequests: () => revocationRequests,
    getOidcRequests: () => oidcRequests,
    getAuthorizationUrls: () => authorizationUrls,
    setRefreshGate: (value) => { refreshGate = value },
    expireCredentials: async () => {
      const file = path.join(directory, 'chatgpt-credentials.bin')
      const credentials = JSON.parse(safeStorage.decryptString(await fs.readFile(file)))
      credentials.expires_at = 0
      await fs.writeFile(file, safeStorage.encryptString(JSON.stringify(credentials)), { mode: 0o600 })
    },
  }
}

test('mocked sign-in stores only encrypted credentials and streams direct Responses to completion', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  assert.deepEqual(await testApp.client.signIn(), { connected: true, email: 'student@example.test', planUse: true })
  assert.equal((await testApp.client.status()).planUse, true)
  const saved = await fs.readFile(path.join(testApp.directory, 'chatgpt-credentials.bin'))
  assert.doesNotMatch(saved.toString(), /access-secret|refresh-secret|student@example/)
  if (process.platform !== 'win32') {
    assert.equal((await fs.stat(path.join(testApp.directory, 'chatgpt-credentials.bin'))).mode & 0o777, 0o600)
  }
  assert.equal(testApp.tokenBodies[0].get('client_id'), 'oaiapp_test')
  assert.equal(testApp.tokenBodies[0].get('code_verifier')?.length > 40, true)
  assert.equal(testApp.tokenBodies[0].has('client_secret'), false)
  assert.deepEqual(await testApp.client.models(), [{ slug: 'model-a', display_name: 'Model A' }])
  const deltas = []
  assert.deepEqual(await testApp.client.chat({ requestId: 'request-test-000001', message: 'How should I review?', model: 'model-a', language: 'en' }, (_id, delta) => deltas.push(delta)), { status: 'completed' })
  assert.equal(deltas.join(''), 'Review this topic.')
  const request = testApp.getResponseRequest()
  assert.equal(request.store, false)
  assert.equal(request.stream, true)
  assert.equal(request.model, 'model-a')
  assert.match(request.instructions, /user-entered and unverified/)
  assert.match(request.instructions, /evidence-of-learning task with observable success criteria/)
  const userInput = JSON.stringify(request.input)
  assert.match(userInput, /Explain an invented pattern/)
  assert.match(request.input[0].content, /Functions/)
  assert.equal(testApp.calls.some(({ url }) => url.includes('backend-api')), false)
})

test('practice-entry calls one strict evidence tool, verifies host transcript, and returns only its draft', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  const messages = ['subject: Matematik', 'correct: 7']
  const argumentsText = JSON.stringify({ evidence: [{ field: 'subject', quote: 'subject: Matematik' }] })
  const functionCall = { type: 'function_call', id: 'fc_1', call_id: 'call_1', name: 'hamartia_practice_prepare', arguments: argumentsText, status: 'completed' }
  const reasoningItem = { type: 'reasoning', id: 'rs_1', summary: [] }
  testApp.setResponseStreams([
    [{ type: 'response.completed', response: { id: 'response-1', output: [reasoningItem, functionCall] } }],
    [{ type: 'response.completed', response: { id: 'response-2', output: [{ type: 'message', role: 'assistant', content: [] }] } }],
  ])
  const deltas = []
  const result = await testApp.client.chat({
    requestId: 'request-practice-000001', message: messages.at(-1), model: 'model-a', language: 'tr',
    workflow: 'practice-entry', messages, scoring_profile_id: 'profile_host-choice', scoring_profile_version: 3,
  }, (_id, delta) => deltas.push(delta))
  assert.equal(result.status, 'completed')
  assert.deepEqual(result.draft, testApp.getPracticeDraft())
  const [request, followup] = testApp.getResponseRequests()
  assert.match(request.instructions, /Provide only exact quotes/)
  assert.match(request.instructions, /Turkish/)
  assert.equal(request.store, false)
  assert.equal(request.stream, true)
  assert.equal(Object.hasOwn(request, 'additional_tools'), false)
  assert.deepEqual(request.input[0], {
    type: 'additional_tools', role: 'developer', tools: [{
      type: 'function', name: 'hamartia_practice_prepare',
      description: 'Submit exact student-message quotes for local verification and a read-only practice preview.',
      parameters: request.input[0].tools[0].parameters, strict: true,
    }],
  })
  const tool = request.input[0].tools[0]
  assert.equal(tool.name, 'hamartia_practice_prepare')
  assert.equal(tool.strict, true)
  assert.deepEqual(tool.parameters.required, ['evidence'])
  assert.equal(tool.parameters.additionalProperties, false)
  assert.deepEqual(request.input[1], { role: 'user', content: JSON.stringify({ student_messages: messages }) })
  assert.deepEqual(followup.input[0], request.input[0])
  assert.deepEqual(followup.input[1], request.input[1])
  assert.match(followup.instructions, /Turkish/)
  assert.deepEqual(followup.input.slice(2, 4), [reasoningItem, functionCall])
  assert.equal(followup.input[4].type, 'function_call_output')
  assert.equal(followup.input[4].call_id, 'call_1')
  assert.equal(JSON.parse(followup.input[4].output).write_allowed, false)
  assert.equal(followup.store, false)
  assert.equal(followup.stream, true)
  assert.equal(Object.hasOwn(followup, 'previous_response_id'), false)
  assert.deepEqual(testApp.getPracticeDraftRequests(), [{
    messages, language: 'tr', evidence_claims: [{ field: 'subject', quote: 'subject: Matematik' }],
    scoring_profile_id: 'profile_host-choice', scoring_profile_version: 3,
  }])
  assert.deepEqual(deltas, [])
  assert.equal(testApp.calls.some(({ url }) => url === 'http://127.0.0.1:43210/questions/insights' || url === 'http://127.0.0.1:43210/practice/insights'), false)
  assert.equal(testApp.calls.some(({ url }) => url.endsWith('/practice/agent-create')), false)
})

test('practice-entry rejects malformed, spoofed, value-bearing, unsupported, and multiple tool calls', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  const messages = ['correct: 5']
  const invalid = [
    { name: 'hamartia_practice_prepare', arguments: 'not-json' },
    { name: 'hamartia_practice_prepare', arguments: JSON.stringify({ evidence: [], messages }) },
    { name: 'hamartia_practice_prepare', arguments: JSON.stringify({ evidence: [], language: 'tr' }) },
    { name: 'hamartia_practice_prepare', arguments: JSON.stringify({ evidence: [{ field: 'correct', quote: 'correct: 5', value: 5 }] }) },
    { name: 'write_record', arguments: JSON.stringify({ evidence: [] }) },
  ]
  for (const [index, call] of invalid.entries()) {
    testApp.setResponseStreams([[{
      type: 'response.completed', response: { id: `invalid-${index}`, output: [{ type: 'function_call', call_id: `invalid-call-${index}`, ...call }] },
    }]])
    const result = await testApp.client.chat({
      requestId: `request-invalid-${String(index).padStart(6, '0')}`, message: messages[0], model: 'model-a', language: 'en',
      workflow: 'practice-entry', messages,
    }, () => assert.fail('Practice tool output must never stream to the renderer.'))
    assert.equal(result.status, 'failed')
  }
  testApp.setResponseStreams([[{
    type: 'response.completed', response: { id: 'multiple', output: [
      { type: 'function_call', call_id: 'multiple-1', name: 'hamartia_practice_prepare', arguments: '{"evidence":[]}' },
      { type: 'function_call', call_id: 'multiple-2', name: 'hamartia_practice_prepare', arguments: '{"evidence":[]}' },
    ] },
  }]])
  const result = await testApp.client.chat({
    requestId: 'request-multiple-0001', message: messages[0], model: 'model-a', language: 'en',
    workflow: 'practice-entry', messages,
  }, () => assert.fail('Practice tool output must never stream to the renderer.'))
  assert.equal(result.status, 'failed')
  assert.equal(testApp.getPracticeDraftRequests().length, 0)
  assert.equal(testApp.calls.some(({ url }) => url.endsWith('/practice/agent-create')), false)
})

test('practice-entry rejects an additional tool turn after verified tool output', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  const messages = ['subject: Mathematics']
  const args = JSON.stringify({ evidence: [{ field: 'subject', quote: 'subject: Mathematics' }] })
  testApp.setResponseStreams([
    [{ type: 'response.completed', response: { id: 'first', output: [{ type: 'function_call', call_id: 'call-1', name: 'hamartia_practice_prepare', arguments: args }] } }],
    [{ type: 'response.completed', response: { id: 'second', output: [{ type: 'function_call', call_id: 'call-2', name: 'hamartia_practice_prepare', arguments: args }] } }],
  ])
  const result = await testApp.client.chat({
    requestId: 'request-extra-tool-0001', message: messages[0], model: 'model-a', language: 'en',
    workflow: 'practice-entry', messages,
  }, () => assert.fail('Practice tool output must never stream to the renderer.'))
  assert.equal(result.status, 'failed')
  assert.equal(testApp.getPracticeDraftRequests().length, 1)
  assert.equal(testApp.calls.some(({ url }) => url.endsWith('/practice/agent-create')), false)
})

test('learning-evidence uses only expected-field quote hints and returns host preview without a write route', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  const messages = ['I completed reading chapter 2.']
  const claims = [{ field: 'activity', quote: messages[0] }]
  const call = { type: 'function_call', id: 'fc_learning', call_id: 'call_learning', name: 'hamartia_learning_evidence_prepare', arguments: JSON.stringify({ evidence: claims }), status: 'completed' }
  const reasoningItem = { type: 'reasoning', id: 'rs_learning', summary: [] }
  const draft = {
    status: 'incomplete', fields: { activity: messages[0] }, verified_evidence: { activity: { value: messages[0], message_index: 0, quote: messages[0], start: 0, end: messages[0].length } },
    evidence_claims: claims, missing: ['subject', 'topic', 'date', 'observation'], ambiguous: {},
    questions: ['Which subject was the activity for?'], expected_field: 'subject', preview_digest: null, write_allowed: false,
  }
  testApp.setLearningEvidenceDraft(draft)
  testApp.setResponseStreams([
    [{ type: 'response.completed', response: { id: 'learning-1', output: [reasoningItem, call] } }],
    [{ type: 'response.completed', response: { id: 'learning-2', output: [{ type: 'message', role: 'assistant', content: [] }] } }],
  ])
  const result = await testApp.client.chat({
    requestId: 'request-learning-000001', message: messages[0], model: 'model-a', language: 'en',
    workflow: 'learning-evidence-entry', messages, expected_evidence_field: 'activity',
  })
  assert.equal(result.status, 'completed')
  assert.deepEqual(result.draft, draft)
  const [initial, followup] = testApp.getResponseRequests()
  assert.match(initial.instructions, /host currently expects only the activity field/i)
  assert.equal(initial.store, false)
  assert.equal(initial.input[0].tools[0].name, 'hamartia_learning_evidence_prepare')
  assert.deepEqual(initial.input[0].tools[0].parameters.properties.evidence.items.properties.field.enum,
    ['date', 'subject', 'topic', 'activity', 'observation', 'reference_url'])
  assert.deepEqual(testApp.getLearningEvidenceDraftRequests(), [{
    messages, language: 'en', expected_evidence_field: 'activity', state_token: null, evidence_claims: claims,
  }])
  assert.deepEqual(followup.input.slice(2, 4), [reasoningItem, call])
  assert.equal(JSON.parse(followup.input[4].output).write_allowed, false)
  assert.equal(testApp.calls.some(({ url }) => url.endsWith('/learning-evidence/agent-create')), false)
})

test('learning-evidence carries only opaque signed state into the next host preview', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  const messages = ['I worked on chapter 2.', 'Biology', 'Cell division']
  const stateToken = 'opaque-host-signed-state-token'
  const newClaim = { field: 'topic', quote: messages[2] }
  const draft = {
    status: 'incomplete', language: 'en', fields: { activity: messages[0], subject: messages[1], topic: messages[2] },
    verified_evidence: {
      activity: { value: messages[0], message_index: 0, quote: messages[0], start: 0, end: messages[0].length },
      subject: { value: messages[1], message_index: 1, quote: messages[1], start: 0, end: messages[1].length },
      topic: { value: messages[2], message_index: 2, quote: messages[2], start: 0, end: messages[2].length },
    },
    evidence_claims: [newClaim], missing: ['date', 'observation'], ambiguous: {},
    questions: ['What date did you complete it? Reply with an explicit YYYY-MM-DD date.'],
    expected_field: 'date', preview_digest: null, write_allowed: false,
  }
  const call = { type: 'function_call', id: 'fc_learning_next', call_id: 'call_learning_next', name: 'hamartia_learning_evidence_prepare', arguments: JSON.stringify({ evidence: [newClaim] }), status: 'completed' }
  testApp.setLearningEvidenceDraft(draft)
  testApp.setResponseStreams([
    [{ type: 'response.completed', response: { id: 'learning-next-1', output: [{ type: 'reasoning', id: 'rs-next', summary: [] }, call] } }],
    [{ type: 'response.completed', response: { id: 'learning-next-2', output: [{ type: 'message', role: 'assistant', content: [] }] } }],
  ])
  const result = await testApp.client.chat({
    requestId: 'request-learning-next-0001', message: messages[2], model: 'model-a', language: 'en',
    workflow: 'learning-evidence-entry', messages, expected_evidence_field: 'topic', state_token: stateToken,
  })
  assert.equal(result.status, 'completed')
  assert.equal(result.draft.expected_field, 'date')
  assert.deepEqual(testApp.getLearningEvidenceDraftRequests(), [{
    messages, language: 'en', expected_evidence_field: 'topic', state_token: stateToken, evidence_claims: [newClaim],
  }])
  assert.equal(testApp.calls.some(({ url }) => url.endsWith('/learning-evidence/agent-create')), false)
})

test('learning-evidence rejects value-bearing, unsupported, duplicate, and out-of-contract tool args before preview', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  const messages = ['Biology']
  const invalidArguments = [
    { evidence: [{ field: 'subject', quote: 'Biology', value: 'Chemistry' }] },
    { evidence: [{ field: 'record_id', quote: 'Biology' }] },
    { evidence: [{ field: 'activity', quote: 'Biology' }], language: 'en' },
    { evidence: Array.from({ length: 13 }, () => ({ field: 'activity', quote: 'Biology' })) },
  ]
  for (const [index, argumentsValue] of invalidArguments.entries()) {
    testApp.setResponseStreams([[{
      type: 'response.completed', response: { id: `learning-invalid-${index}`, output: [{
        type: 'function_call', call_id: `learning-invalid-call-${index}`, name: 'hamartia_learning_evidence_prepare', arguments: JSON.stringify(argumentsValue),
      }] },
    }]])
    const result = await testApp.client.chat({
      requestId: `request-learning-invalid-${index}`, message: messages[0], model: 'model-a', language: 'en',
      workflow: 'learning-evidence-entry', messages, expected_evidence_field: 'activity',
    })
    assert.equal(result.status, 'failed')
  }
  assert.equal(testApp.getLearningEvidenceDraftRequests().length, 0)
  assert.equal(testApp.calls.some(({ url }) => url.endsWith('/learning-evidence/agent-create')), false)
})

test('newly issued client registration is retained when code exchange fails and reused on retry', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  testApp.setTokenResponse(async () => { throw new Error('temporary token endpoint failure') })
  await assert.rejects(testApp.client.signIn(), /temporary token endpoint failure/)

  const saved = JSON.parse(testApp.safeStorage.decryptString(await fs.readFile(path.join(testApp.directory, 'chatgpt-credentials.bin'))))
  assert.deepEqual(saved, { client_id: 'oaiapp_test' })
  assert.equal(new URL(testApp.getAuthorizationUrls()[0]).searchParams.get('client_id'), 'dynamic_agent_client')

  testApp.setTokenResponse(null)
  assert.deepEqual(await testApp.client.signIn(), { connected: true, email: 'student@example.test', planUse: true })
  assert.equal(new URL(testApp.getAuthorizationUrls()[1]).searchParams.get('client_id'), 'oaiapp_test')
  assert.equal(testApp.tokenBodies[1].get('client_id'), 'oaiapp_test')
})

test('plan-use cannot proceed when secure storage is unavailable or Linux falls back to basic_text', async (t) => {
  const testApp = await setup({ backend: 'basic_text', platform: 'linux' })
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  assert.deepEqual(await testApp.client.status(), { connected: false, unavailable: true })
  await assert.rejects(testApp.client.signIn(), /Protected credential storage is unavailable/)
  assert.equal(await fs.readdir(testApp.directory).then((files) => files.length), 0)
  const unavailable = await setup({ encryptionAvailable: false })
  t.after(() => fs.rm(unavailable.directory, { recursive: true, force: true }))
  assert.deepEqual(await unavailable.client.status(), { connected: false, unavailable: true })
  await assert.rejects(unavailable.client.signIn(), /Protected credential storage is unavailable/)
  assert.equal(await fs.readdir(unavailable.directory).then((files) => files.length), 0)
})

test('sign-in rejects callback state mismatch, denied consent, missing scope, and invalid ID-token nonce', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  testApp.setCallbackMutator((callback) => callback.replace(/state=[^&]+/, 'state=wrong-state'))
  await assert.rejects(testApp.client.signIn(), /could not be verified/)
  assert.equal(testApp.tokenBodies.length, 0)
  testApp.setCallbackMutator((callback) => callback)
  testApp.setCallbackError('access_denied')
  await assert.rejects(testApp.client.signIn(), /permission was not granted/)
  assert.equal(testApp.tokenBodies.length, 0)
  testApp.setCallbackError('')
  testApp.setTokenResponse(async (_body, { nonce, privateKey }) => ({
    access_token: 'access', refresh_token: 'refresh', expires_in: 3600, scope: 'openid offline_access resource.invoke',
    id_token: await new SignJWT({ nonce }).setProtectedHeader({ alg: 'RS256', kid: 'test-key' }).setIssuer('https://auth.openai.com').setAudience('oaiapp_test').setSubject('student-123').setIssuedAt().setExpirationTime('1h').sign(privateKey),
  }))
  await assert.rejects(testApp.client.signIn(), /did not grant the required/)
  assert.deepEqual(JSON.parse(testApp.safeStorage.decryptString(await fs.readFile(path.join(testApp.directory, 'chatgpt-credentials.bin')))), { client_id: 'oaiapp_test' })
  testApp.setTokenResponse(async (_body, { privateKey }) => ({
    access_token: 'access', refresh_token: 'refresh', expires_in: 3600, scope: SCOPES.join(' '),
    id_token: await new SignJWT({ nonce: 'wrong-nonce' }).setProtectedHeader({ alg: 'RS256', kid: 'test-key' }).setIssuer('https://auth.openai.com').setAudience('oaiapp_test').setSubject('student-123').setIssuedAt().setExpirationTime('1h').sign(privateKey),
  }))
  await assert.rejects(testApp.client.signIn(), /nonce did not match|identity validation failed/)
  assert.deepEqual(JSON.parse(testApp.safeStorage.decryptString(await fs.readFile(path.join(testApp.directory, 'chatgpt-credentials.bin')))), { client_id: 'oaiapp_test' })
})

test('rotating refresh credentials are serialized across concurrent model requests', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  await testApp.expireCredentials()
  let releaseRefresh
  testApp.setRefreshGate(new Promise((resolve) => { releaseRefresh = resolve }))
  testApp.setTokenResponse((body) => body.get('grant_type') === 'refresh_token'
    ? { access_token: 'rotated-access', refresh_token: 'rotated-refresh', expires_in: 3600 }
    : { access_token: 'access-secret', refresh_token: 'refresh-secret', id_token: 'unused', expires_in: 3600, scope: SCOPES.join(' ') })
  const first = testApp.client.models()
  const second = testApp.client.models()
  while (testApp.tokenBodies.filter((body) => body.get('grant_type') === 'refresh_token').length === 0) await new Promise((resolve) => setTimeout(resolve, 1))
  releaseRefresh()
  assert.equal((await first)[0].slug, 'model-a')
  assert.equal((await second)[0].slug, 'model-a')
  assert.equal(testApp.tokenBodies.filter((body) => body.get('grant_type') === 'refresh_token').length, 1)
  const credentials = JSON.parse(testApp.safeStorage.decryptString(await fs.readFile(path.join(testApp.directory, 'chatgpt-credentials.bin'))))
  assert.equal(credentials.refresh_token, 'rotated-refresh')
})

test('usage-limit response is an error and never falls back to a local provider', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  testApp.setResponseError(429, 'subscription_sharing_usage_limit_exceeded')
  const result = await testApp.client.chat({ requestId: 'request-quota-000001', message: 'Explain this', model: 'model-a', language: 'en' }, () => {})
  assert.equal(result.status, 'failed')
  assert.match(result.detail, /limit/i)
  assert.equal(testApp.calls.some(({ url }) => /localhost:4000|litellm|ollama/i.test(url)), false)
})

test('sign-out revokes the renewable session before clearing encrypted local tokens', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  assert.deepEqual(await testApp.client.signOut(), { connected: false, savedAccount: true, email: 'student@example.test', revocationConfirmed: true })
  assert.equal(testApp.getRevocationRequests(), 1)
  const body = new URLSearchParams(testApp.calls.find(({ url }) => url.endsWith('/oauth/revoke')).options.body)
  assert.equal(body.get('token'), 'refresh-secret')
  assert.equal(body.get('token_type_hint'), 'refresh_token')
  assert.equal(body.get('client_id'), 'oaiapp_test')
  const mapping = JSON.parse(testApp.safeStorage.decryptString(await fs.readFile(path.join(testApp.directory, 'chatgpt-credentials.bin'))))
  assert.deepEqual(mapping, { client_id: 'oaiapp_test', subject: 'student-123', email: 'student@example.test' })
  assert.equal((await testApp.client.status()).connected, false)
  await testApp.client.signIn()
  const reauthorization = new URL(testApp.getAuthorizationUrls()[1])
  assert.equal(reauthorization.searchParams.get('client_id'), 'oaiapp_test')
  assert.equal(reauthorization.searchParams.has('agent_name_hint'), false)
  assert.equal(reauthorization.searchParams.has('id_token_hint'), false)
})

test('sign-out clears local tokens and reports unconfirmed remote revocation after retryable failures', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  testApp.setRevocationStatus(503)
  assert.deepEqual(await testApp.client.signOut(), { connected: false, savedAccount: true, email: 'student@example.test', revocationConfirmed: false })
  assert.equal(testApp.getRevocationRequests(), 3)
  const mapping = JSON.parse(testApp.safeStorage.decryptString(await fs.readFile(path.join(testApp.directory, 'chatgpt-credentials.bin'))))
  assert.deepEqual(mapping, { client_id: 'oaiapp_test', subject: 'student-123', email: 'student@example.test' })
})

test('revocation metadata is validated, cached after success, and retried after discovery failure', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  testApp.setOidcMetadata(new Error('temporary discovery failure'))
  assert.equal((await testApp.client.signOut()).revocationConfirmed, false)
  assert.equal(testApp.getOidcRequests(), 1)
  assert.equal(testApp.getRevocationRequests(), 0)

  testApp.setOidcMetadata({ issuer: 'https://auth.openai.com', revocation_endpoint: 'https://auth.openai.com/custom/oauth/revoke' })
  await testApp.client.signIn()
  assert.equal((await testApp.client.signOut()).revocationConfirmed, true)
  assert.equal(testApp.getOidcRequests(), 2)
  assert.equal(testApp.calls.some(({ url }) => url === 'https://auth.openai.com/custom/oauth/revoke'), true)

  await testApp.client.signIn()
  assert.equal((await testApp.client.signOut()).revocationConfirmed, true)
  assert.equal(testApp.getOidcRequests(), 2)
})

test('malformed and untrusted revocation metadata fail closed without sending tokens to it', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()

  for (const metadata of [
    null,
    { issuer: 'https://attacker.example', revocation_endpoint: 'https://auth.openai.com/revoke' },
    { issuer: 'https://auth.openai.com', revocation_endpoint: 'http://auth.openai.com/revoke' },
    { issuer: 'https://auth.openai.com', revocation_endpoint: 'https://attacker.example/revoke' },
    { issuer: 'https://auth.openai.com', revocation_endpoint: 'https://user@auth.openai.com/revoke' },
    { issuer: 'https://auth.openai.com', revocation_endpoint: 7 },
  ]) {
    testApp.setOidcMetadata(metadata)
    await testApp.client.signOut()
    assert.equal(testApp.getRevocationRequests(), 0)
    assert.equal(testApp.calls.some(({ url }) => url.includes('attacker.example') || url.startsWith('http://auth.openai.com')), false)
    await testApp.client.signIn()
  }
  assert.equal(testApp.calls.filter(({ url }) => url === 'https://auth.openai.com/api/accounts/oauth/token').length, 7)
  assert.equal(testApp.calls.some(({ url }) => url.includes('attacker.example') || url.startsWith('http://auth.openai.com')), false)
})

test('sign-in clears the callback timeout and closes its listener when opening the browser fails', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  testApp.setOpenExternalError(new Error('browser unavailable'))
  await assert.rejects(testApp.client.signIn(), /browser unavailable/)
  assert.equal(testApp.tokenBodies.length, 0)
  testApp.setOpenExternalError(null)
  assert.deepEqual(await testApp.client.signIn(), { connected: true, email: 'student@example.test', planUse: true })
})

test('unreadable encrypted credentials have a confirmed local recovery that preserves host identity', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  const hostId = await fs.readFile(path.join(testApp.directory, 'chatgpt-host-id'), 'utf8')
  await fs.writeFile(path.join(testApp.directory, 'chatgpt-credentials.bin'), Buffer.from('corrupt encrypted credential data'))

  assert.deepEqual(await testApp.client.status(), { connected: false, recoveryRequired: true })
  await assert.rejects(testApp.client.recoverUnreadableCredentials(false), /Confirm local credential removal/)
  const recovery = await testApp.client.recoverUnreadableCredentials(true)
  assert.deepEqual(recovery, { connected: false, savedAccount: false, recoveredUnreadableCredentials: true, revocationConfirmed: false })
  assert.equal(await fs.readFile(path.join(testApp.directory, 'chatgpt-host-id'), 'utf8'), hostId)
  await assert.rejects(fs.stat(path.join(testApp.directory, 'chatgpt-credentials.bin')), { code: 'ENOENT' })
  assert.deepEqual(await testApp.client.signIn(), { connected: true, email: 'student@example.test', planUse: true })
  assert.equal(new URL(testApp.getAuthorizationUrls()[1]).searchParams.get('client_id'), 'dynamic_agent_client')
})

test('forgetting a signed-out account keeps the host ID and permits a fresh dynamic registration', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  await testApp.client.signOut()
  const hostBefore = await fs.readFile(path.join(testApp.directory, 'chatgpt-host-id'), 'utf8')
  await testApp.client.forgetAccount()
  assert.equal(await fs.readdir(testApp.directory).then((files) => files.includes('chatgpt-credentials.bin')), false)
  assert.equal(await fs.readFile(path.join(testApp.directory, 'chatgpt-host-id'), 'utf8'), hostBefore)
  await testApp.client.signIn()
  assert.equal(new URL(testApp.getAuthorizationUrls()[1]).searchParams.get('client_id'), 'dynamic_agent_client')
})

test('chat cancellation aborts the in-flight Responses stream', async (t) => {
  const testApp = await setup()
  t.after(() => fs.rm(testApp.directory, { recursive: true, force: true }))
  await testApp.client.signIn()
  testApp.setStreamMode('cancel')
  const operation = testApp.client.chat({ requestId: 'request-cancel-000001', message: 'Explain this topic', model: 'model-a', language: 'en' }, () => {})
  while (!testApp.getResponseRequest()) await new Promise((resolve) => setTimeout(resolve, 1))
  testApp.client.cancel('request-cancel-000001')
  assert.deepEqual(await operation, { status: 'cancelled' })
})

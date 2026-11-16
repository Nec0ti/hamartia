const assert = require('node:assert/strict')
const test = require('node:test')
const { diagnosticPracticeState, diagnosticRequests, isSettingsRequestUrl, settingsRoutePattern, withDeadline, withTimeout } = require('../smokeDeadline.cjs')

test('smoke deadline preserves successful results and rejects a stalled operation with diagnostics', async () => {
  assert.equal(await withTimeout(Promise.resolve('ready'), 50, 'startup'), 'ready')
  await assert.rejects(
    withTimeout(new Promise(() => {}), 5, 'startup', () => '; last request: /settings'),
    /startup timed out after 5ms; last request: \/settings/,
  )
})

test('settings route matcher accepts same-origin slash and query variants but rejects unrelated URLs', () => {
  const origin = 'http://127.0.0.1:8000'
  assert.equal(isSettingsRequestUrl(`${origin}/settings`, origin), true)
  assert.equal(isSettingsRequestUrl(`${origin}/settings/?initial=1`, origin), true)
  assert.equal(isSettingsRequestUrl(`${origin}/settings?initial=1`, origin), true)
  assert.equal(isSettingsRequestUrl('https://attacker.invalid/settings', origin), false)
  assert.equal(isSettingsRequestUrl(`${origin}/other/settings`, origin), false)
  const routePattern = settingsRoutePattern(origin)
  assert.equal(routePattern.test(`${origin}/settings?initial=1`), true)
  assert.equal(routePattern.test(`${origin}/settings/`), true)
  assert.equal(routePattern.test('http://127.0.0.1.evil.invalid:8000/settings'), false)
})

test('browser diagnostics redact request URLs, query strings, and JSON bodies', () => {
  const projected = diagnosticRequests([{ method: 'POST', origin: 'http://127.0.0.1:8000', path: '/settings', url: 'http://127.0.0.1:8000/settings?token=smoke-secret', body: { api_key: 'smoke-secret' } }])
  assert.deepEqual(projected, [{ method: 'POST', origin: 'http://127.0.0.1:8000', path: '/settings' }])
  assert.equal(JSON.stringify(projected).includes('smoke-secret'), false)
})

test('practice smoke failure diagnostics omit payloads, response bodies, and query strings', () => {
  const projected = diagnosticPracticeState({
    language: 'en',
    payload: { workflow: 'practice-entry', message: 'private synthetic prompt' },
    draftHttp: { status: 200, body: 'private response body' },
    draft: { missing: ['topic'], questions: ['private clarification'] },
    liveText: ['private answer'],
    pageErrors: ['private exception'],
    consoleErrors: [{ text: 'Content Security Policy blocked https://api.example.test?secret=private' }],
    failedResponses: [{ url: 'https://api.example.test/social?token=private', status: 503 }],
    appRequests: [{ method: 'POST', origin: 'https://api.example.test', path: '/social?token=private', query: { token: 'private' }, body: { api_key: 'private' } }],
  })
  assert.deepEqual(projected, {
    language: 'en', workflow: 'practice-entry', draftHttpStatus: 200,
    missingFieldCount: 1, clarificationCount: 1, liveTextCount: 1, pageErrorCount: 1,
    cspConsoleError: true,
    failedResponses: [{ origin: 'https://api.example.test', path: '/social', status: 503 }],
    requests: [{ method: 'POST', origin: 'https://api.example.test', path: '/social' }],
  })
  const rendered = JSON.stringify(projected)
  for (const privateValue of ['private synthetic prompt', 'private response body', 'private clarification', 'private answer', 'private exception', 'api_key', 'token=private']) {
    assert.equal(rendered.includes(privateValue), false)
  }
})

test('smoke deadline races a stalled operation, awaits cleanup, and rejects with diagnostics', async () => {
  let cleanupCalled = false
  await assert.rejects(
    withDeadline(() => new Promise(() => {}), 5, () => '; phase: fixture', async () => {
      await new Promise((resolve) => setTimeout(resolve, 5))
      cleanupCalled = true
    }),
    /Browser smoke exceeded 5ms; phase: fixture/,
  )
  assert.equal(cleanupCalled, true)
})

test('smoke deadline cannot resolve successfully after timeout while cleanup is pending', async () => {
  await assert.rejects(
    withDeadline(() => new Promise((resolve) => setTimeout(() => resolve('late success'), 10)), 5, () => '; phase: race',
      () => new Promise((resolve) => setTimeout(resolve, 30))),
    /Browser smoke exceeded 5ms; phase: race/,
  )
})

test('smoke deadline surfaces cleanup failure instead of hiding failed reaping', async () => {
  await assert.rejects(
    withDeadline(() => new Promise(() => {}), 5, () => '; phase: cleanup', () => Promise.reject(new Error('fixture retained'))),
    /cleanup failed: fixture retained/,
  )
})

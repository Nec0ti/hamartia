const assert = require('node:assert/strict')
const test = require('node:test')
const { isSettingsRequestUrl, withDeadline, withTimeout } = require('../smokeDeadline.cjs')

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

const assert = require('node:assert/strict')
const test = require('node:test')
const { withTimeout } = require('../smokeDeadline.cjs')

test('smoke deadline preserves successful results and rejects a stalled operation with diagnostics', async () => {
  assert.equal(await withTimeout(Promise.resolve('ready'), 50, 'startup'), 'ready')
  await assert.rejects(
    withTimeout(new Promise(() => {}), 5, 'startup', () => '; last request: /settings'),
    /startup timed out after 5ms; last request: \/settings/,
  )
})

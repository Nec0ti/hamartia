const assert = require('node:assert/strict')
const test = require('node:test')
const { gracefulStop } = require('../shutdownFlow.cjs')

test('graceful shutdown waits for backend exit before restore can proceed', async () => {
  const events = []
  await gracefulStop({
    requestShutdown: async () => { events.push('request'); return { ok: true } },
    waitForExit: async () => { events.push('exit') },
  })
  events.push('restore')
  assert.deepEqual(events, ['request', 'exit', 'restore'])
})

test('graceful shutdown rejects a refused request without waiting or restoring', async () => {
  let waited = false
  await assert.rejects(gracefulStop({
    requestShutdown: async () => ({ ok: false, status: 403 }),
    waitForExit: async () => { waited = true },
  }), /rejected graceful shutdown/)
  assert.equal(waited, false)
})

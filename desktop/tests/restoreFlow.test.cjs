const assert = require('node:assert/strict')
const test = require('node:test')
const { restoreWithRestart } = require('../restoreFlow.cjs')

test('backup restore stops the server, applies the backup, and restarts the server in order', async () => {
  const events = []
  const status = await restoreWithRestart({
    stop: async () => events.push('stop'),
    restore: async () => { events.push('restore'); return 'success' },
    restart: async () => events.push('restart'),
  })
  assert.equal(status, 'success')
  assert.deepEqual(events, ['stop', 'restore', 'restart'])
})

test('failed restores still restart the server', async () => {
  const events = []
  const status = await restoreWithRestart({
    stop: async () => events.push('stop'),
    restore: async () => { events.push('restore'); throw new Error('invalid archive') },
    restart: async () => events.push('restart'),
  })
  assert.equal(status, 'failed')
  assert.deepEqual(events, ['stop', 'restore', 'restart'])
})

test('a stop failure skips the restore but still attempts to restart', async () => {
  const events = []
  const status = await restoreWithRestart({
    stop: async () => { events.push('stop'); throw new Error('still running') },
    restore: async () => { events.push('restore'); return 'success' },
    restart: async () => events.push('restart'),
  })
  assert.equal(status, 'failed')
  assert.deepEqual(events, ['stop', 'restart'])
})

test('restart failures are reported separately', async () => {
  const status = await restoreWithRestart({
    stop: async () => {},
    restore: async () => 'success',
    restart: async () => { throw new Error('backend unavailable') },
  })
  assert.equal(status, 'restartFailed')
})

test('restore and restart remain pending while the backup is still being applied', async () => {
  let finishRestore
  let restartCalled = false
  const pendingRestore = new Promise((resolve) => { finishRestore = resolve })
  const operation = restoreWithRestart({
    stop: async () => {},
    restore: async () => pendingRestore,
    restart: async () => { restartCalled = true },
  })
  await new Promise((resolve) => setTimeout(resolve, 25))
  assert.equal(restartCalled, false)
  finishRestore('success')
  assert.equal(await operation, 'success')
  assert.equal(restartCalled, true)
})

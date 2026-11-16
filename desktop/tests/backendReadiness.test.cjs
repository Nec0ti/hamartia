const assert = require('node:assert/strict')
const test = require('node:test')
const { isDesktopBackendReady } = require('../backendReadiness.cjs')

test('a fake HTTP 200 without token verification cannot satisfy desktop readiness', () => {
  const response = new Response('OK', { status: 200 })
  assert.equal(isDesktopBackendReady(response), false)
})

test('desktop readiness requires the backend token-verification response', () => {
  const response = new Response(null, {
    status: 204,
    headers: { 'X-Hamartia-Control-Token-Verified': 'true' },
  })
  assert.equal(isDesktopBackendReady(response), true)
})

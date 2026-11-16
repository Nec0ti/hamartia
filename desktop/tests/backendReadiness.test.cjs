const assert = require('node:assert/strict')
const { createHmac } = require('node:crypto')
const { EventEmitter } = require('node:events')
const http = require('node:http')
const test = require('node:test')
const { isDesktopBackendReady, waitUntilReady } = require('../backendReadiness.cjs')

const TOKEN = 'launch-specific-secret'

function child() {
  const process = new EventEmitter()
  process.exitCode = null
  return process
}

async function withServer(handler, run) {
  const server = http.createServer(handler)
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  try {
    await run(`http://127.0.0.1:${server.address().port}`)
  } finally {
    await new Promise((resolve) => server.close(resolve))
  }
}

test('readiness rejects a mismatched or malformed HMAC proof', () => {
  const wrong = new Response(null, { status: 204, headers: { 'X-Hamartia-Control-Proof': '0'.repeat(64) } })
  const malformed = new Response(null, { status: 204, headers: { 'X-Hamartia-Control-Proof': 'true' } })
  assert.equal(isDesktopBackendReady(wrong, 'a'.repeat(64), TOKEN), false)
  assert.equal(isDesktopBackendReady(malformed, 'a'.repeat(64), TOKEN), false)
})

test('a real loopback fake server with a plausible 204 and old public marker times out', async () => {
  const nonces = new Set()
  await withServer((request, response) => {
    if (request.url === '/healthcheck/ready') {
      response.writeHead(200).end('ready')
    } else {
      nonces.add(request.headers['x-hamartia-control-nonce'])
      response.writeHead(204, { 'X-Hamartia-Control-Token-Verified': 'true' }).end()
    }
  }, async (url) => {
    await assert.rejects(waitUntilReady(child(), url, TOKEN, { timeoutMs: 60, intervalMs: 5 }), /Timed out/)
  })
  assert.ok(nonces.size > 0)
  assert.ok([...nonces].every((nonce) => /^[0-9a-f]{64}$/.test(nonce)))
})

test('a valid proof arriving after the readiness deadline is rejected', async () => {
  await withServer((request, response) => {
    if (request.url === '/healthcheck/ready') return response.writeHead(200).end('ready')
    const nonce = request.headers['x-hamartia-control-nonce']
    const proof = createHmac('sha256', TOKEN).update(nonce, 'ascii').digest('hex')
    setTimeout(() => response.writeHead(204, { 'X-Hamartia-Control-Proof': proof }).end(), 80)
  }, async (url) => {
    await assert.rejects(waitUntilReady(child(), url, TOKEN, { timeoutMs: 40, intervalMs: 5 }), /Timed out/)
  })
})

test('each readiness retry gets a new nonce', async () => {
  const nonces = []
  await withServer((request, response) => {
    if (request.url === '/healthcheck/ready') return response.writeHead(200).end('ready')
    const nonce = request.headers['x-hamartia-control-nonce']
    nonces.push(nonce)
    if (nonces.length < 2) return response.writeHead(403).end()
    const proof = createHmac('sha256', TOKEN).update(nonce, 'ascii').digest('hex')
    response.writeHead(204, { 'X-Hamartia-Control-Proof': proof }).end()
  }, async (url) => {
    await waitUntilReady(child(), url, TOKEN, { timeoutMs: 1000, intervalMs: 5 })
  })
  assert.equal(nonces.length, 2)
  assert.notEqual(nonces[0], nonces[1])
})

test('readiness succeeds only when the loopback server proves the fresh nonce', async () => {
  let nonceCount = 0
  await withServer((request, response) => {
    if (request.url === '/healthcheck/ready') return response.writeHead(200).end('ready')
    const nonce = request.headers['x-hamartia-control-nonce']
    nonceCount += 1
    const proof = createHmac('sha256', TOKEN).update(nonce, 'ascii').digest('hex')
    response.writeHead(204, { 'X-Hamartia-Control-Proof': proof }).end()
  }, async (url) => {
    await waitUntilReady(child(), url, TOKEN, { timeoutMs: 1000, intervalMs: 5 })
  })
  assert.equal(nonceCount, 1)
})

test('readiness rejects if the child exits during the proof request', async () => {
  const spawned = child()
  await withServer((request, response) => {
    if (request.url === '/healthcheck/ready') return response.writeHead(200).end('ready')
    spawned.exitCode = 1
    const nonce = request.headers['x-hamartia-control-nonce']
    const proof = createHmac('sha256', TOKEN).update(nonce, 'ascii').digest('hex')
    response.writeHead(204, { 'X-Hamartia-Control-Proof': proof }).end()
  }, async (url) => {
    await assert.rejects(waitUntilReady(spawned, url, TOKEN, { timeoutMs: 1000 }), /Backend exited with code 1/)
  })
})

test('readiness fails immediately for a child that already exited', async () => {
  const exited = child()
  exited.exitCode = 2
  await assert.rejects(waitUntilReady(exited, 'http://127.0.0.1:1', TOKEN), /Backend exited with code 2/)
})

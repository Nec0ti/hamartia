const { createHmac, randomBytes, timingSafeEqual } = require('node:crypto')

function isDesktopBackendReady(response, nonce, controlToken) {
  const proof = response.headers.get('X-Hamartia-Control-Proof')
  if (response.status !== 204 || !/^[0-9a-f]{64}$/.test(proof || '')) return false
  const expected = createHmac('sha256', controlToken).update(nonce, 'ascii').digest()
  return timingSafeEqual(Buffer.from(proof, 'hex'), expected)
}

async function waitUntilReady(child, url, controlToken, { fetchImpl = fetch, timeoutMs = 30_000, intervalMs = 200 } = {}) {
  const deadline = Date.now() + timeoutMs
  let spawnError
  child.once('error', (error) => { spawnError = error })

  while (Date.now() < deadline) {
    if (spawnError) throw spawnError
    if (child.exitCode !== null) throw new Error(`Backend exited with code ${child.exitCode}`)
    try {
      const response = await fetchImpl(`${url}/healthcheck/ready`, { signal: AbortSignal.timeout(1000) })
      if (response.ok) {
        const nonce = randomBytes(32).toString('hex')
        const proof = await fetchImpl(`${url}/desktop/ready`, {
          headers: { 'X-Hamartia-Control-Nonce': nonce },
          signal: AbortSignal.timeout(1000),
        })
        if (isDesktopBackendReady(proof, nonce, controlToken) && Date.now() < deadline) {
          if (spawnError) throw spawnError
          if (child.exitCode !== null) throw new Error(`Backend exited with code ${child.exitCode}`)
          return
        }
      }
    } catch {
      if (spawnError) throw spawnError
      if (child.exitCode !== null) throw new Error(`Backend exited with code ${child.exitCode}`)
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }

  throw new Error('Timed out waiting for the local backend')
}

module.exports = { isDesktopBackendReady, waitUntilReady }

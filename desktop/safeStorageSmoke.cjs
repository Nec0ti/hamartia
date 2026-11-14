const crypto = require('node:crypto')

async function probeSafeStorage({ safeStorage, chatgpt, platform = process.platform, mode = 'protected', expectedBackend }) {
  if (!['protected', 'rejected'].includes(mode)) throw new Error('Unknown safeStorage smoke expectation.')
  const backend = platform === 'linux' ? safeStorage.getSelectedStorageBackend() : null
  const available = safeStorage.isEncryptionAvailable()
  let roundTrip = false

  if (available) {
    try {
      const sample = crypto.randomBytes(32).toString('base64url')
      const encrypted = safeStorage.encryptString(sample)
      roundTrip = safeStorage.decryptString(encrypted) === sample
    } catch {
      throw new Error('Native safeStorage in-memory round-trip failed.')
    }
  }

  const status = await chatgpt.status()
  const protectedStorageAvailable = status.unavailable !== true
  if (!available || !roundTrip) throw new Error('Native safeStorage encryption is unavailable or failed its in-memory round-trip.')
  if (expectedBackend && backend !== expectedBackend) throw new Error(`Unexpected native safeStorage backend: ${backend || 'unknown'}.`)
  if (protectedStorageAvailable !== (mode === 'protected')) {
    throw new Error(`The production credential-storage policy did not match the ${mode} smoke expectation.`)
  }

  return { platform, backend, available, roundTrip, protectedStorageAvailable }
}

module.exports = { probeSafeStorage }

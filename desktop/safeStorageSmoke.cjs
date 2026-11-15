const crypto = require('node:crypto')

function assertSafeStorageMetadata(metadata, { platform = process.platform, mode = 'protected', expectedBackend }) {
  if (!['protected', 'rejected'].includes(mode)) throw new Error('Unknown safeStorage smoke expectation.')
  const protectedMode = mode === 'protected'
  if (metadata.platform !== platform) throw new Error('Unexpected safeStorage smoke platform.')
  if (expectedBackend && metadata.backend !== expectedBackend) {
    throw new Error(`Unexpected native safeStorage backend: ${metadata.backend || 'unknown'}.`)
  }
  if (metadata.available !== protectedMode || metadata.roundTrip !== protectedMode) {
    throw new Error(`Native safeStorage availability and round-trip did not match the ${mode} smoke expectation.`)
  }
  if (metadata.protectedStorageAvailable !== protectedMode) {
    throw new Error(`The production credential-storage policy did not match the ${mode} smoke expectation.`)
  }
}

async function probeSafeStorage({ safeStorage, chatgpt, platform = process.platform, mode = 'protected', expectedBackend }) {
  if (!['protected', 'rejected'].includes(mode)) throw new Error('Unknown safeStorage smoke expectation.')
  const backend = platform === 'linux' ? safeStorage.getSelectedStorageBackend() : null
  const available = safeStorage.isEncryptionAvailable()
  let roundTrip = false

  if (mode === 'protected' && available) {
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
  if (mode === 'protected' && (!available || !roundTrip)) {
    throw new Error('Native safeStorage encryption is unavailable or failed its in-memory round-trip.')
  }
  const metadata = { platform, backend, available, roundTrip, protectedStorageAvailable }
  assertSafeStorageMetadata(metadata, { platform, mode, expectedBackend })
  return metadata
}

module.exports = { assertSafeStorageMetadata, probeSafeStorage }

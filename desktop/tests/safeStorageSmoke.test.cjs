const assert = require('node:assert/strict')
const test = require('node:test')
const { assertSafeStorageMetadata, probeSafeStorage } = require('../safeStorageSmoke.cjs')

function storageFixture(backend) {
  return {
    isEncryptionAvailable: () => true,
    getSelectedStorageBackend: () => backend,
    encryptString: (value) => Buffer.from(`fixture:${value}`),
    decryptString: (value) => value.toString().slice('fixture:'.length),
  }
}

test('safeStorage smoke emits only native metadata for a protected round-trip', async () => {
  const status = { unavailable: false }
  const result = await probeSafeStorage({
    safeStorage: storageFixture('gnome_libsecret'),
    chatgpt: { status: async () => status },
    platform: 'linux',
    expectedBackend: 'gnome_libsecret',
  })

  assert.deepEqual(result, {
    platform: 'linux', backend: 'gnome_libsecret', available: true,
    roundTrip: true, protectedStorageAvailable: true,
  })
  assert.equal(JSON.stringify(result).includes('fixture:'), false)
})

test('packaged smoke marker validation accepts protected and rejected native metadata only', () => {
  assert.doesNotThrow(() => assertSafeStorageMetadata({
    platform: 'win32', backend: null, available: true, roundTrip: true, protectedStorageAvailable: true,
  }, { platform: 'win32', mode: 'protected' }))
  assert.doesNotThrow(() => assertSafeStorageMetadata({
    platform: 'linux', backend: 'basic_text', available: false, roundTrip: false, protectedStorageAvailable: false,
  }, { platform: 'linux', mode: 'rejected', expectedBackend: 'basic_text' }))
  for (const metadata of [
    { platform: 'linux', backend: 'gnome_libsecret', available: true, roundTrip: true, protectedStorageAvailable: false },
    { platform: 'linux', backend: 'basic_text', available: true, roundTrip: false, protectedStorageAvailable: false },
    { platform: 'linux', backend: 'basic_text', available: false, roundTrip: true, protectedStorageAvailable: false },
  ]) {
    assert.throws(() => assertSafeStorageMetadata(metadata, {
      platform: 'linux', mode: 'rejected', expectedBackend: 'basic_text',
    }))
  }
})

test('basic_text smoke uses the production guard and expects protected storage rejection', async () => {
  const safeStorage = storageFixture('basic_text')
  safeStorage.isEncryptionAvailable = () => false
  safeStorage.encryptString = () => { throw new Error('Rejected mode must not encrypt.') }
  safeStorage.decryptString = () => { throw new Error('Rejected mode must not decrypt.') }
  const result = await probeSafeStorage({
    safeStorage,
    chatgpt: { status: async () => ({ unavailable: true }) },
    platform: 'linux', mode: 'rejected', expectedBackend: 'basic_text',
  })

  assert.equal(result.available, false)
  assert.equal(result.roundTrip, false)
  assert.equal(result.protectedStorageAvailable, false)
})

test('safeStorage smoke fails when the backend or production policy differs from its expectation', async () => {
  const chatgpt = { status: async () => ({ unavailable: true }) }

  await assert.rejects(probeSafeStorage({
    safeStorage: storageFixture('basic_text'), chatgpt, platform: 'linux', expectedBackend: 'gnome_libsecret',
  }), /Unexpected native safeStorage backend/)
  await assert.rejects(probeSafeStorage({
    safeStorage: storageFixture('gnome_libsecret'), chatgpt, platform: 'linux', expectedBackend: 'gnome_libsecret',
  }), /production credential-storage policy/)
})

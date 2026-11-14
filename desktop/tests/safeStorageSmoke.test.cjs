const assert = require('node:assert/strict')
const test = require('node:test')
const { probeSafeStorage } = require('../safeStorageSmoke.cjs')

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

test('basic_text smoke uses the production guard and expects protected storage rejection', async () => {
  const result = await probeSafeStorage({
    safeStorage: storageFixture('basic_text'),
    chatgpt: { status: async () => ({ unavailable: true }) },
    platform: 'linux', mode: 'rejected', expectedBackend: 'basic_text',
  })

  assert.equal(result.roundTrip, true)
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

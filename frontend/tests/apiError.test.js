import assert from 'node:assert/strict'
import test from 'node:test'
import { handleApiError } from '../src/services/apiError.js'

test('API failures become localized messages instead of leaking backend details', () => {
  const t = (key) => `localized:${key}`
  assert.deepEqual(handleApiError(new Error('offline'), t), {
    ok: false, status: 0, detail: 'localized:error.network',
  })
  assert.equal(handleApiError({ response: { status: 404, data: { detail: 'Soru bulunamadı' } } }, t).detail, 'localized:error.notFound')
  assert.equal(handleApiError({ response: { status: 413, data: { detail: 'A detailed server error' } } }, t).detail, 'localized:error.fileTooLarge')
  assert.equal(handleApiError({ response: { status: 502, data: { detail: 'Yerel model isteği başarısız oldu' } } }, t).detail, 'localized:error.localAi')
  assert.equal(handleApiError({ response: { status: 500, data: { detail: 'Storage unavailable: /private/path' } } }, t).detail, 'localized:error.server')
})

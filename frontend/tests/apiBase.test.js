import assert from 'node:assert/strict'
import test from 'node:test'
import { getApiBase } from '../src/services/apiBase.js'

test('API base honors overrides, uses same-origin in production, and localhost in development', () => {
  assert.equal(getApiBase({ VITE_API_BASE: 'http://127.0.0.1:8000', PROD: true }), 'http://127.0.0.1:8000')
  assert.equal(getApiBase({ VITE_API_BASE: '', PROD: true }), '')
  assert.equal(getApiBase({ PROD: true }), '')
  assert.equal(getApiBase({ PROD: false }), 'http://localhost:8000')
})

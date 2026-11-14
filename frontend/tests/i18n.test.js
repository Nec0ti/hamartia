import assert from 'node:assert/strict'
import test from 'node:test'
import { getSavedLanguage, LANGUAGE_STORAGE_KEY, normalizeLanguage, translate } from '../src/i18n/core.js'

test('language preference accepts only English and Turkish', () => {
  assert.equal(normalizeLanguage('en'), 'en')
  assert.equal(normalizeLanguage('tr'), 'tr')
  assert.equal(normalizeLanguage('tr-TR'), 'en')
  assert.equal(normalizeLanguage('fr'), 'en')
})

test('fresh or invalid storage defaults to English and storage failures are safe', () => {
  assert.equal(getSavedLanguage({ getItem: () => null }), 'en')
  assert.equal(getSavedLanguage({ getItem: () => 'tr' }), 'tr')
  assert.equal(getSavedLanguage({ getItem: () => 'fr' }), 'en')
  assert.equal(getSavedLanguage({ getItem: () => { throw new Error('blocked') } }), 'en')
  assert.equal(LANGUAGE_STORAGE_KEY, 'hamartia.language')
})

test('missing translations fall back to the English key', () => {
  assert.equal(translate('missing.translation.key', 'en'), 'missing.translation.key')
})

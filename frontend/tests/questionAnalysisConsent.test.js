import test from 'node:test'
import assert from 'node:assert/strict'
import {
  prepareQuestionAnalysisConsent,
  sendApprovedQuestionAnalysis,
} from '../src/services/questionAnalysisConsent.js'

function previewFixture(overrides = {}) {
  return {
    consent_id: 'one-use-fixture-id',
    endpoint_class: 'remote',
    endpoint_authority: 'provider.example.test:443',
    scheme: 'https',
    model: 'fixture-model',
    payload: {
      analysis_instructions_included: true,
      ocr_text_included: true,
      ocr_text_has_content: true,
      image_filename_included: true,
      saved_image_included: false,
    },
    auth_setting_category: 'blank',
    auth_value_category: 'placeholder',
    ...overrides,
  }
}

test('preview fetch does not call analysis transport, and decline sends nothing', async () => {
  const calls = []
  const questionsApi = {
    analysisPreview: async (id) => {
      calls.push(['preview', id])
      return previewFixture()
    },
    cancelAnalysisPreview: async (id, consentId) => calls.push(['cancel', id, consentId]),
    analyze: async (...args) => calls.push(['analyze', ...args]),
  }

  const preview = await prepareQuestionAnalysisConsent(questionsApi, 'q-1')
  assert.equal(preview.consent_id, 'one-use-fixture-id')
  assert.equal(calls.length, 1)
  assert.equal(calls[0][0], 'preview')
  assert.equal(await sendApprovedQuestionAnalysis(questionsApi, 'q-1', preview, false), null)
  assert.deepEqual(calls, [
    ['preview', 'q-1'],
    ['cancel', 'q-1', 'one-use-fixture-id'],
  ])
})

test('approval sends exactly once with the preview consent ID', async () => {
  const calls = []
  const questionsApi = {
    analysisPreview: async () => previewFixture(),
    analyze: async (...args) => { calls.push(args); return { id: args[0] } },
  }
  const preview = await prepareQuestionAnalysisConsent(questionsApi, 'q-2')
  const result = await sendApprovedQuestionAnalysis(questionsApi, 'q-2', preview, true)
  assert.deepEqual(calls, [['q-2', 'one-use-fixture-id']])
  assert.deepEqual(result, { id: 'q-2' })
})

test('incomplete preview fails closed before sending', async () => {
  let sends = 0
  const questionsApi = {
    analysisPreview: async () => ({ consent_id: 'id', endpoint_class: 'unknown' }),
    analyze: async () => { sends += 1 },
  }
  await assert.rejects(prepareQuestionAnalysisConsent(questionsApi, 'q-3'))
  await assert.rejects(sendApprovedQuestionAnalysis(questionsApi, 'q-3', null, true))
  assert.equal(sends, 0)
})

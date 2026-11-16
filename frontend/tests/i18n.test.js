import assert from 'node:assert/strict'
import test from 'node:test'
import { getSavedLanguage, LANGUAGE_STORAGE_KEY, messages, normalizeLanguage, translate } from '../src/i18n/core.js'

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

test('every message has English and Turkish text', () => {
  for (const [key, localized] of Object.entries(messages)) {
    assert.equal(typeof localized.en, 'string', `${key} is missing English text`)
    assert.equal(typeof localized.tr, 'string', `${key} is missing Turkish text`)
  }
})

test('configured Study Agent server option is labeled in both locales with remote-endpoint caveat', () => {
  assert.equal(translate('agent.configuredProvider', 'en'), 'Local or remote OpenAI-compatible server (optional)')
  assert.equal(translate('agent.configuredProvider', 'tr'), 'Yerel veya uzak OpenAI uyumlu sunucu (isteğe bağlı)')
  assert.match(translate('agent.configuredProviderInfo', 'en'), /URL may point to a remote host/)
  assert.match(translate('agent.configuredProviderInfo', 'tr'), /uzaktaki bir ana makineyi/)
  assert.match(translate('settings.localAiServerUrl', 'en'), /local or remote/)
  assert.match(translate('settings.localAiServerUrl', 'tr'), /yerel veya uzak/)
})

test('question analysis action and consent explain its configured endpoint and payload in both locales', () => {
  assert.equal(translate('questions.reviewWithAI', 'en'), 'Review with AI')
  assert.equal(translate('questions.reviewWithAI', 'tr'), 'Yapay zekâyla incele')
  assert.match(translate('questions.aiConsentEndpointNote', 'en'), /may be local or remote/)
  assert.match(translate('questions.aiConsentEndpointNote', 'tr'), /yerel veya uzak olabilir/)
  assert.match(translate('questions.aiConsentEndpoint', 'en', { hostClass: 'remote', authority: 'provider.example.test:443', scheme: 'HTTPS', model: 'fixture' }), /provider\.example\.test:443/)
  assert.match(translate('questions.aiConsentQuestionText', 'en'), /question \/ OCR text/)
  assert.match(translate('questions.aiConsentSavedImage', 'tr'), /görselinin verisi/)
  assert.match(translate('questions.aiConsentAuthValueConfigured', 'en'), /value is hidden/)
  assert.match(translate('questions.aiConsentAuthValueConfigured', 'tr'), /değeri gösterilmez/)
  assert.match(translate('error.analysisPayloadTooLarge', 'en'), /Shorten the text or use a smaller image/)
  assert.match(translate('error.analysisPayloadTooLarge', 'tr'), /Metni kısalt veya daha küçük görsel/)
  assert.match(translate('questions.textByteLimit', 'en'), /64 KiB of UTF-8/)
  assert.match(translate('questions.textByteLimit', 'tr'), /UTF-8 olarak 64 KiB/)
})

test('Study Agent practice entry explains evidence, missing fields, and approval in both languages', () => {
  assert.match(translate('agent.practiceEntryHint', 'en'), /never fills them in/)
  assert.match(translate('agent.practiceEntryHint', 'tr'), /kendisi doldurmaz/)
  assert.match(translate('agent.practiceEntryConsent', 'en'), /only after you approve it/)
  assert.match(translate('agent.practiceEntryLocalConsent', 'tr', { endpoint: 'http://localhost:4000', key: 'key note' }), /tam olarak şu yapılandırılmış uç noktaya gönderilir/)
  assert.equal(translate('agent.practiceSave', 'en'), 'Approve this preview and save')
  assert.equal(translate('agent.practiceSave', 'tr'), 'Bu önizlemeyi onayla ve kaydet')
})

test('Study Agent missed-question capture explains exact text, optional skips, payload, and approval in both languages', () => {
  assert.equal(translate('agent.workflowQuestion', 'en'), 'Capture a missed question')
  assert.equal(translate('agent.workflowQuestion', 'tr'), 'Kaçırdığım soruyu kaydet')
  assert.match(translate('agent.questionCapturePrompt', 'en'), /exact problem text as one message/)
  assert.match(translate('agent.questionCapturePrompt', 'tr'), /tam metnini tek mesaj/)
  assert.match(translate('agent.questionCaptureHint', 'en'), /type “skip”/)
  assert.match(translate('agent.questionCaptureHint', 'tr'), /“atla” yaz/)
  assert.match(translate('agent.questionCaptureHint', 'en'), /No image, URL, analysis, tag, or curriculum data/)
  assert.match(translate('agent.questionCaptureConsent', 'en'), /only the student messages/)
  assert.match(translate('agent.questionCaptureLocalConsent', 'tr', { endpoint: 'https://provider.example/v1', key: 'anahtar bilgisi' }), /yapılandırılmış uç noktaya gönderilir/)
  assert.match(translate('agent.questionCaptureNoWrite', 'en'), /Only approval saves the record/)
  assert.equal(translate('agent.questionCaptureSave', 'tr'), 'Bu önizlemeyi onayla ve kaydet')
})

test('Study Agent branch-exam capture describes explicit fields, host scoring, and approval in both languages', () => {
  assert.equal(translate('agent.workflowExam', 'en'), 'Capture a branch exam')
  assert.equal(translate('agent.workflowExam', 'tr'), 'Branş denemesi kaydet')
  assert.match(translate('agent.examCaptureHint', 'en'), /one single-subject branch exam/)
  assert.match(translate('agent.examCaptureHint', 'tr'), /Tek dersli bir branş denemesi/)
  assert.match(translate('agent.examCaptureHint', 'en'), /never assumes today, counts, timing, exam type, or score/)
  assert.match(translate('agent.examCapturePrompt', 'tr'), /YYYY-MM-DD/)
  assert.match(translate('agent.examCaptureConsent', 'en'), /only the student messages/)
  assert.match(translate('agent.examCaptureLocalConsent', 'tr', { endpoint: 'https://provider.example/v1', key: 'anahtar bilgisi' }), /yapılandırılmış uç noktaya gönderilir/)
  assert.match(translate('agent.examCaptureNoWrite', 'en'), /Only approval saves it/)
  assert.match(translate('agent.examCaptureNoWrite', 'tr'), /yalnızca onayın kaydeder/)
  assert.equal(translate('agent.examCaptureSave', 'tr'), 'Bu önizlemeyi onayla ve kaydet')
})

test('Study Agent sectioned-exam capture describes consent, explicit roster, six-section limit, host profile, and approval', () => {
  for (const language of ['en', 'tr']) {
    assert.ok(translate('agent.workflowSectionedExam', language))
    assert.ok(translate('agent.sectionedExamHint', language).includes(language === 'en' ? '6' : '6'))
    assert.ok(translate('agent.sectionedExamConsent', language).includes(language === 'en' ? 'profile' : 'profili'))
    assert.ok(translate('agent.sectionedExamLocalConsent', language).includes('{{endpoint}}'))
    assert.ok(translate('agent.sectionedExamNoWrite', language).includes(language === 'en' ? 'Hamartia' : 'Hamartia'))
  }
})

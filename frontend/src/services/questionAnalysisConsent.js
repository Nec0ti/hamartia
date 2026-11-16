const AUTH_CATEGORIES = new Set(['blank', 'placeholder', 'configured_secret'])
const HOST_CLASSES = new Set(['local', 'remote'])
const SCHEMES = new Set(['http', 'https'])

export async function prepareQuestionAnalysisConsent(questionsApi, questionId) {
  const preview = await questionsApi.analysisPreview(questionId)
  if (
    !preview || typeof preview.consent_id !== 'string' || !preview.consent_id ||
    !HOST_CLASSES.has(preview.endpoint_class) || !SCHEMES.has(preview.scheme) ||
    typeof preview.endpoint_authority !== 'string' || !preview.endpoint_authority ||
    typeof preview.model !== 'string' ||
    !AUTH_CATEGORIES.has(preview.auth_setting_category) ||
    !AUTH_CATEGORIES.has(preview.auth_value_category) ||
    typeof preview.payload?.analysis_instructions_included !== 'boolean' ||
    typeof preview.payload?.ocr_text_included !== 'boolean' ||
    typeof preview.payload?.ocr_text_has_content !== 'boolean' ||
    typeof preview.payload?.image_filename_included !== 'boolean' ||
    typeof preview.payload?.saved_image_included !== 'boolean'
  ) {
    throw new Error('The local API returned an incomplete question-analysis consent preview.')
  }
  return Object.freeze({ ...preview, payload: Object.freeze({ ...preview.payload }) })
}

export async function sendApprovedQuestionAnalysis(questionsApi, questionId, preview, approved) {
  if (!approved) {
    if (preview?.consent_id && questionsApi.cancelAnalysisPreview) {
      try {
        await questionsApi.cancelAnalysisPreview(questionId, preview.consent_id)
      } catch {
        // The one-use token still expires locally; cancellation never contacts the provider.
      }
    }
    return null
  }
  if (!preview?.consent_id) throw new Error('Question analysis requires an active consent preview.')
  return questionsApi.analyze(questionId, preview.consent_id)
}

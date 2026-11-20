import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckCircle2, FileImage, FileText, Pencil, Save, Sparkles, Trash2, Upload, X } from 'lucide-react'
import api, { API_BASE, handleApiError } from '../services/api'
import Modal from '../components/Modal.jsx'
import { prepareQuestionAnalysisConsent, sendApprovedQuestionAnalysis } from '../services/questionAnalysisConsent.js'
import { useI18n } from '../i18n.jsx'
import { examTypeDisplay } from '../utils/examSections.js'
import { fmtDate } from '../utils/formatters.js'

const TAGS = ['[Knowledge Gap]', '[Distractor Trap]', '[Reading Slip]', '[Time Panic]']
const EMPTY_CURRICULUM_REFERENCE = {
  framework: '', source: '', version: '', grade_year: '', unit_theme: '',
  learning_outcome: '', process_component: '', source_url: '',
}

export default function QuestionsTab({ initialExam = null }) {
  const { t, locale } = useI18n()
  const [questions, setQuestions] = useState([])
  const [subject, setSubject] = useState(initialExam?.subject || '')
  const [topic, setTopic] = useState('')
  const [questionNumber, setQuestionNumber] = useState('')
  const [solveOrder, setSolveOrder] = useState('')
  const [timeSpentSeconds, setTimeSpentSeconds] = useState('')
  const [ocrText, setOcrText] = useState('')
  const [curriculumReference, setCurriculumReference] = useState({ ...EMPTY_CURRICULUM_REFERENCE })
  const [search, setSearch] = useState('')
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(null)
  const [analysisConsent, setAnalysisConsent] = useState(null)
  const fileInput = useRef(null)

  const load = useCallback(async () => {
    try {
      setQuestions(await api.questions.list())
      setError('')
    } catch (e) {
      setError(handleApiError(e, t).detail)
    }
  }, [t])

  useEffect(() => { load() }, [load])
  useEffect(() => { if (initialExam) setSubject(initialExam.subject) }, [initialExam])

  const upload = async (event) => {
    event.preventDefault()
    if (!file && !ocrText.trim()) return setError(t('questions.requireTextOrImage'))
    if (utf8ByteLength(ocrText) > 64 * 1024) return setError(t('error.analysisPayloadTooLarge'))
    setBusy(true)
    setError('')
    try {
      await api.questions.upload(file, ocrText, subject, topic, {
        examId: initialExam?.id,
        questionNumber,
        solveOrder,
        timeSpentSeconds,
      }, curriculumReference)
      setFile(null)
      setTopic('')
      setOcrText('')
      setCurriculumReference({ ...EMPTY_CURRICULUM_REFERENCE })
      setQuestionNumber('')
      setSolveOrder('')
      setTimeSpentSeconds('')
      if (fileInput.current) fileInput.current.value = ''
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    } finally {
      setBusy(false)
    }
  }

  const tag = async (question, hamartiaTag) => {
    try {
      await api.questions.tag(question.id, hamartiaTag)
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    }
  }

  const analyze = async (question) => {
    setBusy(true)
    setError('')
    try {
      const preview = await prepareQuestionAnalysisConsent(api.questions, question.id)
      setAnalysisConsent({ questionId: question.id, preview })
    } catch (e) {
      setError(handleApiError(e, t).detail)
    } finally {
      setBusy(false)
    }
  }

  const dismissAnalysisConsent = () => {
    if (analysisConsent) {
      void sendApprovedQuestionAnalysis(api.questions, analysisConsent.questionId, analysisConsent.preview, false)
    }
    setAnalysisConsent(null)
  }

  const approveAnalysisConsent = async () => {
    if (!analysisConsent || busy) return
    const pending = analysisConsent
    // Close and consume the UI's consent before starting; a failure requires a fresh preview.
    setAnalysisConsent(null)
    setBusy(true)
    setError('')
    try {
      await sendApprovedQuestionAnalysis(api.questions, pending.questionId, pending.preview, true)
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    } finally {
      setBusy(false)
    }
  }

  const review = async (question, reviewed) => {
    try {
      await api.questions.review(question.id, reviewed)
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    }
  }

  const edit = async (event) => {
    event.preventDefault()
    if (utf8ByteLength(editing.ocr_text) > 64 * 1024) return setError(t('error.analysisPayloadTooLarge'))
    try {
      const { id, ...payload } = editing
      await api.questions.update(id, payload)
      setEditing(null)
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    }
  }

  const remove = async (question) => {
    if (!window.confirm(t('questions.confirmDelete', { subject: question.subject || t('questions.thisQuestion') }))) return
    try {
      await api.questions.remove(question.id)
      if (editing?.id === question.id) setEditing(null)
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    }
  }

  const searchTerm = search.trim().toLocaleLowerCase(locale)
  const visibleQuestions = questions.filter((question) => {
    if (!searchTerm) return true
    const reference = question.curriculum_reference || EMPTY_CURRICULUM_REFERENCE
    return [
      question.subject, question.topic, question.ocr_text, reference.framework,
      reference.source, reference.version, reference.grade_year, reference.unit_theme,
      reference.learning_outcome, reference.process_component, reference.source_url,
    ].some((value) => String(value || '').toLocaleLowerCase(locale).includes(searchTerm))
  })

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-canvas-text">{t('questions.title')}</h1>
        <p className="mt-1 text-sm text-canvas-muted">{t('questions.intro')}</p>
      </header>

      <form onSubmit={upload} className="grid gap-4 rounded-xl border border-canvas-line bg-canvas-panel p-4 sm:grid-cols-2">
        {initialExam && <div className="rounded-lg border border-canvas-line bg-canvas-base p-3 text-sm text-canvas-muted sm:col-span-2">
          {t('questions.linkedExam', { date: fmtDate(initialExam.date, locale), subject: initialExam.subject, type: examTypeDisplay(initialExam, t) })}
          <p className="mt-1 text-xs">{t('questions.sectionCount', { count: initialExam.correct + initialExam.incorrect + initialExam.blank })}</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <label>{t('questions.questionNumber')}<input type="number" min="1" max={initialExam.correct + initialExam.incorrect + initialExam.blank} value={questionNumber} onChange={(e) => setQuestionNumber(e.target.value)} className={inputClass} /></label>
            <label>{t('questions.solveOrder')}<input type="number" min="1" max={initialExam.correct + initialExam.incorrect + initialExam.blank} value={solveOrder} onChange={(e) => setSolveOrder(e.target.value)} className={inputClass} /></label>
            <label>{t('questions.secondsSpent')}<input type="number" min="1" value={timeSpentSeconds} onChange={(e) => setTimeSpentSeconds(e.target.value)} className={inputClass} /></label>
          </div>
        </div>}
        <label className="text-sm text-canvas-muted">
          {t('common.subject')}
          <input required value={subject} onChange={(e) => setSubject(e.target.value)} className={inputClass} placeholder={t('questions.exampleMath')} />
        </label>
        <label className="text-sm text-canvas-muted">
          {t('common.topic')}
          <input value={topic} onChange={(e) => setTopic(e.target.value)} className={inputClass} placeholder={t('questions.exampleFunctions')} />
        </label>
        <label className="text-sm text-canvas-muted sm:col-span-2">
          {t('questions.imageLabel')}
          <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} className="mt-1 block w-full text-sm text-canvas-muted file:mr-3 file:rounded-lg file:border-0 file:bg-canvas-raise file:px-3 file:py-2 file:text-canvas-text" />
        </label>
        <label className="text-sm text-canvas-muted sm:col-span-2">
          {t('questions.textLabel')}
          <textarea maxLength={65536} value={ocrText} onChange={(e) => setOcrText(e.target.value)} rows={3} className={inputClass} placeholder={t('questions.textPlaceholder')} />
          <span className="mt-1 block text-xs">{t('questions.textByteLimit')}</span>
        </label>
        <CurriculumReferenceFields value={curriculumReference} onChange={setCurriculumReference} t={t} />
        <div className="flex items-center justify-between gap-3 sm:col-span-2">
          <span className="truncate text-xs text-canvas-muted">{file?.name || t('questions.noImageSelected')}</span>
          <button disabled={busy} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">
            <Upload size={16} /> {busy ? t('common.saving') : t('questions.saveQuestion')}
          </button>
        </div>
      </form>

      {error && <p role="alert" className="rounded-lg border border-canvas-line/50 bg-canvas-panel p-3 text-sm text-canvas-text">{error}</p>}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-canvas-text">{t('questions.savedQuestions')}</h2>
          <span className="text-sm text-canvas-muted">{t('questions.questionCount', { count: new Intl.NumberFormat(locale).format(questions.length) })}</span>
        </div>
        <input type="search" aria-label={t('questions.search')} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('questions.search')} className={inputClass} />
        {questions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-canvas-line p-8 text-center text-sm text-canvas-muted">{t('questions.empty')}</div>
        ) : visibleQuestions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-canvas-line p-8 text-center text-sm text-canvas-muted">{t('questions.noSearchResults')}</div>
        ) : visibleQuestions.slice().reverse().map((question) => (
          <article key={question.id} data-question-id={question.id} className="grid gap-4 rounded-xl border border-canvas-line bg-canvas-panel p-4 sm:grid-cols-[160px_1fr]">
            {question.image_path ? (
              <a href={`${API_BASE}/questions/${question.id}/image`} target="_blank" rel="noreferrer" className="flex min-h-32 items-center justify-center overflow-hidden rounded-lg bg-canvas-base" aria-label={t('questions.openImage')}>
                <img src={`${API_BASE}/questions/${question.id}/image`} alt={t('questions.imageAlt', { subject: question.subject || t('common.unlabelled'), topic: question.topic ? ` · ${question.topic}` : '' })} className="max-h-56 w-full object-contain" />
              </a>
            ) : (
              <div role="img" aria-label={t('questions.textQuestionWithoutImage')} className="flex min-h-32 flex-col items-center justify-center gap-2 rounded-lg bg-canvas-base text-sm text-canvas-muted"><FileText size={22} />{t('questions.textQuestion')}</div>
            )}
            <div className="min-w-0 space-y-3">
              {editing?.id === question.id ? (
                <form onSubmit={edit} className="grid gap-3 sm:grid-cols-2">
                  <fieldset disabled={busy} className="contents">
                  <label className="text-xs text-canvas-muted">{t('common.subject')}<input aria-label={t('questions.editSubject')} value={editing.subject} onChange={(e) => setEditing({ ...editing, subject: e.target.value })} className={inputClass} /></label>
                  <label className="text-xs text-canvas-muted">{t('common.topic')}<input aria-label={t('questions.editTopic')} value={editing.topic} onChange={(e) => setEditing({ ...editing, topic: e.target.value })} className={inputClass} /></label>
                  <label className="text-xs text-canvas-muted sm:col-span-2">{t('questions.questionText')}<textarea maxLength={65536} aria-label={t('questions.editQuestionText')} value={editing.ocr_text} onChange={(e) => setEditing({ ...editing, ocr_text: e.target.value })} rows={3} className={inputClass} /><span className="mt-1 block">{t('questions.textByteLimit')}</span></label>
                  <CurriculumReferenceFields value={editing.curriculum_reference || { ...EMPTY_CURRICULUM_REFERENCE }} onChange={(reference) => setEditing({ ...editing, curriculum_reference: reference })} t={t} />
                  <div className="flex gap-2 sm:col-span-2">
                    <button className="inline-flex items-center gap-1 rounded-lg bg-canvas-accent px-3 py-2 text-sm text-canvas-base"><Save size={14} /> {t('common.save')}</button>
                    <button type="button" onClick={() => setEditing(null)} className="inline-flex items-center gap-1 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-muted"><X size={14} /> {t('common.cancel')}</button>
                  </div>
                  </fieldset>
                </form>
              ) : (
                <>
                  <div>
                    <p className="font-semibold text-canvas-text">{question.subject || t('common.subjectNotSpecified')}{question.topic ? ` · ${question.topic}` : ''}</p>
                {question.exam_id && <p className="mt-1 text-xs text-canvas-muted">{t('questions.examQuestionMeta', { number: question.question_number ?? '—', order: question.solve_order ?? '—', time: question.time_spent_seconds ? t('common.seconds', { count: new Intl.NumberFormat(locale).format(question.time_spent_seconds) }) : t('questions.noTimeRecorded') })}</p>}
                    <p className="text-xs text-canvas-muted">{question.created_at ? fmtDate(question.created_at.slice(0, 10), locale) : ''}</p>
                  </div>
                  {question.ocr_text && <p className="whitespace-pre-wrap text-sm text-canvas-muted">{question.ocr_text}</p>}
                </>
              )}
              <div className="flex flex-wrap items-center gap-2">
                <label className="sr-only" htmlFor={`tag-${question.id}`}>{t('questions.errorType')}</label>
                <select id={`tag-${question.id}`} disabled={busy} value={question.hamartia_tag} onChange={(e) => tag(question, e.target.value)} className="rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text disabled:opacity-50">
                  {TAGS.map((item) => <option key={item} value={item}>{tagLabel(item, t)}</option>)}
                </select>
                {!question.analysis && <button type="button" disabled={busy} onClick={() => analyze(question)} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text disabled:opacity-50"><Sparkles size={14} /> {t('questions.reviewWithAI')}</button>}
                {!question.reviewed_at && <button type="button" disabled={busy} onClick={() => review(question, true)} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text hover:bg-canvas-raise disabled:opacity-50"><CheckCircle2 size={14} /> {t('questions.markReviewed')}</button>}
                {question.reviewed_at && <><span className="inline-flex items-center gap-1 rounded-lg bg-canvas-raise px-3 py-2 text-xs text-canvas-text"><CheckCircle2 size={14} /> {t('questions.reviewedOn', { date: fmtDate(question.reviewed_at.slice(0, 10), locale) })}</span><button type="button" disabled={busy} onClick={() => review(question, false)} className="rounded-lg px-2 py-2 text-xs text-canvas-muted underline hover:text-canvas-text disabled:opacity-50">{t('questions.undoReview')}</button></>}
                {hasCurriculumReference(question.curriculum_reference) && <CurriculumReferenceSummary value={question.curriculum_reference} t={t} />}
                <button type="button" disabled={busy} onClick={() => setEditing({ id: question.id, subject: question.subject, topic: question.topic, ocr_text: question.ocr_text, curriculum_reference: { ...EMPTY_CURRICULUM_REFERENCE, ...(question.curriculum_reference || {}) } })} aria-label={t('questions.editQuestion', { subject: question.subject || question.id })} className="inline-flex items-center gap-1 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text"><Pencil size={14} /> {t('common.edit')}</button>
                <button type="button" disabled={busy} onClick={() => remove(question)} aria-label={t('questions.deleteQuestion', { subject: question.subject || question.id })} className="inline-flex items-center gap-1 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text"><Trash2 size={14} /> {t('common.delete')}</button>
              </div>
              {question.analysis && (
                <div className="rounded-lg bg-canvas-base p-3 text-sm">
                  <p className="font-medium text-canvas-text">{question.analysis.verdict.root_cause}</p>
                  <p className="mt-1 text-canvas-muted">{question.analysis.verdict.action_advice}</p>
                  {question.analysis.counselors?.executor && <p className="mt-2 text-canvas-text">{question.analysis.counselors.executor}</p>}
                </div>
              )}
            </div>
          </article>
        ))}
      </section>
      <div className="flex items-center gap-2 text-xs text-canvas-muted"><FileImage size={14} /> {t('questions.imagesStoredLocally')}</div>
      <Modal
        open={Boolean(analysisConsent)}
        onClose={dismissAnalysisConsent}
        title={t('questions.aiConsentTitle')}
        descriptionId="question-analysis-consent-description"
        footer={analysisConsent && <>
          <button type="button" autoFocus onClick={dismissAnalysisConsent} className="rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-muted">{t('questions.aiConsentCancel')}</button>
          <button type="button" onClick={approveAnalysisConsent} className="rounded-lg bg-canvas-accent px-3 py-2 text-sm font-semibold text-canvas-base">{t('questions.aiConsentApprove')}</button>
        </>}
      >
        {analysisConsent && <div id="question-analysis-consent-description" className="space-y-4 text-sm text-canvas-muted">
          <p>{t('questions.aiConsentEndpointNote')}</p>
          <p className="rounded-lg bg-canvas-base p-3 font-medium text-canvas-text">{t('questions.aiConsentEndpoint', {
            hostClass: t(analysisConsent.preview.endpoint_class === 'local' ? 'questions.aiConsentHostLocal' : 'questions.aiConsentHostRemote'),
            authority: analysisConsent.preview.endpoint_authority,
            scheme: analysisConsent.preview.scheme.toUpperCase(),
            model: analysisConsent.preview.model,
          })}</p>
          <div>
            <p className="font-medium text-canvas-text">{t('questions.aiConsentIncludes')}</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {analysisConsent.preview.payload.analysis_instructions_included && <li>{t('questions.aiConsentInstructions')}</li>}
              {analysisConsent.preview.payload.ocr_text_included && <li>{analysisConsent.preview.payload.ocr_text_has_content ? t('questions.aiConsentQuestionText') : t('questions.aiConsentQuestionTextEmpty')}</li>}
              {analysisConsent.preview.payload.image_filename_included && <li>{t('questions.aiConsentImageFilename')}</li>}
              <li>{analysisConsent.preview.payload.saved_image_included ? t('questions.aiConsentSavedImage') : t('questions.aiConsentNoSavedImage')}</li>
            </ul>
          </div>
          <div className="rounded-lg border border-canvas-line p-3">
            <p>{t(analysisConsent.preview.auth_setting_category === 'blank' ? 'questions.aiConsentAuthSettingBlank' : analysisConsent.preview.auth_setting_category === 'placeholder' ? 'questions.aiConsentAuthSettingPlaceholder' : 'questions.aiConsentAuthSettingConfigured')}</p>
            <p className="mt-1">{t(analysisConsent.preview.auth_value_category === 'placeholder' ? 'questions.aiConsentAuthValuePlaceholder' : 'questions.aiConsentAuthValueConfigured')}</p>
          </div>
        </div>}
      </Modal>
    </div>
  )
}

const inputClass = 'mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text outline-none focus:border-canvas-accent'

function utf8ByteLength(value) {
  return new TextEncoder().encode(value || '').length
}

function hasCurriculumReference(reference = {}) {
  return Object.values(reference).some((value) => String(value || '').trim())
}

function CurriculumReferenceFields({ value, onChange, t }) {
  const update = (field, nextValue) => onChange({ ...EMPTY_CURRICULUM_REFERENCE, ...value, [field]: nextValue })
  return <details className="rounded-lg border border-canvas-line p-3 sm:col-span-2">
    <summary className="cursor-pointer text-sm font-medium text-canvas-text">{t('questions.curriculumReference')}</summary>
    <p className="mt-2 text-xs leading-relaxed text-canvas-muted">{t('questions.curriculumReferenceHelp')}</p>
    <p className="mt-1 text-xs text-canvas-muted">{t('questions.curriculumSubjectHelp')}</p>
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <ReferenceInput field="framework" label="questions.curriculumFramework" value={value.framework} onChange={update} t={t} maxLength={100} />
      <ReferenceInput field="source" label="questions.curriculumSource" value={value.source} onChange={update} t={t} maxLength={160} />
      <ReferenceInput field="version" label="questions.curriculumVersion" value={value.version} onChange={update} t={t} maxLength={80} />
      <ReferenceInput field="grade_year" label="questions.curriculumGradeYear" value={value.grade_year} onChange={update} t={t} maxLength={80} />
      <ReferenceInput field="unit_theme" label="questions.curriculumUnitTheme" value={value.unit_theme} onChange={update} t={t} maxLength={160} />
      <ReferenceInput field="process_component" label="questions.curriculumProcess" value={value.process_component} onChange={update} t={t} maxLength={200} />
      <label className="text-xs text-canvas-muted sm:col-span-2">{t('questions.curriculumOutcome')}<textarea value={value.learning_outcome} onChange={(event) => update('learning_outcome', event.target.value)} maxLength={500} rows={2} className={inputClass} /></label>
      <label className="text-xs text-canvas-muted sm:col-span-2">{t('questions.curriculumSourceUrl')}<input type="url" value={value.source_url} onChange={(event) => update('source_url', event.target.value)} maxLength={2048} className={inputClass} placeholder="https://" /></label>
    </div>
  </details>
}

function ReferenceInput({ field, label, value, onChange, t, maxLength }) {
  return <label className="text-xs text-canvas-muted">{t(label)}<input value={value || ''} onChange={(event) => onChange(field, event.target.value)} maxLength={maxLength} className={inputClass} /></label>
}

function CurriculumReferenceSummary({ value, t }) {
  const details = [value.framework, value.source, value.version, value.grade_year, value.unit_theme, value.process_component].filter(Boolean)
  return <div className="w-full rounded-lg border border-canvas-line bg-canvas-base p-3 text-xs text-canvas-muted">
    <p className="font-medium text-canvas-text">{t('questions.referenceUserProvided')}</p>
    {details.length > 0 && <p className="mt-1">{details.join(' · ')}</p>}
    {value.learning_outcome && <p className="mt-1">{value.learning_outcome}</p>}
    {value.source_url && <a href={value.source_url} target="_blank" rel="noreferrer noopener" className="mt-1 inline-block break-all text-canvas-text underline">{value.source_url}</a>}
  </div>
}

function tagLabel(tag, t) {
  return ({
    '[Knowledge Gap]': t('questions.tag.knowledgeGap'),
    '[Distractor Trap]': t('questions.tag.distractorTrap'),
    '[Reading Slip]': t('questions.tag.readingSlip'),
    '[Time Panic]': t('questions.tag.timePanic'),
  })[tag] || tag
}

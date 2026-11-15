import { useCallback, useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import api, { handleApiError } from '../services/api'
import { useI18n } from '../i18n.jsx'
import { fmtDate, localDateToday } from '../utils/formatters.js'

const emptyForm = () => ({ date: localDateToday(), subject: '', topic: '', activity: '', observation: '', reference_url: '' })
const inputClass = 'mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text outline-none focus:border-canvas-accent'
const buttonClass = 'rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text hover:bg-canvas-raise disabled:opacity-50'

export default function LearningEvidence({ topics = [] }) {
  const { t, locale } = useI18n()
  const [records, setRecords] = useState([])
  const [draft, setDraft] = useState(emptyForm)
  const [editingId, setEditingId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState('')

  const suggestions = topics.filter((item) => item.subject?.trim() && item.topic?.trim())
    .filter((item, index, all) => all.findIndex((other) => other.subject === item.subject && other.topic === item.topic) === index)
  const suggestionKey = (subject, topic) => JSON.stringify([subject, topic])
  const availableSuggestions = draft.subject && !suggestions.some((item) => item.subject === draft.subject && item.topic === draft.topic)
    ? [{ subject: draft.subject, topic: draft.topic }, ...suggestions]
    : suggestions

  const load = useCallback(async () => {
    try {
      setRecords(await api.learningEvidence.list())
      setError('')
    } catch (e) {
      setError(handleApiError(e, t).detail)
    }
  }, [t])

  useEffect(() => { load() }, [load])

  const set = (key, value) => setDraft((current) => ({ ...current, [key]: value }))

  const chooseSuggestion = (value) => {
    const chosen = suggestions.find((item) => suggestionKey(item.subject, item.topic) === value)
    if (chosen) setDraft((current) => ({ ...current, subject: chosen.subject, topic: chosen.topic }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setFeedback('')
    try {
      if (editingId) await api.learningEvidence.update(editingId, draft)
      else await api.learningEvidence.create(draft)
      setDraft(emptyForm())
      setEditingId('')
      setFeedback(t(editingId ? 'study.evidenceUpdated' : 'study.evidenceSaved'))
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    } finally {
      setSaving(false)
    }
  }

  const edit = (record) => {
    setEditingId(record.id)
    setDraft({
      date: record.date, subject: record.subject, topic: record.topic,
      activity: record.activity, observation: record.observation, reference_url: record.reference_url,
    })
    setError('')
    setFeedback('')
  }

  const cancelEdit = () => { setDraft(emptyForm()); setEditingId('') }

  const remove = async (record) => {
    if (!window.confirm(t('study.confirmDeleteEvidence', { activity: record.activity }))) return
    setError('')
    try {
      await api.learningEvidence.remove(record.id)
      if (editingId === record.id) cancelEdit()
      await load()
      setFeedback(t('study.evidenceDeleted'))
    } catch (e) {
      setError(handleApiError(e, t).detail)
    }
  }

  const orderedRecords = [...records].sort((a, b) => b.date.localeCompare(a.date) || b.created_at.localeCompare(a.created_at))

  return <section aria-label={t('study.evidenceTitle')} className="space-y-3 rounded-xl border border-canvas-line bg-canvas-panel p-4">
    <div>
      <h2 className="font-semibold text-canvas-text">{t('study.evidenceTitle')}</h2>
      <p className="mt-1 text-sm text-canvas-muted">{t('study.evidenceIntro')}</p>
    </div>
    {feedback && <p role="status" aria-live="polite" className="rounded-lg border border-canvas-line bg-canvas-base p-3 text-sm text-canvas-text">{feedback}</p>}
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
      <label className="text-xs text-canvas-muted sm:col-span-2">{t('study.evidenceSuggestion')}
        <select required value={draft.subject ? suggestionKey(draft.subject, draft.topic) : ''} onChange={(event) => chooseSuggestion(event.target.value)} className={inputClass}>
          <option value="" disabled>{suggestions.length ? t('study.chooseEvidenceSuggestion') : t('study.noEvidenceSuggestions')}</option>
          {availableSuggestions.map((item) => <option key={suggestionKey(item.subject, item.topic)} value={suggestionKey(item.subject, item.topic)}>{item.subject} · {item.topic}</option>)}
        </select>
      </label>
      <label className="text-xs text-canvas-muted">{t('common.date')}<input required type="date" value={draft.date} onChange={(event) => set('date', event.target.value)} className={inputClass} /></label>
      <label className="text-xs text-canvas-muted">{t('study.completedActivity')}<input required maxLength={500} value={draft.activity} onChange={(event) => set('activity', event.target.value)} className={inputClass} /></label>
      <label className="text-xs text-canvas-muted sm:col-span-2">{t('study.observation')}<textarea required maxLength={3000} rows={3} value={draft.observation} onChange={(event) => set('observation', event.target.value)} className={inputClass} /></label>
      <label className="text-xs text-canvas-muted sm:col-span-2">{t('study.evidenceReference')}<input type="url" maxLength={2048} value={draft.reference_url} onChange={(event) => set('reference_url', event.target.value)} placeholder="https://…" className={inputClass} /></label>
      <div className="flex justify-end gap-2 sm:col-span-2">
        {editingId && <button type="button" onClick={cancelEdit} className={buttonClass}>{t('common.cancel')}</button>}
        <button type="submit" disabled={saving || !suggestions.length && !editingId} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50"><Plus size={15} />{saving ? t('common.saving') : t(editingId ? 'study.saveChanges' : 'study.saveEvidence')}</button>
      </div>
    </form>
    {error && <p role="alert" className="rounded-lg border border-canvas-line/50 bg-canvas-base p-3 text-sm text-canvas-text">{error}</p>}
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-canvas-text">{t('study.savedEvidence')}</h3>
      {!orderedRecords.length ? <p className="rounded-lg border border-dashed border-canvas-line p-3 text-sm text-canvas-muted">{t('study.noEvidence')}</p> : orderedRecords.map((record) => (
        <article key={record.id} className="rounded-lg bg-canvas-base p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-xs text-canvas-muted">{fmtDate(record.date, locale)} · {record.subject} / {record.topic}</p>
              <h4 className="mt-1 font-medium text-canvas-text">{record.activity}</h4>
            </div>
            <span className="inline-flex gap-1">
              <button type="button" aria-label={t('study.editEvidence', { activity: record.activity })} onClick={() => edit(record)} className="rounded p-1 text-canvas-muted hover:text-canvas-text"><Pencil size={14} /></button>
              <button type="button" aria-label={t('study.deleteEvidence', { activity: record.activity })} onClick={() => remove(record)} className="rounded p-1 text-canvas-muted hover:text-canvas-text"><Trash2 size={14} /></button>
            </span>
          </div>
          <p className="mt-2 whitespace-pre-wrap text-sm text-canvas-muted">{record.observation}</p>
          {record.reference_url && <a href={record.reference_url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block break-all text-xs text-canvas-text underline">{t('study.evidenceReferenceLink')}</a>}
        </article>
      ))}
    </div>
  </section>
}

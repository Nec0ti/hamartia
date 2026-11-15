import { useCallback, useEffect, useRef, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import api, { handleApiError } from '../services/api'
import { useI18n } from '../i18n.jsx'
import { fmtDate, fmtPercent, localDateToday } from '../utils/formatters.js'

const emptyForm = () => ({
  date: localDateToday(), subject: '', topic: '', correct: 0, incorrect: 0, blank: 0,
  duration_minutes: 0, duration_seconds: 0,
})
const fields = [
  ['correct', 'common.correct'], ['incorrect', 'common.incorrect'], ['blank', 'common.blank'],
  ['duration_minutes', 'common.minutes'], ['duration_seconds', 'common.secondsLabel'],
]
const activeKey = 'hamartia.active-practice-session'

function readActiveSession() {
  try {
    const item = JSON.parse(localStorage.getItem(activeKey))
    if (item && typeof item.subject === 'string' && typeof item.topic === 'string'
      && ['correct', 'incorrect', 'blank', 'elapsed_seconds'].every((key) => Number.isInteger(item[key]) && item[key] >= 0)
      && (item.running_since === null || Number.isFinite(item.running_since))) return item
  } catch {}
  return null
}

function elapsedSeconds(session, now = Date.now()) {
  return session.elapsed_seconds + (session.running_since ? Math.floor((now - session.running_since) / 1000) : 0)
}

function timeLabel(seconds) {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}

export default function PracticeSessions({ startTopic, onStartTopicConsumed }) {
  const { t, locale } = useI18n()
  const [sessions, setSessions] = useState([])
  const [summaries, setSummaries] = useState([])
  const [draft, setDraft] = useState(emptyForm)
  const [editingId, setEditingId] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [active, setActive] = useState(readActiveSession)
  const [now, setNow] = useState(Date.now())
  const activeRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const [records, insights] = await Promise.all([api.practice.list(), api.practice.insights()])
      setSessions(records)
      setSummaries(insights)
      setError('')
    } catch (e) {
      setError(handleApiError(e, t).detail)
    }
  }, [t])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (active) localStorage.setItem(activeKey, JSON.stringify(active))
    else localStorage.removeItem(activeKey)
  }, [active])

  useEffect(() => {
    if (!active?.running_since) return undefined
    const interval = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(interval)
  }, [active?.running_since])

  useEffect(() => {
    if (!startTopic) return
    setError('')
    if (active) {
      setError(t('study.finishOrCancelActive'))
    } else {
      setActive({
        date: localDateToday(), subject: startTopic.subject, topic: startTopic.topic,
        correct: 0, incorrect: 0, blank: 0, elapsed_seconds: 0, running_since: Date.now(),
      })
    }
    onStartTopicConsumed?.()
  }, [startTopic])

  useEffect(() => {
    if (startTopic) activeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [startTopic])

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (editingId) await api.practice.update(editingId, draft)
      else await api.practice.create(draft)
      setDraft(emptyForm())
      setEditingId('')
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    } finally {
      setSaving(false)
    }
  }

  const edit = (session) => {
    setEditingId(session.id)
    setDraft({
      date: session.date, subject: session.subject, topic: session.topic,
      correct: session.correct, incorrect: session.incorrect, blank: session.blank,
      duration_minutes: session.duration_minutes, duration_seconds: session.duration_seconds,
    })
  }

  const remove = async (session) => {
    if (!window.confirm(t('study.confirmDeleteSession', { date: fmtDate(session.date, locale), subject: session.subject, topic: session.topic }))) return
    try {
      await api.practice.remove(session.id)
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    }
  }

  const set = (key, value) => setDraft((current) => ({ ...current, [key]: value }))

  const adjust = (key, delta) => setActive((current) => current && ({ ...current, [key]: Math.max(0, current[key] + delta) }))

  const finishFocus = async () => {
    if (active.correct + active.incorrect + active.blank === 0) {
      setError(t('study.markAtLeastOneResult'))
      return
    }
    setSaving(true)
    setError('')
    const seconds = elapsedSeconds(active)
    try {
      await api.practice.create({
        date: active.date, subject: active.subject, topic: active.topic,
        correct: active.correct, incorrect: active.incorrect, blank: active.blank,
        duration_minutes: Math.floor(seconds / 60), duration_seconds: seconds % 60,
      })
      setActive(null)
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    } finally {
      setSaving(false)
    }
  }

  const pauseFocus = () => setActive((current) => ({
    ...current, elapsed_seconds: elapsedSeconds(current), running_since: null,
  }))

  const resumeFocus = () => setActive((current) => ({ ...current, running_since: Date.now() }))

  const cancelFocus = () => {
    if (window.confirm(t('study.confirmCancelSession'))) setActive(null)
  }

  const currentSeconds = active ? elapsedSeconds(active, now) : 0

  return (
    <section aria-label={t('study.practiceSets')} className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-canvas-text">{t('study.practiceSets')}</h2>
        <p className="text-sm text-canvas-muted">{t('study.practiceSetsIntro')}</p>
      </div>
      {active && <section ref={activeRef} aria-label={t('study.focusedSession')} className="space-y-3 rounded-xl border border-canvas-accent/50 bg-canvas-panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h3 className="font-semibold text-canvas-text">{t('study.focusedPractice', { subject: active.subject, topic: active.topic })}</h3><p className="text-sm text-canvas-muted">{t('study.focusedPracticeIntro')}</p></div>
          <output aria-label={t('study.elapsedTime')} className="font-mono text-2xl font-semibold tabular-nums text-canvas-text">{timeLabel(currentSeconds)}</output>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          {[["correct", t('common.correct')], ["incorrect", t('common.incorrect')], ["blank", t('common.blank')]].map(([key, label]) => <div key={key} className="flex items-center justify-between rounded-lg bg-canvas-base px-3 py-2"><span className="text-sm text-canvas-text">{label}: {new Intl.NumberFormat(locale).format(active[key])}</span><span className="flex gap-2"><button type="button" aria-label={t('study.decreaseResult', { label })} onClick={() => adjust(key, -1)} className={secondaryButton}>−</button><button type="button" aria-label={t('study.increaseResult', { label })} onClick={() => adjust(key, 1)} className={secondaryButton}>+</button></span></div>)}
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          {active.running_since ? <button type="button" onClick={pauseFocus} className={secondaryButton}>{t('study.pause')}</button> : <button type="button" onClick={resumeFocus} className={secondaryButton}>{t('study.resume')}</button>}
          <button type="button" onClick={cancelFocus} className={secondaryButton}>{t('study.cancelSession')}</button>
          <button type="button" disabled={saving} onClick={finishFocus} className="rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{saving ? t('common.saving') : t('study.finishAndSave')}</button>
        </div>
      </section>}
      <form onSubmit={submit} className="grid gap-3 rounded-xl border border-canvas-line bg-canvas-panel p-4 sm:grid-cols-4">
        <label className="text-xs text-canvas-muted">{t('common.date')}<input required type="date" value={draft.date} onChange={(e) => set('date', e.target.value)} className={inputClass} /></label>
        <label className="text-xs text-canvas-muted">{t('common.subject')}<input required value={draft.subject} onChange={(e) => set('subject', e.target.value)} placeholder={t('study.exampleMath')} className={inputClass} /></label>
        <label className="text-xs text-canvas-muted sm:col-span-2">{t('common.topic')}<input required value={draft.topic} onChange={(e) => set('topic', e.target.value)} placeholder={t('study.exampleFunctions')} className={inputClass} /></label>
        {fields.map(([key, label]) => <label key={key} className="text-xs text-canvas-muted">{t(label)}<input required type="number" min="0" max={key === 'duration_seconds' ? 59 : undefined} value={draft[key]} onChange={(e) => set(key, Number(e.target.value))} className={inputClass} /></label>)}
        <div className="flex items-end justify-end gap-2 sm:col-span-4">
          {editingId && <button type="button" onClick={() => { setDraft(emptyForm()); setEditingId('') }} className={secondaryButton}>{t('common.cancel')}</button>}
          <button disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50"><Plus size={15} />{saving ? t('common.saving') : editingId ? t('study.saveChanges') : t('study.saveSet')}</button>
        </div>
      </form>
      {error && <p role="alert" className="rounded-lg border border-canvas-line/50 bg-canvas-panel p-3 text-sm text-canvas-text">{error}</p>}
      {summaries.length === 0 ? <p className="rounded-lg border border-dashed border-canvas-line p-4 text-sm text-canvas-muted">{t('study.noPracticeSets')}</p> : summaries.map((group) => {
        const chartData = group.trend.map((item) => ({ ...item, accuracy_percent: item.accuracy == null ? null : item.accuracy * 100 }))
        const recent = group.trend.slice(-6).reverse()
        const older = group.trend.slice(0, -6).reverse()
        return <article key={`${group.subject}-${group.topic}`} className="rounded-xl border border-canvas-line bg-canvas-panel p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div><h3 className="font-semibold text-canvas-text">{group.subject} · {group.topic}</h3><p className="text-xs text-canvas-muted">{t('study.savedSetCount', { count: new Intl.NumberFormat(locale).format(group.session_count) })}</p></div>
            <div className="text-right text-sm text-canvas-text">{formatNumber(group.net, locale)} {t('study.totalNet')}<p className="text-xs text-canvas-muted">{group.accuracy == null ? t('study.noAnsweredQuestions') : t('study.answeredAccuracy', { accuracy: fmtPercent(group.accuracy * 100, locale) })}</p></div>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <PracticeTrendChart subject={group.subject} topic={group.topic} data={chartData} metric="net" t={t} locale={locale} />
            <PracticeTrendChart subject={group.subject} topic={group.topic} data={chartData} metric="accuracy_percent" t={t} locale={locale} />
          </div>
          <SessionRows items={recent} sessions={sessions} topic={group.topic} locale={locale} t={t} onEdit={edit} onRemove={remove} />
          {older.length > 0 && <details className="mt-2 rounded-lg border border-canvas-line px-3 py-2">
            <summary className="cursor-pointer text-sm text-canvas-muted">{t('study.olderSessions', { count: new Intl.NumberFormat(locale).format(older.length) })}</summary>
            <SessionRows items={older} sessions={sessions} topic={group.topic} locale={locale} t={t} onEdit={edit} onRemove={remove} />
          </details>}
        </article>
      })}
    </section>
  )
}

function PracticeTrendChart({ subject, topic, data, metric, t, locale }) {
  const accuracy = metric === 'accuracy_percent'
  const label = accuracy ? t('study.accuracy') : t('study.net')
  return <section aria-label={t('study.metricChart', { subject, topic, metric: label.toLowerCase() })} className="min-w-0 rounded-lg bg-canvas-base p-2">
    <h4 className="mb-1 text-xs font-medium text-canvas-muted">{t('study.metricPerSet', { metric: label.toLowerCase() })}</h4>
    <div role="img" aria-label={t('study.metricChange', { subject, topic, metric: label.toLowerCase() })} className="h-36 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: '#a1a1aa', fontSize: 10 }} tickFormatter={(date) => date.slice(5)} />
          <YAxis tick={{ fill: '#a1a1aa', fontSize: 10 }} width={32} domain={accuracy ? [0, 100] : ['auto', 'auto']} />
          <Tooltip
            contentStyle={{ background: '#18181b', border: '1px solid #27272a', borderRadius: '8px', color: '#d4d4d8', fontSize: '12px' }}
            labelFormatter={(date) => fmtDate(date, locale)}
            formatter={(value) => [value == null ? t('study.noAccuracy') : accuracy ? `${fmtPercent(value, locale)}%` : formatNumber(value, locale, 2), label]}
          />
          <Line type="monotone" dataKey={metric} name={label} stroke="#d4d4d8" strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
    {accuracy && data.every((item) => item.accuracy_percent == null) && <p className="text-center text-xs text-canvas-muted">{t('study.noAnsweredQuestions')}</p>}
  </section>
}

function SessionRows({ items, sessions, topic, locale, t, onEdit, onRemove }) {
  return <ol className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
    {items.map((item) => {
      const session = sessions.find((record) => record.id === item.id)
      return <li key={item.id} className="flex items-center justify-between rounded-lg bg-canvas-base px-3 py-2 text-xs">
        <span className="text-canvas-muted">{fmtDate(item.date, locale)} · {t('study.net')} {formatNumber(item.net, locale)}</span>
        {session && <span className="inline-flex gap-1">
          <button type="button" aria-label={t('study.editSet', { date: fmtDate(item.date, locale), topic })} onClick={() => onEdit(session)} className="rounded p-1 text-canvas-muted hover:text-canvas-text"><Pencil size={13} /></button>
          <button type="button" aria-label={t('study.deleteSet', { date: fmtDate(item.date, locale), topic })} onClick={() => onRemove(session)} className="rounded p-1 text-canvas-muted hover:text-canvas-text"><Trash2 size={13} /></button>
        </span>}
      </li>
    })}
  </ol>
}

const inputClass = 'mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text outline-none focus:border-canvas-accent'
const secondaryButton = 'rounded-lg border border-canvas-line px-4 py-2 text-sm text-canvas-muted'

function formatNumber(value, locale, maximumFractionDigits = 2) {
  return new Intl.NumberFormat(locale, { maximumFractionDigits }).format(value)
}

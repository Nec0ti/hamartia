import { useCallback, useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import api, { handleApiError } from '../services/api'

const dateToday = () => {
  const date = new Date()
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
const emptyForm = () => ({
  date: dateToday(), subject: '', topic: '', correct: 0, incorrect: 0, blank: 0,
  duration_minutes: 0, duration_seconds: 0,
})
const fields = [
  ['correct', 'Doğru'], ['incorrect', 'Yanlış'], ['blank', 'Boş'],
  ['duration_minutes', 'Dakika'], ['duration_seconds', 'Saniye'],
]

export default function PracticeSessions() {
  const [sessions, setSessions] = useState([])
  const [summaries, setSummaries] = useState([])
  const [draft, setDraft] = useState(emptyForm)
  const [editingId, setEditingId] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const [records, insights] = await Promise.all([api.practice.list(), api.practice.insights()])
      setSessions(records)
      setSummaries(insights)
      setError('')
    } catch (e) {
      setError(handleApiError(e).detail)
    }
  }, [])

  useEffect(() => { load() }, [load])

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
      setError(handleApiError(e).detail)
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
    if (!window.confirm(`${session.date} · ${session.subject} / ${session.topic} seti silinsin mi?`)) return
    try {
      await api.practice.remove(session.id)
      await load()
    } catch (e) {
      setError(handleApiError(e).detail)
    }
  }

  const set = (key, value) => setDraft((current) => ({ ...current, [key]: value }))

  return (
    <section aria-label="Konu çalışma setleri" className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-canvas-text">Konu çalışma setleri</h2>
        <p className="text-sm text-canvas-muted">Bitirdiğin setin sonucunu kaydet. Doğruluk yalnızca cevapladığın sorulardan hesaplanır; boşlar paydaya girmez.</p>
      </div>
      <form onSubmit={submit} className="grid gap-3 rounded-xl border border-canvas-line bg-canvas-panel p-4 sm:grid-cols-4">
        <label className="text-xs text-canvas-muted">Tarih<input required type="date" value={draft.date} onChange={(e) => set('date', e.target.value)} className={inputClass} /></label>
        <label className="text-xs text-canvas-muted">Ders<input required value={draft.subject} onChange={(e) => set('subject', e.target.value)} placeholder="Matematik" className={inputClass} /></label>
        <label className="text-xs text-canvas-muted sm:col-span-2">Konu<input required value={draft.topic} onChange={(e) => set('topic', e.target.value)} placeholder="Fonksiyonlar" className={inputClass} /></label>
        {fields.map(([key, label]) => <label key={key} className="text-xs text-canvas-muted">{label}<input required type="number" min="0" max={key === 'duration_seconds' ? 59 : undefined} value={draft[key]} onChange={(e) => set(key, Number(e.target.value))} className={inputClass} /></label>)}
        <div className="flex items-end justify-end gap-2 sm:col-span-4">
          {editingId && <button type="button" onClick={() => { setDraft(emptyForm()); setEditingId('') }} className={secondaryButton}>Vazgeç</button>}
          <button disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><Plus size={15} />{saving ? 'Kaydediliyor…' : editingId ? 'Değişiklikleri kaydet' : 'Seti kaydet'}</button>
        </div>
      </form>
      {error && <p role="alert" className="rounded-lg border border-accent/50 bg-canvas-panel p-3 text-sm text-accent">{error}</p>}
      {summaries.length === 0 ? <p className="rounded-lg border border-dashed border-canvas-line p-4 text-sm text-canvas-muted">Henüz kayıtlı çalışma seti yok.</p> : summaries.map((group) => (
        <article key={`${group.subject}-${group.topic}`} className="rounded-xl border border-canvas-line bg-canvas-panel p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div><h3 className="font-semibold text-canvas-text">{group.subject} · {group.topic}</h3><p className="text-xs text-canvas-muted">{group.session_count} kayıtlı set</p></div>
            <div className="text-right text-sm text-canvas-text">{group.net.toFixed(2)} toplam net<p className="text-xs text-canvas-muted">{group.accuracy == null ? 'Cevaplanan soru yok' : `${(group.accuracy * 100).toFixed(1)}% cevaplanan doğruluğu`}</p></div>
          </div>
          <ol className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {group.trend.slice(-6).reverse().map((item) => {
              const session = sessions.find((record) => record.id === item.id)
              return <li key={item.id} className="flex items-center justify-between rounded-lg bg-canvas-base px-3 py-2 text-xs">
                <span className="text-canvas-muted">{item.date} · net {item.net.toFixed(2)}</span>
                <span className="inline-flex gap-1">
                  <button type="button" aria-label={`Seti düzenle ${item.date} ${group.topic}`} onClick={() => edit(session)} className="rounded p-1 text-canvas-muted hover:text-canvas-text"><Pencil size={13} /></button>
                  <button type="button" aria-label={`Seti sil ${item.date} ${group.topic}`} onClick={() => remove(session)} className="rounded p-1 text-canvas-muted hover:text-accent"><Trash2 size={13} /></button>
                </span>
              </li>
            })}
          </ol>
        </article>
      ))}
    </section>
  )
}

const inputClass = 'mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text outline-none focus:border-canvas-accent'
const secondaryButton = 'rounded-lg border border-canvas-line px-4 py-2 text-sm text-canvas-muted'

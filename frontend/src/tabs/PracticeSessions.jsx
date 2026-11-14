import { useCallback, useEffect, useRef, useState } from 'react'
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
      setError(handleApiError(e).detail)
    }
  }, [])

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
      setError('Bitirmeden önce açık oturumu tamamla veya iptal et.')
    } else {
      setActive({
        date: dateToday(), subject: startTopic.subject, topic: startTopic.topic,
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

  const adjust = (key, delta) => setActive((current) => current && ({ ...current, [key]: Math.max(0, current[key] + delta) }))

  const finishFocus = async () => {
    if (active.correct + active.incorrect + active.blank === 0) {
      setError('Bitirmek için en az bir sorunun sonucunu işaretle.')
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
      setError(handleApiError(e).detail)
    } finally {
      setSaving(false)
    }
  }

  const pauseFocus = () => setActive((current) => ({
    ...current, elapsed_seconds: elapsedSeconds(current), running_since: null,
  }))

  const resumeFocus = () => setActive((current) => ({ ...current, running_since: Date.now() }))

  const cancelFocus = () => {
    if (window.confirm('Açık oturum iptal edilsin mi? Sayılan sonuçlar silinir.')) setActive(null)
  }

  const currentSeconds = active ? elapsedSeconds(active, now) : 0

  return (
    <section aria-label="Konu çalışma setleri" className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-canvas-text">Konu çalışma setleri</h2>
        <p className="text-sm text-canvas-muted">Bitirdiğin setin sonucunu kaydet. Doğruluk yalnızca cevapladığın sorulardan hesaplanır; boşlar paydaya girmez. Açık oturum taslağı bu tarayıcıda saklanır.</p>
      </div>
      {active && <section ref={activeRef} aria-label="Odaklı çalışma oturumu" className="space-y-3 rounded-xl border border-canvas-accent/50 bg-canvas-panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h3 className="font-semibold text-canvas-text">Odaklı çalışma · {active.subject} / {active.topic}</h3><p className="text-sm text-canvas-muted">Kendi materyalinden çöz; her sorudan sonra sonucunu işaretle. Bitince sonuç kaydedilir ve yedeğe dahil olur.</p></div>
          <output aria-label="Geçen süre" className="font-mono text-2xl font-semibold tabular-nums text-canvas-text">{timeLabel(currentSeconds)}</output>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          {[["correct", "Doğru"], ["incorrect", "Yanlış"], ["blank", "Boş"]].map(([key, label]) => <div key={key} className="flex items-center justify-between rounded-lg bg-canvas-base px-3 py-2"><span className="text-sm text-canvas-text">{label}: {active[key]}</span><span className="flex gap-2"><button type="button" aria-label={`${label} azalt`} onClick={() => adjust(key, -1)} className={secondaryButton}>−</button><button type="button" aria-label={`${label} artır`} onClick={() => adjust(key, 1)} className={secondaryButton}>+</button></span></div>)}
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          {active.running_since ? <button type="button" onClick={pauseFocus} className={secondaryButton}>Duraklat</button> : <button type="button" onClick={resumeFocus} className={secondaryButton}>Sürdür</button>}
          <button type="button" onClick={cancelFocus} className={secondaryButton}>Oturumu iptal et</button>
          <button type="button" disabled={saving} onClick={finishFocus} className="rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Kaydediliyor…' : 'Bitir ve kaydet'}</button>
        </div>
      </section>}
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

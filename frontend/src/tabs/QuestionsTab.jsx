import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckCircle2, FileImage, Sparkles, Upload } from 'lucide-react'
import api, { API_BASE, handleApiError } from '../services/api'

const TAGS = ['[Knowledge Gap]', '[Distractor Trap]', '[Reading Slip]', '[Time Panic]']

export default function QuestionsTab({ initialSubject = '' }) {
  const [questions, setQuestions] = useState([])
  const [subject, setSubject] = useState(initialSubject)
  const [topic, setTopic] = useState('')
  const [ocrText, setOcrText] = useState('')
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const fileInput = useRef(null)

  const load = useCallback(async () => {
    try {
      setQuestions(await api.questions.list())
      setError('')
    } catch (e) {
      setError(handleApiError(e).detail)
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { if (initialSubject) setSubject(initialSubject) }, [initialSubject])

  const upload = async (event) => {
    event.preventDefault()
    if (!file) return setError('Önce soru görseli seç.')
    setBusy(true)
    setError('')
    try {
      await api.questions.upload(file, ocrText, subject, topic)
      setFile(null)
      setTopic('')
      setOcrText('')
      if (fileInput.current) fileInput.current.value = ''
      await load()
    } catch (e) {
      setError(handleApiError(e).detail)
    } finally {
      setBusy(false)
    }
  }

  const tag = async (question, hamartiaTag) => {
    try {
      await api.questions.tag(question.id, hamartiaTag)
      await load()
    } catch (e) {
      setError(handleApiError(e).detail)
    }
  }

  const analyze = async (question) => {
    setBusy(true)
    setError('')
    try {
      await api.questions.analyze(question.id)
      await load()
    } catch (e) {
      setError(handleApiError(e).detail)
    } finally {
      setBusy(false)
    }
  }

  const review = async (question, reviewed) => {
    try {
      await api.questions.review(question.id, reviewed)
      await load()
    } catch (e) {
      setError(handleApiError(e).detail)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-canvas-text">Yanlış soru defteri</h1>
        <p className="mt-1 text-sm text-canvas-muted">Soruyu kaydet, ders ve konusunu işaretle; tekrar eden hata türlerini görünür tut.</p>
      </header>

      <form onSubmit={upload} className="grid gap-4 rounded-xl border border-canvas-line bg-canvas-panel p-4 sm:grid-cols-2">
        <label className="text-sm text-canvas-muted">
          Ders
          <input required value={subject} onChange={(e) => setSubject(e.target.value)} className={inputClass} placeholder="Örn. Matematik" />
        </label>
        <label className="text-sm text-canvas-muted">
          Konu
          <input value={topic} onChange={(e) => setTopic(e.target.value)} className={inputClass} placeholder="Örn. Fonksiyonlar" />
        </label>
        <label className="text-sm text-canvas-muted sm:col-span-2">
          Soru görseli (PNG, JPEG veya WebP; en fazla 10 MB)
          <input ref={fileInput} required type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} className="mt-1 block w-full text-sm text-canvas-muted file:mr-3 file:rounded-lg file:border-0 file:bg-canvas-raise file:px-3 file:py-2 file:text-canvas-text" />
        </label>
        <label className="text-sm text-canvas-muted sm:col-span-2">
          Soru metni veya kendi notun
          <textarea value={ocrText} onChange={(e) => setOcrText(e.target.value)} rows={3} className={inputClass} placeholder="İstersen soruyu ve nerede takıldığını yaz." />
        </label>
        <div className="flex items-center justify-between gap-3 sm:col-span-2">
          <span className="truncate text-xs text-canvas-muted">{file?.name || 'Henüz görsel seçilmedi'}</span>
          <button disabled={busy} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            <Upload size={16} /> {busy ? 'Kaydediliyor…' : 'Soruyu kaydet'}
          </button>
        </div>
      </form>

      {error && <p role="alert" className="rounded-lg border border-accent/50 bg-canvas-panel p-3 text-sm text-accent">{error}</p>}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-canvas-text">Kayıtlı sorular</h2>
          <span className="text-sm text-canvas-muted">{questions.length} soru</span>
        </div>
        {questions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-canvas-line p-8 text-center text-sm text-canvas-muted">İlk yanlış sorunu ekleyince tekrar listende görünecek.</div>
        ) : questions.slice().reverse().map((question) => (
          <article key={question.id} className="grid gap-4 rounded-xl border border-canvas-line bg-canvas-panel p-4 sm:grid-cols-[160px_1fr]">
            <a href={`${API_BASE}/questions/${question.id}/image`} target="_blank" rel="noreferrer" className="flex min-h-32 items-center justify-center overflow-hidden rounded-lg bg-canvas-base" aria-label="Soru görselini aç">
              <img src={`${API_BASE}/questions/${question.id}/image`} alt={`${question.subject || 'Derssiz'} ${question.topic || 'konusuz'} soru`} className="max-h-56 w-full object-contain" />
            </a>
            <div className="min-w-0 space-y-3">
              <div>
                <p className="font-semibold text-canvas-text">{question.subject || 'Ders belirtilmedi'}{question.topic ? ` · ${question.topic}` : ''}</p>
                <p className="text-xs text-canvas-muted">{question.created_at?.slice(0, 10)}</p>
              </div>
              {question.ocr_text && <p className="whitespace-pre-wrap text-sm text-canvas-muted">{question.ocr_text}</p>}
              <div className="flex flex-wrap items-center gap-2">
                <label className="sr-only" htmlFor={`tag-${question.id}`}>Hata türü</label>
                <select id={`tag-${question.id}`} value={question.hamartia_tag} onChange={(e) => tag(question, e.target.value)} className="rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text">
                  {TAGS.map((item) => <option key={item} value={item}>{tagLabel(item)}</option>)}
                </select>
                {!question.analysis && <button type="button" disabled={busy} onClick={() => analyze(question)} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text disabled:opacity-50"><Sparkles size={14} /> Yerel AI ile incele</button>}
                {!question.reviewed_at && <button type="button" onClick={() => review(question, true)} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text hover:bg-canvas-raise"><CheckCircle2 size={14} /> Tekrar ettim</button>}
                {question.reviewed_at && <><span className="inline-flex items-center gap-1 rounded-lg bg-emerald-400/10 px-3 py-2 text-xs text-emerald-300"><CheckCircle2 size={14} /> Tekrarlandı · {question.reviewed_at.slice(0, 10)}</span><button type="button" onClick={() => review(question, false)} className="rounded-lg px-2 py-2 text-xs text-canvas-muted underline hover:text-canvas-text">Tekrarı geri al</button></>}
              </div>
              {question.analysis && (
                <div className="rounded-lg bg-canvas-base p-3 text-sm">
                  <p className="font-medium text-canvas-text">{question.analysis.verdict.root_cause}</p>
                  <p className="mt-1 text-canvas-muted">{question.analysis.verdict.action_advice}</p>
                  {question.analysis.counselors?.executor && <p className="mt-2 text-canvas-cyan">{question.analysis.counselors.executor}</p>}
                </div>
              )}
            </div>
          </article>
        ))}
      </section>
      <div className="flex items-center gap-2 text-xs text-canvas-muted"><FileImage size={14} /> Görseller bu bilgisayardaki Hamartia veri klasöründe tutulur.</div>
    </div>
  )
}

const inputClass = 'mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text outline-none focus:border-canvas-accent'

function tagLabel(tag) {
  return ({
    '[Knowledge Gap]': 'Konu eksiği',
    '[Distractor Trap]': 'Çeldirici tuzağı',
    '[Reading Slip]': 'Soruyu yanlış okuma',
    '[Time Panic]': 'Zaman baskısı',
  })[tag] || tag
}

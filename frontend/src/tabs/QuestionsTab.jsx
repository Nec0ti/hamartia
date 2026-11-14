import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckCircle2, FileImage, FileText, Pencil, Save, Sparkles, Trash2, Upload, X } from 'lucide-react'
import api, { API_BASE, handleApiError } from '../services/api'

const TAGS = ['[Knowledge Gap]', '[Distractor Trap]', '[Reading Slip]', '[Time Panic]']

export default function QuestionsTab({ initialExam = null }) {
  const [questions, setQuestions] = useState([])
  const [subject, setSubject] = useState(initialExam?.subject || '')
  const [topic, setTopic] = useState('')
  const [questionNumber, setQuestionNumber] = useState('')
  const [solveOrder, setSolveOrder] = useState('')
  const [timeSpentSeconds, setTimeSpentSeconds] = useState('')
  const [ocrText, setOcrText] = useState('')
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(null)
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
  useEffect(() => { if (initialExam) setSubject(initialExam.subject) }, [initialExam])

  const upload = async (event) => {
    event.preventDefault()
    if (!file && !ocrText.trim()) return setError('Görsel seç veya soru metnini yaz.')
    setBusy(true)
    setError('')
    try {
      await api.questions.upload(file, ocrText, subject, topic, {
        examId: initialExam?.id,
        questionNumber,
        solveOrder,
        timeSpentSeconds,
      })
      setFile(null)
      setTopic('')
      setOcrText('')
      setQuestionNumber('')
      setSolveOrder('')
      setTimeSpentSeconds('')
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

  const edit = async (event) => {
    event.preventDefault()
    try {
      const { id, ...payload } = editing
      await api.questions.update(id, payload)
      setEditing(null)
      await load()
    } catch (e) {
      setError(handleApiError(e).detail)
    }
  }

  const remove = async (question) => {
    if (!window.confirm(`${question.subject || 'Bu'} soru kaydı silinsin mi?`)) return
    try {
      await api.questions.remove(question.id)
      if (editing?.id === question.id) setEditing(null)
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
        {initialExam && <div className="rounded-lg border border-canvas-line bg-canvas-base p-3 text-sm text-canvas-muted sm:col-span-2">
          Bağlı deneme: {initialExam.date} · {initialExam.subject} ({initialExam.exam_type?.toUpperCase() || 'BRANŞ'})
          <p className="mt-1 text-xs">Bu bölümde {initialExam.correct + initialExam.incorrect + initialExam.blank} soru var.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <label>Sınavdaki soru no<input type="number" min="1" max={initialExam.correct + initialExam.incorrect + initialExam.blank} value={questionNumber} onChange={(e) => setQuestionNumber(e.target.value)} className={inputClass} /></label>
            <label>Çözüm sırası<input type="number" min="1" max={initialExam.correct + initialExam.incorrect + initialExam.blank} value={solveOrder} onChange={(e) => setSolveOrder(e.target.value)} className={inputClass} /></label>
            <label>Soruda harcanan saniye<input type="number" min="1" value={timeSpentSeconds} onChange={(e) => setTimeSpentSeconds(e.target.value)} className={inputClass} /></label>
          </div>
        </div>}
        <label className="text-sm text-canvas-muted">
          Ders
          <input required value={subject} onChange={(e) => setSubject(e.target.value)} className={inputClass} placeholder="Örn. Matematik" />
        </label>
        <label className="text-sm text-canvas-muted">
          Konu
          <input value={topic} onChange={(e) => setTopic(e.target.value)} className={inputClass} placeholder="Örn. Fonksiyonlar" />
        </label>
        <label className="text-sm text-canvas-muted sm:col-span-2">
          Soru görseli (isteğe bağlı; PNG, JPEG veya WebP, en fazla 10 MB)
          <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} className="mt-1 block w-full text-sm text-canvas-muted file:mr-3 file:rounded-lg file:border-0 file:bg-canvas-raise file:px-3 file:py-2 file:text-canvas-text" />
        </label>
        <label className="text-sm text-canvas-muted sm:col-span-2">
          Soru metni veya kendi notun (görsel yoksa zorunlu)
          <textarea value={ocrText} onChange={(e) => setOcrText(e.target.value)} rows={3} className={inputClass} placeholder="Soruyu ve nerede takıldığını yaz." />
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
          <article key={question.id} data-question-id={question.id} className="grid gap-4 rounded-xl border border-canvas-line bg-canvas-panel p-4 sm:grid-cols-[160px_1fr]">
            {question.image_path ? (
              <a href={`${API_BASE}/questions/${question.id}/image`} target="_blank" rel="noreferrer" className="flex min-h-32 items-center justify-center overflow-hidden rounded-lg bg-canvas-base" aria-label="Soru görselini aç">
                <img src={`${API_BASE}/questions/${question.id}/image`} alt={`${question.subject || 'Derssiz'} ${question.topic || 'konusuz'} soru`} className="max-h-56 w-full object-contain" />
              </a>
            ) : (
              <div role="img" aria-label="Görseli olmayan metin sorusu" className="flex min-h-32 flex-col items-center justify-center gap-2 rounded-lg bg-canvas-base text-sm text-canvas-muted"><FileText size={22} />Metin sorusu</div>
            )}
            <div className="min-w-0 space-y-3">
              {editing?.id === question.id ? (
                <form onSubmit={edit} className="grid gap-3 sm:grid-cols-2">
                  <label className="text-xs text-canvas-muted">Ders<input aria-label="Düzenle · Ders" value={editing.subject} onChange={(e) => setEditing({ ...editing, subject: e.target.value })} className={inputClass} /></label>
                  <label className="text-xs text-canvas-muted">Konu<input aria-label="Düzenle · Konu" value={editing.topic} onChange={(e) => setEditing({ ...editing, topic: e.target.value })} className={inputClass} /></label>
                  <label className="text-xs text-canvas-muted sm:col-span-2">Soru metni<textarea aria-label="Düzenle · Soru metni" value={editing.ocr_text} onChange={(e) => setEditing({ ...editing, ocr_text: e.target.value })} rows={3} className={inputClass} /></label>
                  <div className="flex gap-2 sm:col-span-2">
                    <button className="inline-flex items-center gap-1 rounded-lg bg-canvas-accent px-3 py-2 text-sm text-white"><Save size={14} /> Kaydet</button>
                    <button type="button" onClick={() => setEditing(null)} className="inline-flex items-center gap-1 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-muted"><X size={14} /> Vazgeç</button>
                  </div>
                </form>
              ) : (
                <>
                  <div>
                    <p className="font-semibold text-canvas-text">{question.subject || 'Ders belirtilmedi'}{question.topic ? ` · ${question.topic}` : ''}</p>
                {question.exam_id && <p className="mt-1 text-xs text-canvas-muted">Deneme sorusu {question.question_number ?? '—'} · çözüm sırası {question.solve_order ?? '—'} · {question.time_spent_seconds ? `${question.time_spent_seconds} sn` : 'süre yok'}</p>}
                    <p className="text-xs text-canvas-muted">{question.created_at?.slice(0, 10)}</p>
                  </div>
                  {question.ocr_text && <p className="whitespace-pre-wrap text-sm text-canvas-muted">{question.ocr_text}</p>}
                </>
              )}
              <div className="flex flex-wrap items-center gap-2">
                <label className="sr-only" htmlFor={`tag-${question.id}`}>Hata türü</label>
                <select id={`tag-${question.id}`} value={question.hamartia_tag} onChange={(e) => tag(question, e.target.value)} className="rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text">
                  {TAGS.map((item) => <option key={item} value={item}>{tagLabel(item)}</option>)}
                </select>
                {!question.analysis && <button type="button" disabled={busy} onClick={() => analyze(question)} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text disabled:opacity-50"><Sparkles size={14} /> Yerel AI ile incele</button>}
                {!question.reviewed_at && <button type="button" onClick={() => review(question, true)} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text hover:bg-canvas-raise"><CheckCircle2 size={14} /> Tekrar ettim</button>}
                {question.reviewed_at && <><span className="inline-flex items-center gap-1 rounded-lg bg-emerald-400/10 px-3 py-2 text-xs text-emerald-300"><CheckCircle2 size={14} /> Tekrarlandı · {question.reviewed_at.slice(0, 10)}</span><button type="button" onClick={() => review(question, false)} className="rounded-lg px-2 py-2 text-xs text-canvas-muted underline hover:text-canvas-text">Tekrarı geri al</button></>}
                <button type="button" onClick={() => setEditing({ id: question.id, subject: question.subject, topic: question.topic, ocr_text: question.ocr_text })} aria-label={`Soruyu düzenle ${question.subject || question.id}`} className="inline-flex items-center gap-1 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text"><Pencil size={14} /> Düzenle</button>
                <button type="button" onClick={() => remove(question)} aria-label={`Soruyu sil ${question.subject || question.id}`} className="inline-flex items-center gap-1 rounded-lg border border-canvas-line px-3 py-2 text-sm text-accent"><Trash2 size={14} /> Sil</button>
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

import { useCallback, useEffect, useState } from 'react'
import { BookOpenCheck, CheckCircle2, Clock3, FileText, Tags, ThumbsDown, ThumbsUp } from 'lucide-react'
import api, { API_BASE, handleApiError } from '../services/api'

const TAG_LABELS = {
  '[Knowledge Gap]': 'Konu eksiği',
  '[Distractor Trap]': 'Çeldirici tuzağı',
  '[Reading Slip]': 'Soruyu yanlış okuma',
  '[Time Panic]': 'Zaman baskısı',
}

export default function StudyPlanTab() {
  const [plan, setPlan] = useState(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState('')

  const load = useCallback(() => api.questions.insights().then(setPlan).catch((e) => setError(handleApiError(e).detail)), [])

  useEffect(() => { load() }, [load])

  const recordAttempt = async (question, correct) => {
    setBusyId(question.id)
    setError('')
    try {
      await api.questions.attempt(question.id, correct)
      await load()
    } catch (e) {
      setError(handleApiError(e).detail)
    } finally {
      setBusyId('')
    }
  }

  if (error) return <p role="alert" className="rounded-lg border border-accent/50 bg-canvas-panel p-3 text-sm text-accent">{error}</p>
  if (!plan) return <p className="py-20 text-center text-sm text-canvas-muted">Çalışma verileri yükleniyor…</p>

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-canvas-text">Çalışma önceliklerin</h1>
        <p className="mt-1 text-sm text-canvas-muted">Soruyu yeniden çöz, sonucunu kaydet; yanlışlar ertesi gün, doğru çözümler artan aralıklarla tekrar listene gelir. Plan yerel ve deterministiktir; AI kullanmaz.</p>
      </header>

      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="Kayıtlı yanlış" value={plan.total_questions} icon={<BookOpenCheck size={18} />} />
        <Stat label="Tekrar bekleyen" value={plan.pending_questions} icon={<CheckCircle2 size={18} />} />
        <Stat label="Sonraki güne planlı" value={plan.scheduled_questions} icon={<Clock3 size={18} />} />
        <Stat label="Ders veya konusu eksik" value={plan.unclassified_questions} icon={<Tags size={18} />} />
      </div>

      <section aria-label="Bugünkü çalışma" className="rounded-xl border border-canvas-line bg-canvas-panel p-4">
        <h2 className="font-semibold text-canvas-text">Bugün</h2>
        <p className="mt-1 text-sm text-canvas-muted"><strong className="text-canvas-text">{plan.today_questions}</strong> farklı soru denedin · {plan.today_correct} doğru, {plan.today_incorrect} yanlış yanıt</p>
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-canvas-text">Şimdi çöz</h2>
          <p className="text-sm text-canvas-muted">Bir soru çözdükten sonra sonucunu işaretle. Yanlış seçersen soru yarın, doğru seçersen aralıklı tekrar için geri gelir.</p>
        </div>
        {plan.reviews.length === 0 ? (
          <div className="rounded-xl border border-dashed border-canvas-line p-6 text-center text-sm text-canvas-muted">{plan.scheduled_questions ? `${plan.scheduled_questions} soru sonraki tekrar tarihinde açılacak.` : 'Şu an çözmen gereken soru yok. Yanlışlarım sekmesinden yeni bir soru kaydet.'}</div>
        ) : plan.reviews.slice(0, 6).map((question) => (
          <article key={question.id} className="grid gap-4 rounded-xl border border-canvas-line bg-canvas-panel p-4 sm:grid-cols-[200px_1fr]">
            {question.has_image ? (
              <img src={`${API_BASE}/questions/${question.id}/image`} alt={`${question.subject} · ${question.topic} sorusu`} className="max-h-56 w-full rounded-lg bg-canvas-base object-contain" />
            ) : (
              <div role="img" aria-label="Görseli olmayan metin sorusu" className="flex min-h-32 flex-col items-center justify-center gap-2 rounded-lg bg-canvas-base text-sm text-canvas-muted"><FileText size={22} />Metin sorusu</div>
            )}
            <div className="space-y-3">
              <div>
                <p className="text-xs text-canvas-muted">{question.subject} · {question.topic}</p>
                <h3 className="font-semibold text-canvas-text">{TAG_LABELS[question.hamartia_tag] || question.hamartia_tag}</h3>
              </div>
              {question.ocr_text && <p className="whitespace-pre-wrap text-sm text-canvas-muted">{question.ocr_text}</p>}
              <p className="text-xs text-canvas-muted">{question.last_correct === false ? 'Son denemede yanlış çözüldü.' : question.streak ? `Arka arkaya ${question.streak} doğru deneme.` : 'İlk tekrar.'}</p>
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busyId === question.id} onClick={() => recordAttempt(question, true)} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text hover:bg-canvas-raise disabled:opacity-50"><ThumbsUp size={15} /> Doğru çözdüm</button>
                <button type="button" disabled={busyId === question.id} onClick={() => recordAttempt(question, false)} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text hover:bg-canvas-raise disabled:opacity-50"><ThumbsDown size={15} /> Yanlış çözdüm</button>
              </div>
            </div>
          </article>
        ))}
      </section>

      {plan.scheduled_questions > 0 && <section className="rounded-xl border border-canvas-line bg-canvas-panel p-4 text-sm text-canvas-muted">{plan.scheduled_questions} soru aralıklı tekrar için ileride açılacak. Doğru çözdükçe aralıklar 1, 3, 7, 14 ve 30 güne kadar uzar.</section>}

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-canvas-text">Tekrar etmen gereken konular</h2>
          <p className="text-sm text-canvas-muted">Bir konuda daha çok yanlış kaydı varsa listede daha üstte görünür.</p>
        </div>
        {plan.topics.length === 0 ? (
          <div className="rounded-xl border border-dashed border-canvas-line p-8 text-center text-sm text-canvas-muted">{plan.total_questions ? 'Bekleyen yanlışın yok. Tekrar listeni tamamladın.' : 'Öncelik oluşturmak için önce Yanlışlarım sekmesinden soru kaydet.'}</div>
        ) : plan.topics.slice(0, 8).map((topic, index) => (
          <article key={`${topic.subject}-${topic.topic}`} className="rounded-xl border border-canvas-line bg-canvas-panel p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-canvas-raise text-sm font-semibold text-canvas-cyan">{index + 1}</span>
                <div>
                  <h3 className="font-semibold text-canvas-text">{topic.topic}</h3>
                  <p className="text-sm text-canvas-muted">{topic.subject}</p>
                </div>
              </div>
              <span className="rounded-full border border-canvas-line px-3 py-1 text-xs text-canvas-muted">{topic.pending_count} bekleyen yanlış</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(topic.tags).map(([tag, count]) => (
                <span key={tag} className="rounded-md bg-canvas-base px-2 py-1 text-xs text-canvas-muted">{TAG_LABELS[tag] || tag}: {count}</span>
              ))}
              {topic.last_seen && <span className="px-2 py-1 text-xs text-canvas-muted">Son kayıt: {topic.last_seen}</span>}
            </div>
          </article>
        ))}
      </section>
    </div>
  )
}

function Stat({ label, value, icon }) {
  return (
    <article className="flex items-center gap-3 rounded-xl border border-canvas-line bg-canvas-panel p-4">
      <div className="rounded-lg bg-canvas-raise p-2 text-canvas-cyan">{icon}</div>
      <div><p className="text-xs text-canvas-muted">{label}</p><p className="text-xl font-bold text-canvas-text">{value}</p></div>
    </article>
  )
}

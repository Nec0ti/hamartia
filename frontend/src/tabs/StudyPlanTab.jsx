import { useEffect, useState } from 'react'
import { BookOpenCheck, CheckCircle2, Tags } from 'lucide-react'
import api, { handleApiError } from '../services/api'

const TAG_LABELS = {
  '[Knowledge Gap]': 'Konu eksiği',
  '[Distractor Trap]': 'Çeldirici tuzağı',
  '[Reading Slip]': 'Soruyu yanlış okuma',
  '[Time Panic]': 'Zaman baskısı',
}

export default function StudyPlanTab() {
  const [plan, setPlan] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.questions.insights().then(setPlan).catch((e) => setError(handleApiError(e).detail))
  }, [])

  if (error) return <p role="alert" className="rounded-lg border border-accent/50 bg-canvas-panel p-3 text-sm text-accent">{error}</p>
  if (!plan) return <p className="py-20 text-center text-sm text-canvas-muted">Çalışma verileri yükleniyor…</p>

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-canvas-text">Çalışma önceliklerin</h1>
        <p className="mt-1 text-sm text-canvas-muted">Öncelikler, yanlış soru defterindeki tekrar sayılarına göre sıralanır. Bu görünüm yerel ve deterministiktir; AI kullanmaz.</p>
      </header>

      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Kayıtlı yanlış" value={plan.total_questions} icon={<BookOpenCheck size={18} />} />
        <Stat label="Tekrar bekleyen" value={plan.pending_questions} icon={<CheckCircle2 size={18} />} />
        <Stat label="Ders veya konusu eksik" value={plan.unclassified_questions} icon={<Tags size={18} />} />
      </div>

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

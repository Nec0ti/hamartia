import { useEffect, useState } from 'react'
import { Flame, Orbit, Sparkles } from 'lucide-react'
import api, { handleApiError } from '../services/api'
import { fmtInt, levelForXp, xpProgress, xpToNextLevel } from '../utils/formatters'

export default function CosmosTab() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.user.get(), api.questions.insights()])
      .then(([profile, plan]) => setData({ profile, plan }))
      .catch((e) => setError(handleApiError(e).detail))
  }, [])

  if (error) return <p role="alert" className="rounded-lg border border-accent/50 bg-canvas-panel p-3 text-sm text-accent">{error}</p>
  if (!data) return <p className="py-20 text-center text-sm text-canvas-muted">Cosmos verileri yükleniyor…</p>

  const { profile, plan } = data
  const xp = profile.total_xp ?? 0
  const level = profile.level ?? levelForXp(xp)
  const progress = xpProgress(xp, level)
  const nextLevelXp = xpToNextLevel(level)

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-canvas-text">Cosmos</h1>
        <p className="mt-1 text-sm text-canvas-muted">Deneme ilerlemen ve tekrar bekleyen konuların bu yerel haritayı oluşturur. Görünüm AI kullanmaz ve yeni kayıt üretmez.</p>
      </header>

      <section className="rounded-2xl border border-canvas-line bg-canvas-panel p-5 sm:p-7" aria-label="Seviye ilerlemesi">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full border border-canvas-cyan/40 bg-canvas-raise text-canvas-cyan"><Orbit size={23} /></div>
            <div><p className="text-xs uppercase tracking-wider text-canvas-muted">Gezgin seviyesi</p><p className="text-2xl font-bold text-canvas-text">Seviye {level}</p></div>
          </div>
          <div className="flex items-center gap-2 rounded-lg bg-canvas-raise px-3 py-2 text-sm text-canvas-text"><Sparkles size={16} className="text-canvas-cyan" />{fmtInt(xp)} XP</div>
        </div>
        <div className="mt-5">
          <div className="mb-2 flex justify-between text-xs text-canvas-muted"><span>Sonraki seviyeye ilerleme</span><span>{fmtInt(xp)} / {fmtInt(nextLevelXp)} XP</span></div>
          <div role="progressbar" aria-label="Sonraki seviyeye ilerleme" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)} className="h-2 overflow-hidden rounded-full bg-canvas-base"><div className="h-full rounded-full bg-canvas-cyan transition-all" style={{ width: `${progress * 100}%` }} /></div>
        </div>
        <div className="mt-5 flex items-center gap-2 text-sm text-canvas-muted"><Flame size={16} className="text-canvas-accent" />{profile.streak_days ?? 0} günlük çalışma serisi</div>
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-canvas-text">Tekrar yörüngeleri</h2>
          <p className="text-sm text-canvas-muted">Daha çok bekleyen yanlış içeren konular önce görünür.</p>
        </div>
        {plan.topics.length === 0 ? (
          <div className="rounded-xl border border-dashed border-canvas-line p-8 text-center text-sm text-canvas-muted">{plan.total_questions ? 'Bekleyen yanlışın yok. Yörüngelerin temiz.' : 'Haritaya konu eklemek için Yanlışlarım sekmesinden soru kaydet ve ders/konu bilgisini gir.'}</div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {plan.topics.slice(0, 9).map((topic, index) => (
              <article key={`${topic.subject}-${topic.topic}`} className="flex min-h-36 items-center gap-4 rounded-xl border border-canvas-line bg-canvas-panel p-4">
                <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border ${index === 0 ? 'border-canvas-cyan/60 bg-canvas-cyan/10 text-canvas-cyan' : 'border-canvas-line bg-canvas-raise text-canvas-muted'}`}><Orbit size={20} /></div>
                <div className="min-w-0"><p className="truncate text-xs text-canvas-muted">{topic.subject}</p><h3 className="truncate font-semibold text-canvas-text">{topic.topic}</h3><p className="mt-1 text-xs text-canvas-muted">{topic.pending_count} bekleyen yanlış</p></div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

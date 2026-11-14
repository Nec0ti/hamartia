import { useEffect, useState } from 'react'
import { Flame, Orbit, Sparkles } from 'lucide-react'
import api, { handleApiError } from '../services/api'
import { fmtInt, labelOr, levelForXp, localDateToday, xpProgress, xpToNextLevel } from '../utils/formatters'
import { useI18n } from '../i18n.jsx'

export default function CosmosTab() {
  const { t, locale } = useI18n()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.user.get(), api.questions.insights(localDateToday())])
      .then(([profile, plan]) => setData({ profile, plan }))
      .catch((e) => setError(handleApiError(e, t).key))
  }, [])

  if (error) return <p role="alert" className="rounded-lg border border-accent/50 bg-canvas-panel p-3 text-sm text-accent">{t(error)}</p>
  if (!data) return <p className="py-20 text-center text-sm text-canvas-muted">{t('cosmos.loading')}</p>

  const { profile, plan } = data
  const xp = profile.total_xp ?? 0
  const level = profile.level ?? levelForXp(xp)
  const progress = xpProgress(xp, level)
  const nextLevelXp = xpToNextLevel(level)

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-canvas-text">Cosmos</h1>
        <p className="mt-1 text-sm text-canvas-muted">{t('cosmos.intro')}</p>
      </header>

      <section className="rounded-2xl border border-canvas-line bg-canvas-panel p-5 sm:p-7" aria-label={t('cosmos.levelProgress')}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full border border-canvas-cyan/40 bg-canvas-raise text-canvas-cyan"><Orbit size={23} /></div>
            <div><p className="text-xs uppercase tracking-wider text-canvas-muted">{t('cosmos.explorerLevel')}</p><p className="text-2xl font-bold text-canvas-text">{t('cosmos.level', { level: new Intl.NumberFormat(locale).format(level) })}</p></div>
          </div>
          <div className="flex items-center gap-2 rounded-lg bg-canvas-raise px-3 py-2 text-sm text-canvas-text"><Sparkles size={16} className="text-canvas-cyan" />{fmtInt(xp, locale)} XP</div>
        </div>
        <div className="mt-5">
          <div className="mb-2 flex justify-between text-xs text-canvas-muted"><span>{t('cosmos.nextLevelProgress')}</span><span>{new Intl.NumberFormat(locale).format(xp)} / {new Intl.NumberFormat(locale).format(nextLevelXp)} XP</span></div>
          <div role="progressbar" aria-label={t('cosmos.nextLevelProgress')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)} className="h-2 overflow-hidden rounded-full bg-canvas-base"><div className="h-full rounded-full bg-canvas-cyan transition-all" style={{ width: `${progress * 100}%` }} /></div>
        </div>
        <div className="mt-5 flex items-center gap-2 text-sm text-canvas-muted"><Flame size={16} className="text-canvas-accent" />{t('cosmos.streak', { count: new Intl.NumberFormat(locale).format(profile.streak_days ?? 0) })}</div>
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-canvas-text">{t('cosmos.orbits')}</h2>
          <p className="text-sm text-canvas-muted">{t('cosmos.orbitsIntro')}</p>
        </div>
        {plan.topics.length === 0 ? (
          <div className="rounded-xl border border-dashed border-canvas-line p-8 text-center text-sm text-canvas-muted">{plan.total_questions ? t('cosmos.noPending') : t('cosmos.addTopic')}</div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {plan.topics.slice(0, 9).map((topic, index) => (
              <article key={`${topic.subject}-${topic.topic}`} className="flex min-h-36 items-center gap-4 rounded-xl border border-canvas-line bg-canvas-panel p-4">
                <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border ${index === 0 ? 'border-canvas-cyan/60 bg-canvas-cyan/10 text-canvas-cyan' : 'border-canvas-line bg-canvas-raise text-canvas-muted'}`}><Orbit size={20} /></div>
                <div className="min-w-0"><p className="truncate text-xs text-canvas-muted">{labelOr(topic.subject, t('common.subjectNotSpecified'))}</p><h3 className="truncate font-semibold text-canvas-text">{labelOr(topic.topic, t('common.topicNotSpecified'))}</h3><p className="mt-1 text-xs text-canvas-muted">{t('study.pendingWrongCount', { count: new Intl.NumberFormat(locale).format(topic.pending_count) })}</p></div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

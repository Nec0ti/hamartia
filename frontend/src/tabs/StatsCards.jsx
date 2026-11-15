import {
  GraduationCap,
  Target,
  Zap,
  Shield,
  Flame,
} from 'lucide-react'
import { fmtInt, fmtNet } from '../utils/formatters'
import { useI18n } from '../i18n.jsx'

const CARDS = [
  { label: 'dashboard.stat.examCount', value: (p, locale) => fmtInt(p.total, locale), icon: GraduationCap },
  { label: 'dashboard.stat.averageNet', value: (p, locale) => fmtNet(p.avgNet, locale), icon: Target },
  { label: 'dashboard.stat.totalXp', value: (p, locale) => fmtInt(p.totalXp, locale), icon: Zap },
  { label: 'dashboard.stat.level', value: (p, locale) => fmtInt(p.level, locale), icon: Shield },
  { label: 'dashboard.stat.dailyStreak', value: (p, locale) => fmtInt(p.streakDays, locale), icon: Flame },
]

/** Five stat cards across the top of the dashboard. */
export default function StatsCards({ profile, stats, examType = 'all' }) {
  const { t, locale } = useI18n()
  const examLabel = t({ all: 'dashboard.stat.examCount', tyt: 'dashboard.stat.examCountTyt', ayt: 'dashboard.stat.examCountAyt', branch: 'dashboard.stat.examCountBranch' }[examType])
  const values = {
    ...stats,
    totalXp: profile?.totalXp ?? 0,
    level: profile?.level ?? 1,
    streakDays: profile?.streakDays ?? 0,
  }
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {CARDS.map((card) => {
        const Icon = card.icon
        return (
          <div
            key={card.label}
            className="rounded-xl border border-canvas-line bg-canvas-panel p-4"
          >
            <div className="flex items-center gap-2 text-canvas-muted">
              <Icon size={14} />
              <span className="text-xs font-medium uppercase tracking-wider">
                {card.label === 'dashboard.stat.examCount' ? examLabel : t(card.label)}
              </span>
            </div>
            <div className="mt-2 text-2xl font-bold text-canvas-text">
              {card.value(values, locale)}
            </div>
          </div>
        )
      })}
    </div>
  )
}

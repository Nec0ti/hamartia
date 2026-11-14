import {
  GraduationCap,
  Target,
  Zap,
  Shield,
  Flame,
} from 'lucide-react'
import { fmtInt, fmtNet } from '../utils/formatters'

const CARDS = [
  { label: 'Deneme sayısı', value: (p) => fmtInt(p.total), icon: GraduationCap, tone: 'text-canvas-indigo' },
  { label: 'Ortalama net', value: (p) => fmtNet(p.avgNet), icon: Target, tone: 'text-emerald' },
  { label: 'Toplam XP', value: (p) => fmtInt(p.totalXp), icon: Zap, tone: 'text-canvas-cyan' },
  { label: 'Seviye', value: (p) => p.level, icon: Shield, tone: 'text-amber' },
  { label: 'Günlük seri', value: (p) => fmtInt(p.streakDays), icon: Flame, tone: 'text-orange' },
]

/** Five stat cards across the top of the dashboard. */
export default function StatsCards({ profile, stats }) {
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
                {card.label}
              </span>
            </div>
            <div className="mt-2 text-2xl font-bold text-canvas-text">
              {card.value(values)}
            </div>
          </div>
        )
      })}
    </div>
  )
}

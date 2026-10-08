import { useCallback, useEffect, useState } from 'react'
import {
  LayoutDashboard,
  FileQuestion,
  Globe,
  BookOpen,
  Settings,
  Sparkles,
} from 'lucide-react'
import api from '../services/api'
import { handleApiError } from '../services/api'
import { fmtInt, levelForXp, xpProgress, xpToNextLevel } from '../utils/formatters'

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'questions', label: 'Quest[ion]s', icon: FileQuestion },
  { id: 'cosmos', label: 'Cosmos', icon: Globe },
  { id: 'fatalflaw', label: 'Fatal Flaw', icon: BookOpen },
]

/**
 * Top navigation bar. Renders the four primary tabs, a collapsible Settings
 * trigger, and a live XP/Level badge driven by the user.json datastore.
 */
export default function Navbar({ activeTab, onSelectTab, onOpenSettings }) {
  const [profile, setProfile] = useState(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Progression profile (XP, level, radar) is stored in /user, not /settings.
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.user.get()
      const level = data.level ?? levelForXp(data.total_xp ?? 0)
      setProfile({
        total_xp: data.total_xp ?? 0,
        level,
        progress: xpProgress(data.total_xp ?? 0, level),
        nextThreshold: xpToNextLevel(level),
        radar: data.radar_stats ?? { speed: 50, focus: 50, precision: 50, stamina: 50 },
      })
    } catch (e) {
      const res = handleApiError(e)
      setError(res.detail)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const badge = profile
    ? { xp: profile.total_xp, level: profile.level, progress: profile.progress, next: profile.nextThreshold }
    : null

  return (
    <header className="sticky top-0 z-40 border-b border-canvas-line bg-canvas-panel/90 backdrop-blur">
      <div className="flex items-center gap-1 px-4 py-3">
        {/* Brand mark + title. */}
        <div className="flex items-center gap-2 mr-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-canvas-accent text-white shadow-crimson">
            <Sparkles size={16} />
          </div>
          <span className="text-lg font-bold tracking-tight text-canvas-text">
            Hamartia
          </span>
        </div>

        {/* Primary tab navigation. */}
        <nav className="flex flex-1 items-center gap-1 sm:gap-2">
          {TABS.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onSelectTab(tab.id)}
                className={[
                  'relative flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition',
                  isActive
                    ? 'text-white'
                    : 'text-canvas-muted hover:bg-canvas-raise hover:text-canvas-text',
                ].join(' ')}
              >
                {isActive && (
                  <span className="absolute left-0 top-1/2 h-5 w-0 -translate-y-1/2 rounded-r-lg bg-canvas-accent/80 transition-all duration-200" />
                )}
                <Icon size={16} className={isActive ? 'text-canvas-accent' : ''} />
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            )
          })}
        </nav>

        {/* Right rail: Settings trigger + XP/Level badge. */}
        <div className="flex items-center gap-2">
          {badge && (
            <div
              title={`Level ${badge.level} • ${fmtInt(badge.xp)} XP`}
              className="flex items-center gap-2 rounded-full border border-canvas-line bg-canvas-base px-3 py-1.5"
            >
              <div className="relative h-2 w-16 overflow-hidden rounded-full bg-canvas-line">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-canvas-indigo to-canvas-cyan transition-all duration-500"
                  style={{ width: `${Math.round(badge.progress * 100)}%` }}
                />
              </div>
              <span className="flex flex-col items-end leading-none">
                <span className="text-xs font-bold text-canvas-cyan">
                  Lvl {badge.level}
                </span>
                <span className="text-[10px] text-canvas-muted">
                  {fmtInt(badge.xp)} XP
                </span>
              </span>
            </div>
          )}

          <button
            type="button"
            onClick={() => {
              setSettingsOpen(true)
              onOpenSettings?.()
            }}
            className="relative rounded-lg border border-canvas-line bg-canvas-base p-2 text-canvas-muted transition hover:bg-canvas-raise hover:text-canvas-text"
            aria-label="Open settings"
          >
            <Settings size={18} />
          </button>
        </div>
      </div>

      {error && (
        <div className="border-t border-canvas-line bg-canvas-base px-4 py-2 text-xs text-canvas-muted">
          {error}
        </div>
      )}
    </header>
  )
}

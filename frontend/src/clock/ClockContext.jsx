import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import api from '../services/api'
import { useI18n } from '../i18n.jsx'
import { reconcileClock } from './engine.js'

const ClockContext = createContext(null)
const LEGACY_PRACTICE_KEY = 'hamartia.active-practice-session'
const EMPTY_CLOCK = {
  preferences: { pomodoro_work_minutes: 25, pomodoro_break_minutes: 5,
    pomodoro_cycle: false, notifications_opt_in: false },
  alarms: [],
  active_timer: null,
}

function readLegacyPracticeDraft() {
  try {
    const stored = JSON.parse(localStorage.getItem(LEGACY_PRACTICE_KEY))
    if (stored && typeof stored.subject === 'string' && typeof stored.topic === 'string'
      && /^\d{4}-\d{2}-\d{2}$/.test(stored.date)
      && ['correct', 'incorrect', 'blank', 'elapsed_seconds']
        .every((key) => Number.isInteger(stored[key]) && stored[key] >= 0)
      && (stored.running_since === null || Number.isFinite(stored.running_since))) return stored
  } catch {}
  return null
}

function practiceTimerFromLegacy(draft) {
  return {
    kind: 'practice',
    status: draft.running_since ? 'running' : 'paused',
    elapsed_ms: draft.elapsed_seconds * 1000,
    started_at_ms: draft.running_since,
    deadline_at_ms: null,
    duration_ms: 0,
    remaining_ms: 0,
    work_duration_ms: 0,
    break_duration_ms: 0,
    phase: null,
    cycle_enabled: false,
    cycle_count: 0,
    overdue_at_ms: null,
    laps: [],
    practice_draft: {
      date: draft.date,
      subject: draft.subject.trim(),
      topic: draft.topic.trim(),
      correct: draft.correct,
      incorrect: draft.incorrect,
      blank: draft.blank,
    },
  }
}

export function ClockProvider({ children }) {
  const { t } = useI18n()
  const [state, setState] = useState(EMPTY_CLOCK)
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [savingError, setSavingError] = useState('')
  const stateRef = useRef(EMPTY_CLOCK)
  const loadedRef = useRef(false)
  const queueRef = useRef(Promise.resolve())
  const notifiedRef = useRef(new Set())

  const load = useCallback(async () => {
    setLoaded(false)
    loadedRef.current = false
    setLoading(true)
    setSavingError('')
    try {
      let saved = await api.clock.get()
      stateRef.current = saved
      setState(saved)
      const legacy = readLegacyPracticeDraft()
      if (legacy) {
        const migrated = saved.active_timer
          ? saved
          : { ...saved, active_timer: practiceTimerFromLegacy(legacy) }
        // Persist successfully before removing the legacy draft. Repeating this
        // after a restart is safe because the active server state is authoritative.
        saved = await api.clock.update(migrated)
        try { localStorage.removeItem(LEGACY_PRACTICE_KEY) } catch {}
      }
      stateRef.current = saved
      setState(saved)
      loadedRef.current = true
      setLoaded(true)
      return true
    } catch {
      setSavingError('clock.persistenceError')
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const updateClock = useCallback((update) => {
    if (!loadedRef.current) return Promise.reject(new Error('Clock state has not loaded successfully'))
    const current = stateRef.current
    const next = typeof update === 'function' ? update(current) : update
    stateRef.current = next
    setState(next)
    setSavingError('')
    const task = queueRef.current.catch(() => {}).then(async () => {
      const saved = await api.clock.update(next)
      if (stateRef.current === next) {
        stateRef.current = saved
        setState(saved)
      }
      return saved
    }).catch(() => {
      if (stateRef.current === next) {
        stateRef.current = current
        setState(current)
      }
      setSavingError('clock.persistenceError')
      throw new Error('Clock state could not be saved')
    })
    queueRef.current = task
    return task
  }, [])

  useEffect(() => {
    if (!loaded) return undefined
    const reconcile = () => {
      const current = stateRef.current
      const result = reconcileClock(current, Date.now())
      if (JSON.stringify(current) === JSON.stringify(result.state)) return
      stateRef.current = result.state
      setState(result.state)
      void updateClock(result.state).catch(() => {})
      for (const event of result.events) {
        const eventKey = `${event.type}:${event.id || event.kind || 'timer'}:${event.at_ms}`
        if (notifiedRef.current.has(eventKey)) continue
        notifiedRef.current.add(eventKey)
        if (notifiedRef.current.size > 256) notifiedRef.current.delete(notifiedRef.current.values().next().value)
        if (!stateRef.current.preferences.notifications_opt_in
          || typeof window.Notification === 'undefined'
          || window.Notification.permission !== 'granted') continue
        const title = event.type === 'alarm' ? t('clock.reminders') : t('clock.title')
        const body = event.type === 'alarm'
          ? t('clock.alarmNotification', { label: event.label })
          : t('clock.timerNotification')
        try { new window.Notification(title, { body, tag: `hamartia-clock-${event.type}-${event.id || event.kind || 'timer'}` }) } catch {}
      }
    }
    reconcile()
    const interval = window.setInterval(reconcile, 1000)
    const onVisibility = () => { if (document.visibilityState === 'visible') reconcile() }
    window.addEventListener('focus', reconcile)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearInterval(interval)
      window.removeEventListener('focus', reconcile)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [loaded, t, updateClock])

  const value = useMemo(() => ({
    state,
    loaded,
    loading,
    savingError,
    updateClock,
    reload: load,
  }), [state, loaded, loading, savingError, updateClock, load])

  return <ClockContext.Provider value={value}>{children}</ClockContext.Provider>
}

export function useClock() {
  const context = useContext(ClockContext)
  if (!context) throw new Error('useClock must be used inside ClockProvider')
  return context
}

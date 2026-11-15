import { useEffect, useState } from 'react'
import { Bell, BellOff, CircleStop, Pause, Play, RotateCcw, SkipForward } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import { useClock } from '../clock/ClockContext.jsx'
import {
  elapsedMilliseconds, localDateTime, millisecondsLabel, nextWeekdayOccurrence,
  pauseTimer, remainingMilliseconds, resumeTimer,
} from '../clock/engine.js'

const WEEKDAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
const modes = ['pomodoro', 'countdown', 'stopwatch']

export default function ClockTab() {
  const { t, locale } = useI18n()
  const { state, loaded, loading, savingError, updateClock, reload } = useClock()
  const [now, setNow] = useState(Date.now())
  const [selectedMode, setSelectedMode] = useState('pomodoro')
  const [countdownMinutes, setCountdownMinutes] = useState(5)
  const [countdownSeconds, setCountdownSeconds] = useState(0)
  const [pomodoroWork, setPomodoroWork] = useState(state.preferences.pomodoro_work_minutes)
  const [pomodoroBreak, setPomodoroBreak] = useState(state.preferences.pomodoro_break_minutes)
  const [pomodoroCycle, setPomodoroCycle] = useState(state.preferences.pomodoro_cycle)
  const [alarmLabel, setAlarmLabel] = useState('')
  const [alarmKind, setAlarmKind] = useState('once')
  const [alarmDate, setAlarmDate] = useState(() => localDateInput(Date.now()))
  const [alarmTime, setAlarmTime] = useState('09:00')
  const [alarmDays, setAlarmDays] = useState([])
  const [editingAlarm, setEditingAlarm] = useState('')
  const [formError, setFormError] = useState('')
  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(interval)
  }, [])

  useEffect(() => {
    setPomodoroWork(state.preferences.pomodoro_work_minutes)
    setPomodoroBreak(state.preferences.pomodoro_break_minutes)
    setPomodoroCycle(state.preferences.pomodoro_cycle)
  }, [state.preferences.pomodoro_work_minutes, state.preferences.pomodoro_break_minutes, state.preferences.pomodoro_cycle])

  const save = (mutator) => updateClock(mutator).catch(() => setFormError('clock.persistenceError'))
  const currentTimer = state.active_timer
  const clockDisplay = localDateTime(now, locale)
  const timerValue = currentTimer && (currentTimer.kind === 'countdown' || currentTimer.kind === 'pomodoro'
    ? remainingMilliseconds(currentTimer, now)
    : elapsedMilliseconds(currentTimer, now))

  const enableNotifications = async () => {
    if (state.preferences.notifications_opt_in) {
      await save((current) => ({ ...current, preferences: { ...current.preferences, notifications_opt_in: false } }))
      return
    }
    if (typeof window.Notification === 'undefined' || !window.Notification.requestPermission) {
      setFormError('clock.notificationsUnavailable')
      return
    }
    try {
      const permission = await window.Notification.requestPermission()
      const enabled = permission === 'granted'
      await save((current) => ({ ...current, preferences: { ...current.preferences, notifications_opt_in: enabled } }))
      if (!enabled) setFormError('clock.notificationsUnavailable')
    } catch { setFormError('clock.notificationsUnavailable') }
  }

  const startPomodoro = () => {
    const work = state.preferences.pomodoro_work_minutes * 60_000
    const rest = state.preferences.pomodoro_break_minutes * 60_000
    const started = Date.now()
    void save((current) => ({ ...current, active_timer: {
      kind: 'pomodoro', status: 'running', elapsed_ms: 0, started_at_ms: null,
      deadline_at_ms: started + work, duration_ms: work, remaining_ms: work,
      work_duration_ms: work, break_duration_ms: rest, phase: 'work',
      cycle_enabled: current.preferences.pomodoro_cycle, cycle_count: 0,
      overdue_at_ms: null, laps: [], practice_draft: null,
    } }))
  }

  const startCountdown = () => {
    const duration = (Number(countdownMinutes) * 60 + Number(countdownSeconds)) * 1000
    if (!Number.isSafeInteger(duration) || duration < 1000 || duration > 86_400_000) {
      setFormError('clock.invalidCountdown')
      return
    }
    const started = Date.now()
    void save((current) => ({ ...current, active_timer: {
      kind: 'countdown', status: 'running', elapsed_ms: 0, started_at_ms: null,
      deadline_at_ms: started + duration, duration_ms: duration, remaining_ms: duration,
      work_duration_ms: 0, break_duration_ms: 0, phase: null,
      cycle_enabled: false, cycle_count: 0, overdue_at_ms: null, laps: [], practice_draft: null,
    } }))
  }

  const startStopwatch = () => {
    void save((current) => ({ ...current, active_timer: {
      kind: 'stopwatch', status: 'running', elapsed_ms: 0, started_at_ms: Date.now(),
      deadline_at_ms: null, duration_ms: 0, remaining_ms: 0,
      work_duration_ms: 0, break_duration_ms: 0, phase: null,
      cycle_enabled: false, cycle_count: 0, overdue_at_ms: null, laps: [], practice_draft: null,
    } }))
  }

  const resetTimer = () => {
    if (!currentTimer) return
    let reset = { ...currentTimer, status: 'paused', started_at_ms: null, deadline_at_ms: null, overdue_at_ms: null }
    if (currentTimer.kind === 'practice') reset = { ...reset, elapsed_ms: 0 }
    if (currentTimer.kind === 'stopwatch') reset = { ...reset, elapsed_ms: 0, laps: [] }
    if (currentTimer.kind === 'countdown') reset = { ...reset, remaining_ms: currentTimer.duration_ms }
    if (currentTimer.kind === 'pomodoro') {
      reset = { ...reset, phase: 'work', duration_ms: currentTimer.work_duration_ms,
        remaining_ms: currentTimer.work_duration_ms, cycle_count: 0 }
    }
    void save((current) => ({ ...current, active_timer: reset }))
  }

  const skipPhase = () => {
    if (currentTimer?.kind !== 'pomodoro') return
    const phase = currentTimer.phase === 'work' ? 'break' : 'work'
    const duration = phase === 'work' ? currentTimer.work_duration_ms : currentTimer.break_duration_ms
    const running = currentTimer.status === 'running'
    const change = {
      ...currentTimer, phase, duration_ms: duration, remaining_ms: duration,
      deadline_at_ms: running ? Date.now() + duration : null,
      started_at_ms: null, status: running ? 'running' : 'paused', overdue_at_ms: null,
      cycle_count: currentTimer.cycle_count + (currentTimer.phase === 'work' ? 1 : 0),
    }
    void save((current) => ({ ...current, active_timer: change }))
  }

  const clearTimer = () => {
    if (!currentTimer || currentTimer.kind === 'practice') return
    if (!window.confirm(t('clock.clearTimerConfirm'))) return
    void save((current) => ({ ...current, active_timer: null }))
  }

  const savePomodoroPreferences = (event) => {
    event.preventDefault()
    if (!Number.isInteger(Number(pomodoroWork)) || Number(pomodoroWork) < 1 || Number(pomodoroWork) > 180
      || !Number.isInteger(Number(pomodoroBreak)) || Number(pomodoroBreak) < 1 || Number(pomodoroBreak) > 60) {
      setFormError('clock.invalidPomodoro')
      return
    }
    void save((current) => ({ ...current, preferences: {
      ...current.preferences, pomodoro_work_minutes: Number(pomodoroWork),
      pomodoro_break_minutes: Number(pomodoroBreak), pomodoro_cycle: pomodoroCycle,
    } }))
  }

  const resetAlarmForm = () => {
    setAlarmLabel('')
    setAlarmKind('once')
    setAlarmDate(localDateInput(Date.now()))
    setAlarmTime('09:00')
    setAlarmDays([])
    setEditingAlarm('')
    setFormError('')
  }

  const submitAlarm = (event) => {
    event.preventDefault()
    setFormError('')
    const label = alarmLabel.trim()
    const nowAt = Date.now()
    let alarm
    if (alarmKind === 'once') {
      const at = localDateTimeInput(alarmDate, alarmTime)
      if (!label || !Number.isFinite(at) || at <= nowAt) {
        setFormError('clock.invalidReminder')
        return
      }
      alarm = { id: editingAlarm || makeId(), label, kind: 'once', one_off_at_ms: at,
        local_time: '', weekdays: [], enabled: true, next_at_ms: at, overdue_at_ms: null, last_fired_at_ms: null }
    } else {
      if (!label || !alarmDays.length) {
        setFormError('clock.invalidReminder')
        return
      }
      alarm = { id: editingAlarm || makeId(), label, kind: 'weekdays', one_off_at_ms: null,
        local_time: alarmTime, weekdays: [...alarmDays].sort((a, b) => a - b), enabled: true,
        next_at_ms: nextWeekdayOccurrence(alarmDays, alarmTime, nowAt), overdue_at_ms: null, last_fired_at_ms: null }
    }
    const existing = state.alarms.find((item) => item.id === editingAlarm)
    if (!existing && state.alarms.length >= 128) {
      setFormError('clock.limitReached')
      return
    }
    if (existing) alarm.last_fired_at_ms = existing.last_fired_at_ms
    void save((current) => ({ ...current, alarms: [
      ...current.alarms.filter((item) => item.id !== alarm.id), alarm,
    ] }))
    resetAlarmForm()
  }

  const editAlarm = (alarm) => {
    setEditingAlarm(alarm.id)
    setAlarmLabel(alarm.label)
    setAlarmKind(alarm.kind)
    setAlarmTime(alarm.kind === 'once' ? localTimeInput(alarm.one_off_at_ms) : alarm.local_time)
    setAlarmDate(alarm.kind === 'once' ? localDateInput(alarm.one_off_at_ms) : localDateInput(Date.now()))
    setAlarmDays(alarm.weekdays || [])
    setFormError('')
  }

  const toggleAlarm = (alarm) => {
    if (alarm.enabled) {
      void save((current) => ({ ...current, alarms: current.alarms.map((item) => item.id === alarm.id
        ? { ...item, enabled: false } : item) }))
      return
    }
    const next = alarm.kind === 'once' ? alarm.one_off_at_ms
      : nextWeekdayOccurrence(alarm.weekdays, alarm.local_time, Date.now())
    if (next <= Date.now()) {
      setFormError('clock.invalidReminder')
      return
    }
    void save((current) => ({ ...current, alarms: current.alarms.map((item) => item.id === alarm.id
      ? { ...item, enabled: true, next_at_ms: next, overdue_at_ms: null } : item) }))
  }

  const dismissOverdue = (alarm) => {
    void save((current) => ({ ...current, alarms: current.alarms.map((item) => item.id === alarm.id
      ? { ...item, overdue_at_ms: null } : item) }))
  }

  const deleteAlarm = (alarm) => {
    if (editingAlarm === alarm.id) resetAlarmForm()
    void save((current) => ({ ...current, alarms: current.alarms.filter((item) => item.id !== alarm.id) }))
  }

  const toggleDay = (day) => setAlarmDays((current) => current.includes(day)
    ? current.filter((item) => item !== day)
    : [...current, day])

  const statusLabel = currentTimer?.status === 'running' ? t('clock.running')
    : currentTimer?.status === 'overdue' ? t('clock.overdue') : t('clock.paused')
  const timerTitle = currentTimer ? t(`clock.${currentTimer.kind === 'practice' ? 'practiceTimer' : currentTimer.kind}`) : ''
  const canCreate = loaded && !currentTimer
  const secondary = 'rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-muted hover:bg-canvas-raise focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-canvas-text'
  const input = 'mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-canvas-text'

  return <section aria-labelledby="clock-heading" className="mx-auto max-w-5xl space-y-5">
    <header className="space-y-1">
      <h1 id="clock-heading" className="text-2xl font-bold text-canvas-text">{t('clock.title')}</h1>
      <p className="text-sm text-canvas-muted">{t('clock.subtitle')}</p>
    </header>
    {loading && <p role="status" className="rounded-lg border border-canvas-line bg-canvas-panel p-3 text-sm text-canvas-muted">{t('clock.loading')}</p>}
    {(savingError || formError) && <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-canvas-line bg-canvas-panel p-3 text-sm text-canvas-muted"><span>{t(formError || savingError)}</span>{savingError && <button type="button" onClick={reload} className={secondary}>{t('clock.reload')}</button>}</div>}

    <section aria-label={t('clock.localTime')} className="rounded-xl border border-canvas-line bg-canvas-panel p-5">
      <p className="text-xs uppercase tracking-wide text-canvas-muted">{t('clock.localTime')}</p>
      <time className="mt-1 block font-mono text-4xl font-semibold tabular-nums text-canvas-text" dateTime={new Date(now).toISOString()}>{clockDisplay.time}</time>
      <p className="mt-1 text-sm text-canvas-muted">{clockDisplay.date}</p>
    </section>

    <section aria-label={t('clock.title')} className="rounded-xl border border-canvas-line bg-canvas-panel p-5">
      {currentTimer ? <>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="text-lg font-semibold text-canvas-text">{timerTitle}{currentTimer.kind === 'pomodoro' ? ` · ${t(`clock.${currentTimer.phase}`)}` : ''}</h2><p className="text-sm text-canvas-muted">{statusLabel}</p></div>
          <output aria-label={currentTimer.kind === 'countdown' || currentTimer.kind === 'pomodoro' ? t('clock.remaining') : t('clock.elapsed')} className="font-mono text-4xl font-semibold tabular-nums text-canvas-text">{millisecondsLabel(timerValue || 0)}</output>
        </div>
        {currentTimer.status === 'overdue' && <p role="status" className="mt-3 rounded-lg border border-canvas-line bg-canvas-base p-3 text-sm font-medium text-canvas-text">{t('clock.overdue')}</p>}
        {currentTimer.kind === 'practice' && <p className="mt-2 text-sm text-canvas-muted">{currentTimer.practice_draft.subject} · {currentTimer.practice_draft.topic}</p>}
        {currentTimer.kind === 'stopwatch' && currentTimer.laps.length > 0 && <ol className="mt-4 grid gap-1 sm:grid-cols-2" aria-label={t('clock.stopwatch')}>
          {currentTimer.laps.slice().reverse().map((lap, index) => <li key={`${lap.recorded_at_ms}-${index}`} className="flex justify-between border-b border-canvas-line py-1 text-sm text-canvas-muted"><span>{t('clock.lapNumber', { number: currentTimer.laps.length - index })}</span><time className="font-mono">{millisecondsLabel(lap.elapsed_ms)}</time></li>)}
        </ol>}
        <div className="mt-4 flex flex-wrap gap-2">
          {currentTimer.status === 'running'
            ? <button type="button" disabled={!loaded} onClick={() => void save((current) => ({ ...current, active_timer: pauseTimer(current.active_timer, Date.now()) }))} className={secondary}><Pause size={15} className="mr-1 inline" />{t('clock.pause')}</button>
            : <button type="button" disabled={!loaded || currentTimer.status === 'overdue'} onClick={() => void save((current) => ({ ...current, active_timer: resumeTimer(current.active_timer, Date.now()) }))} className={secondary}><Play size={15} className="mr-1 inline" />{t('clock.resume')}</button>}
          {currentTimer.kind === 'stopwatch' && <button type="button" disabled={!loaded} onClick={() => void save((current) => ({ ...current, active_timer: { ...current.active_timer, laps: [...current.active_timer.laps, { elapsed_ms: elapsedMilliseconds(current.active_timer, Date.now()), recorded_at_ms: Date.now() }].slice(-100) } }))} className={secondary}>{t('clock.lap')}</button>}
          {currentTimer.kind === 'pomodoro' && <button type="button" disabled={!loaded} onClick={skipPhase} className={secondary}><SkipForward size={15} className="mr-1 inline" />{t('clock.skipPhase')}</button>}
          <button type="button" disabled={!loaded} onClick={resetTimer} className={secondary}><RotateCcw size={15} className="mr-1 inline" />{t('clock.reset')}</button>
          {currentTimer.kind !== 'practice' && <button type="button" disabled={!loaded} onClick={clearTimer} className={secondary}><CircleStop size={15} className="mr-1 inline" />{t('clock.clearTimer')}</button>}
        </div>
      </> : <>
        <div className="flex flex-wrap gap-2" role="group" aria-label={t('clock.title')}>
          {modes.map((mode) => <button key={mode} type="button" aria-pressed={selectedMode === mode} onClick={() => setSelectedMode(mode)} className={selectedMode === mode ? 'rounded-lg bg-canvas-text px-3 py-2 text-sm font-medium text-canvas-base' : secondary}>{t(`clock.${mode}`)}</button>)}
        </div>
        {selectedMode === 'pomodoro' && <div className="mt-4 space-y-4">
          <form onSubmit={savePomodoroPreferences} className="grid gap-3 rounded-lg bg-canvas-base p-3 sm:grid-cols-3">
            <label className="text-xs text-canvas-muted">{t('clock.workMinutes')}<input className={input} type="number" min="1" max="180" value={pomodoroWork} onChange={(event) => setPomodoroWork(event.target.value)} /></label>
            <label className="text-xs text-canvas-muted">{t('clock.breakMinutes')}<input className={input} type="number" min="1" max="60" value={pomodoroBreak} onChange={(event) => setPomodoroBreak(event.target.value)} /></label>
            <label className="flex items-center gap-2 self-end pb-2 text-sm text-canvas-text"><input type="checkbox" checked={pomodoroCycle} onChange={(event) => setPomodoroCycle(event.target.checked)} />{t('clock.autoCycle')}</label>
            <button disabled={!loaded} className={`${secondary} sm:col-span-3 sm:justify-self-end disabled:opacity-50`}>{t('clock.savePreferences')}</button>
          </form>
          <button type="button" disabled={!canCreate} onClick={startPomodoro} className="rounded-lg bg-canvas-text px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50"><Play size={15} className="mr-1 inline" />{t('clock.start')}</button>
        </div>}
        {selectedMode === 'countdown' && <form onSubmit={(event) => { event.preventDefault(); startCountdown() }} className="mt-4 flex flex-wrap items-end gap-3">
          <label className="text-xs text-canvas-muted">{t('clock.minutes')}<input className={input} type="number" min="0" max="1439" value={countdownMinutes} onChange={(event) => setCountdownMinutes(event.target.value)} /></label>
          <label className="text-xs text-canvas-muted">{t('clock.seconds')}<input className={input} type="number" min="0" max="59" value={countdownSeconds} onChange={(event) => setCountdownSeconds(event.target.value)} /></label>
          <button disabled={!canCreate} className="rounded-lg bg-canvas-text px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50"><Play size={15} className="mr-1 inline" />{t('clock.start')}</button>
        </form>}
        {selectedMode === 'stopwatch' && <div className="mt-4"><button type="button" disabled={!canCreate} onClick={startStopwatch} className="rounded-lg bg-canvas-text px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50"><Play size={15} className="mr-1 inline" />{t('clock.start')}</button></div>}
      </>}
    </section>

    <section className="rounded-xl border border-canvas-line bg-canvas-panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-canvas-text">{t('clock.reminders')}</h2><p className="mt-1 text-xs leading-relaxed text-canvas-muted">{t('clock.awakeNote')}</p></div>
        <button type="button" disabled={!loaded} onClick={enableNotifications} className={`${secondary} disabled:opacity-50`}>{state.preferences.notifications_opt_in ? <Bell size={15} className="mr-1 inline" /> : <BellOff size={15} className="mr-1 inline" />}{state.preferences.notifications_opt_in ? t('clock.notificationsDisable') : t('clock.notificationPermission')}</button></div>
      {!state.preferences.notifications_opt_in && <p className="mt-2 text-xs text-canvas-muted">{t('clock.notificationsOff')}</p>}
      <form onSubmit={submitAlarm} className="mt-4 grid gap-3 rounded-lg bg-canvas-base p-3 sm:grid-cols-2">
        <label className="text-xs text-canvas-muted sm:col-span-2">{t('clock.reminderLabel')}<input required maxLength="80" className={input} value={alarmLabel} onChange={(event) => setAlarmLabel(event.target.value)} /></label>
        <label className="text-xs text-canvas-muted">{t('clock.once')} / {t('clock.weekdays')}<select className={input} value={alarmKind} onChange={(event) => setAlarmKind(event.target.value)}><option value="once">{t('clock.once')}</option><option value="weekdays">{t('clock.weekdays')}</option></select></label>
        <label className="text-xs text-canvas-muted">{t('clock.time')}<input required className={input} type="time" value={alarmTime} onChange={(event) => setAlarmTime(event.target.value)} /></label>
        {alarmKind === 'once' ? <label className="text-xs text-canvas-muted">{t('clock.date')}<input required className={input} type="date" value={alarmDate} onChange={(event) => setAlarmDate(event.target.value)} /></label>
          : <fieldset className="sm:col-span-2"><legend className="text-xs text-canvas-muted">{t('clock.weekdays')}</legend><div className="mt-2 flex flex-wrap gap-3">{WEEKDAYS.map((day, index) => <label key={day} className="flex items-center gap-1 text-sm text-canvas-text"><input type="checkbox" checked={alarmDays.includes(index)} onChange={() => toggleDay(index)} />{t(`clock.${day}`)}</label>)}</div></fieldset>}
        <div className="flex flex-wrap justify-end gap-2 sm:col-span-2">{editingAlarm && <button type="button" onClick={resetAlarmForm} className={secondary}>{t('clock.cancelEdit')}</button>}<button disabled={!loaded} className="rounded-lg bg-canvas-text px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{editingAlarm ? t('clock.editReminder') : t('clock.saveReminder')}</button></div>
      </form>
      {state.alarms.length === 0 ? <p className="mt-4 rounded-lg border border-dashed border-canvas-line p-4 text-sm text-canvas-muted">{t('clock.noReminders')}</p> : <ul className="mt-4 space-y-2">{state.alarms.map((alarm) => {
        const occurrence = alarm.next_at_ms ? new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(alarm.next_at_ms)) : ''
        const overdue = alarm.overdue_at_ms ? new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(alarm.overdue_at_ms)) : ''
        return <li key={alarm.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-canvas-line bg-canvas-base p-3">
          <div><p className="font-medium text-canvas-text">{alarm.label}</p><p className="text-xs text-canvas-muted">{overdue ? t('clock.overdueReminder', { time: overdue }) : t(alarm.enabled ? 'clock.nextReminder' : 'clock.disabled', { time: occurrence })}</p></div>
          <div className="flex flex-wrap gap-1"><button type="button" disabled={!loaded} aria-label={t(alarm.enabled ? 'clock.enabled' : 'clock.disabled')} onClick={() => toggleAlarm(alarm)} className={secondary}>{t(alarm.enabled ? 'clock.enabled' : 'clock.disabled')}</button><button type="button" disabled={!loaded} onClick={() => editAlarm(alarm)} className={secondary}>{t('common.edit')}</button>{alarm.overdue_at_ms && <button type="button" disabled={!loaded} onClick={() => dismissOverdue(alarm)} className={secondary}>{t('clock.dismissOverdue')}</button>}<button type="button" disabled={!loaded} aria-label={t('clock.deleteReminder', { label: alarm.label })} onClick={() => deleteAlarm(alarm)} className={secondary}>{t('common.delete')}</button></div>
        </li>
      })}</ul>}
    </section>
  </section>
}

function localDateInput(timestamp) {
  const date = new Date(timestamp)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function localTimeInput(timestamp) {
  const date = new Date(timestamp)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function localDateTimeInput(date, time) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) return Number.NaN
  const [year, month, day] = date.split('-').map(Number)
  const [hour, minute] = time.split(':').map(Number)
  const candidate = new Date(year, month - 1, day, hour, minute, 0, 0)
  if (candidate.getFullYear() !== year || candidate.getMonth() !== month - 1 || candidate.getDate() !== day
    || candidate.getHours() !== hour || candidate.getMinutes() !== minute) return Number.NaN
  return candidate.getTime()
}

function makeId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `alarm-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

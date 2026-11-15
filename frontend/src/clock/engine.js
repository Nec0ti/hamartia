const MINUTE = 60_000
const DAY = 86_400_000

export function elapsedMilliseconds(timer, now = Date.now()) {
  if (!timer) return 0
  return Math.max(0, timer.elapsed_ms + (timer.status === 'running' && timer.started_at_ms != null
    ? now - timer.started_at_ms
    : 0))
}

export function remainingMilliseconds(timer, now = Date.now()) {
  if (!timer) return 0
  if (timer.status === 'running' && timer.deadline_at_ms != null) {
    return Math.max(0, timer.deadline_at_ms - now)
  }
  return Math.max(0, timer.remaining_ms || 0)
}

export function pauseTimer(timer, now = Date.now()) {
  if (!timer || timer.status !== 'running') return timer
  if (timer.kind === 'countdown' || timer.kind === 'pomodoro') {
    const remaining = remainingMilliseconds(timer, now)
    if (remaining === 0) {
      return { ...timer, status: 'overdue', deadline_at_ms: null, started_at_ms: null,
        remaining_ms: 0, overdue_at_ms: timer.deadline_at_ms }
    }
    return { ...timer, status: 'paused', deadline_at_ms: null, started_at_ms: null,
      remaining_ms: remaining, overdue_at_ms: null }
  }
  return { ...timer, status: 'paused', started_at_ms: null, deadline_at_ms: null,
    elapsed_ms: elapsedMilliseconds(timer, now), overdue_at_ms: null }
}

export function resumeTimer(timer, now = Date.now()) {
  if (!timer || timer.status !== 'paused') return timer
  if (timer.kind === 'countdown' || timer.kind === 'pomodoro') {
    const remaining = Math.max(0, timer.remaining_ms)
    if (!remaining) return { ...timer, status: 'overdue', remaining_ms: 0, overdue_at_ms: now }
    return { ...timer, status: 'running', started_at_ms: null, deadline_at_ms: now + remaining,
      overdue_at_ms: null }
  }
  return { ...timer, status: 'running', started_at_ms: now, deadline_at_ms: null,
    overdue_at_ms: null }
}

function nextPomodoroPhase(timer, now) {
  const safeWork = Math.max(1_000, timer.work_duration_ms)
  const safeBreak = Math.max(1_000, timer.break_duration_ms)
  const oldDeadline = timer.deadline_at_ms
  let anchor = oldDeadline
  let elapsed = Math.max(0, now - oldDeadline)
  let phase = timer.phase === 'work' ? 'break' : 'work'
  let cycles = timer.cycle_count + (timer.phase === 'work' ? 1 : 0)

  let duration = phase === 'work' ? safeWork : safeBreak
  if (elapsed >= duration) {
    elapsed -= duration
    anchor += duration
    if (phase === 'work') cycles += 1
    phase = phase === 'work' ? 'break' : 'work'
    duration = phase === 'work' ? safeWork : safeBreak
  }
  // A full pair completes exactly one work phase. Divide rather than looping
  // so even a long suspension takes constant time and produces one event.
  const completePairs = Math.floor(elapsed / (safeWork + safeBreak))
  if (completePairs > 0) {
    anchor += completePairs * (safeWork + safeBreak)
    elapsed -= completePairs * (safeWork + safeBreak)
    cycles += completePairs
  }
  if (elapsed >= duration) {
    elapsed -= duration
    anchor += duration
    if (phase === 'work') cycles += 1
    phase = phase === 'work' ? 'break' : 'work'
    duration = phase === 'work' ? safeWork : safeBreak
  }
  const remaining = duration - elapsed
  return { endedAt: oldDeadline, timer: {
    ...timer,
    status: 'running',
    phase,
    cycle_count: cycles,
    duration_ms: duration,
    remaining_ms: remaining,
    deadline_at_ms: anchor + duration,
    started_at_ms: null,
    overdue_at_ms: null,
  } }
}

export function reconcileClock(state, now = Date.now()) {
  let timer = state.active_timer
  const events = []
  if (timer?.status === 'running' && timer.deadline_at_ms != null && timer.deadline_at_ms <= now) {
    if (timer.kind === 'pomodoro' && timer.cycle_enabled) {
      const transition = nextPomodoroPhase(timer, now)
      timer = transition.timer
      events.push({ type: 'pomodoro-phase-ended', at_ms: transition.endedAt, phase: timer.phase })
    } else {
      const endedAt = timer.deadline_at_ms
      timer = { ...timer, status: 'overdue', deadline_at_ms: null, started_at_ms: null,
        remaining_ms: 0, overdue_at_ms: endedAt }
      events.push({ type: 'timer-ended', at_ms: endedAt, kind: timer.kind })
    }
  }

  const alarms = state.alarms.map((alarm) => {
    if (!alarm.enabled || alarm.next_at_ms == null || alarm.next_at_ms > now
      || alarm.last_fired_at_ms === alarm.next_at_ms) return alarm
    const firedAt = alarm.next_at_ms
    events.push({ type: 'alarm', id: alarm.id, label: alarm.label, at_ms: firedAt })
    if (alarm.kind === 'once') {
      return { ...alarm, enabled: false, overdue_at_ms: firedAt, last_fired_at_ms: firedAt }
    }
    return { ...alarm, overdue_at_ms: firedAt, last_fired_at_ms: firedAt,
      next_at_ms: nextWeekdayOccurrence(alarm.weekdays, alarm.local_time, now) }
  })
  return { state: { ...state, active_timer: timer, alarms }, events }
}

export function nextWeekdayOccurrence(weekdays, localTime, after = Date.now()) {
  const [hours, minutes] = localTime.split(':').map(Number)
  const now = new Date(after)
  for (let offset = 0; offset <= 7; offset += 1) {
    const candidate = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset, hours, minutes, 0, 0)
    if (weekdays.includes(candidate.getDay()) && candidate.getTime() > after) return candidate.getTime()
  }
  return after + 7 * DAY
}

export function localDateTime(now = Date.now(), locale = 'en-US') {
  const date = new Date(now)
  return {
    date: new Intl.DateTimeFormat(locale, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }).format(date),
    time: new Intl.DateTimeFormat(locale, { hour: 'numeric', minute: '2-digit', second: '2-digit' }).format(date),
  }
}

export function millisecondsLabel(milliseconds) {
  const totalSeconds = Math.floor(Math.max(0, milliseconds) / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export const DEFAULT_POMODORO_WORK_MS = 25 * MINUTE
export const DEFAULT_POMODORO_BREAK_MS = 5 * MINUTE
export const MINUTE_MS = MINUTE

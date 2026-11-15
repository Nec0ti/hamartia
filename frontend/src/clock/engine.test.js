import test from 'node:test'
import assert from 'node:assert/strict'
import {
  elapsedMilliseconds, millisecondsLabel, nextWeekdayOccurrence, pauseTimer,
  reconcileClock, remainingMilliseconds, resumeTimer,
} from './engine.js'

test('running timers derive elapsed and remaining time from timestamps', () => {
  const timer = { kind: 'practice', status: 'running', elapsed_ms: 2_000, started_at_ms: 10_000 }
  assert.equal(elapsedMilliseconds(timer, 13_500), 5_500)
  const countdown = { kind: 'countdown', status: 'running', remaining_ms: 10_000, deadline_at_ms: 20_000 }
  assert.equal(remainingMilliseconds(countdown, 13_500), 6_500)
})

test('pause and resume store remaining duration without accumulating interval drift', () => {
  const timer = { kind: 'countdown', status: 'running', duration_ms: 30_000,
    remaining_ms: 30_000, deadline_at_ms: 50_000, started_at_ms: null }
  const paused = pauseTimer(timer, 27_000)
  assert.equal(paused.remaining_ms, 23_000)
  assert.equal(paused.deadline_at_ms, null)
  const resumed = resumeTimer(paused, 100_000)
  assert.equal(resumed.deadline_at_ms, 123_000)
  assert.equal(resumed.remaining_ms, 23_000)
})

test('expired countdown becomes one visible overdue event and does not refire', () => {
  const state = { active_timer: { kind: 'countdown', status: 'running', duration_ms: 5_000,
    remaining_ms: 5_000, deadline_at_ms: 10_000, started_at_ms: null }, alarms: [] }
  const first = reconcileClock(state, 15_000)
  assert.equal(first.state.active_timer.status, 'overdue')
  assert.equal(first.events.length, 1)
  const second = reconcileClock(first.state, 20_000)
  assert.equal(second.events.length, 0)
})

test('Pomodoro resume reconciliation skips missed cycles without alert bursts', () => {
  const state = { alarms: [], active_timer: { kind: 'pomodoro', status: 'running',
    phase: 'work', duration_ms: 10_000, work_duration_ms: 10_000, break_duration_ms: 5_000,
    cycle_enabled: true, cycle_count: 0, remaining_ms: 10_000, deadline_at_ms: 10_000,
    started_at_ms: null } }
  const result = reconcileClock(state, 33_000)
  assert.equal(result.state.active_timer.phase, 'work')
  assert.equal(result.state.active_timer.cycle_count, 2)
  assert.equal(result.state.active_timer.deadline_at_ms, 40_000)
  assert.equal(result.events.length, 1)
})

test('Pomodoro phase boundaries and long suspension reconcile directly to one future deadline', () => {
  const timer = { kind: 'pomodoro', status: 'running', phase: 'work', duration_ms: 10_000,
    work_duration_ms: 10_000, break_duration_ms: 5_000, cycle_enabled: true,
    cycle_count: 0, remaining_ms: 10_000, deadline_at_ms: 10_000, started_at_ms: null }
  const oneBoundary = reconcileClock({ active_timer: timer, alarms: [] }, 10_000).state.active_timer
  assert.equal(oneBoundary.phase, 'break')
  assert.equal(oneBoundary.deadline_at_ms, 15_000)
  assert.equal(oneBoundary.cycle_count, 1)
  const twoBoundaries = reconcileClock({ active_timer: timer, alarms: [] }, 15_000).state.active_timer
  assert.equal(twoBoundaries.phase, 'work')
  assert.equal(twoBoundaries.deadline_at_ms, 25_000)
  const longPause = reconcileClock({ active_timer: timer, alarms: [] }, 1_000_000_000)
  assert.ok(longPause.state.active_timer.deadline_at_ms > 1_000_000_000)
  assert.equal(longPause.events.length, 1)
})

test('alarm expiration is persisted using the schema overdue timestamp and cannot refire', () => {
  const alarm = { id: 'once-1', label: 'Review', kind: 'once', one_off_at_ms: 10_000,
    next_at_ms: 10_000, enabled: true, last_fired_at_ms: null, overdue_at_ms: null }
  const first = reconcileClock({ active_timer: null, alarms: [alarm] }, 20_000)
  assert.equal(first.state.alarms[0].overdue_at_ms, 10_000)
  assert.equal(first.state.alarms[0].enabled, false)
  assert.equal(first.events.length, 1)
  assert.equal(reconcileClock(first.state, 30_000).events.length, 0)
})

test('weekday alarm occurrence is the next matching local wall time', () => {
  const thursday = new Date(2026, 0, 1, 9, 0, 0, 0).getTime()
  const friday = nextWeekdayOccurrence([5], '09:00', thursday)
  const date = new Date(friday)
  assert.equal(date.getDay(), 5)
  assert.equal(date.getHours(), 9)
  assert.equal(date.getMinutes(), 0)
  assert.ok(friday > thursday)
})

test('time output is hours, minutes and seconds', () => {
  assert.equal(millisecondsLabel(3_723_999), '01:02:03')
})

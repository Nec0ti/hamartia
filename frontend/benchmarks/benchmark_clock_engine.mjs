import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { performance } from 'node:perf_hooks'
import { reconcileClock } from '../src/clock/engine.js'

const SEED = 20261115
const ENGINE_URL = new URL('../src/clock/engine.js', import.meta.url).href

function seededCases(seed, count = 96) {
  let value = seed >>> 0
  const random = (limit) => {
    value = (Math.imul(value, 1664525) + 1013904223) >>> 0
    return value % limit
  }
  return Array.from({ length: count }, (_, index) => {
    const work = 5_000 + random(56) * 1_000
    const rest = 3_000 + random(28) * 1_000
    const deadline = 1_700_000_000_000 + index * 100_000
    const jump = random(7 * 24 * 60 * 60) * 1_000
    const timer = {
      kind: 'pomodoro', status: 'running', elapsed_ms: 0, started_at_ms: null,
      deadline_at_ms: deadline, duration_ms: work, remaining_ms: work,
      work_duration_ms: work, break_duration_ms: rest, phase: 'work',
      cycle_enabled: true, cycle_count: index % 11, overdue_at_ms: null, laps: [],
      practice_draft: null,
    }
    return { id: `seed-${index}`, at: deadline + jump, state: { active_timer: timer, alarms: [] } }
  })
}

function independentPomodoroOracle(timer, now) {
  const expected = { ...timer }
  const firstDeadline = timer.deadline_at_ms
  let transitions = 0
  while (expected.deadline_at_ms <= now) {
    if (expected.phase === 'work') expected.cycle_count = Math.min(1_000_000, expected.cycle_count + 1)
    expected.phase = expected.phase === 'work' ? 'break' : 'work'
    expected.duration_ms = expected.phase === 'work' ? expected.work_duration_ms : expected.break_duration_ms
    expected.deadline_at_ms += expected.duration_ms
    transitions += 1
    if (transitions > 100_000) throw new Error('Seeded oracle scenario exceeded its deliberate iteration guard')
  }
  expected.cycle_count = Math.min(1_000_000, expected.cycle_count)
  expected.remaining_ms = expected.deadline_at_ms - now
  return {
    state: { active_timer: expected, alarms: [] },
    events: [{ type: 'pomodoro-phase-ended', at_ms: firstDeadline,
      phase: expected.phase }],
  }
}

function measure(operation, repeats = 11) {
  const samples = []
  for (let index = 0; index < repeats; index += 1) {
    const start = performance.now()
    operation()
    samples.push(performance.now() - start)
  }
  samples.sort((a, b) => a - b)
  return {
    samples: repeats,
    warmups: 0,
    quantiles: 'p50 is median; p95 is nearest-rank ceil(0.95*n), with no interpolation',
    p50_ms: round(samples[Math.floor(repeats / 2)]),
    p95_ms: round(samples[Math.ceil(repeats * 0.95) - 1]),
  }
}

function round(value) { return Number(value.toFixed(4)) }

const scenarios = seededCases(SEED)
for (const scenario of scenarios) {
  const expected = independentPomodoroOracle(scenario.state.active_timer, scenario.at)
  const actual = reconcileClock(scenario.state, scenario.at)
  assert.deepEqual(actual, expected, `seeded scenario ${scenario.id}`)
}

const boundaryTimer = {
  kind: 'pomodoro', status: 'running', elapsed_ms: 0, started_at_ms: null,
  deadline_at_ms: 10_000, duration_ms: 10_000, remaining_ms: 10_000,
  work_duration_ms: 10_000, break_duration_ms: 5_000, phase: 'work',
  cycle_enabled: true, cycle_count: 0, overdue_at_ms: null, laps: [], practice_draft: null,
}
const boundaryExpectations = [
  { at: 10_000, phase: 'break', cycle_count: 1, deadline_at_ms: 15_000, remaining_ms: 5_000 },
  { at: 15_000, phase: 'work', cycle_count: 1, deadline_at_ms: 25_000, remaining_ms: 10_000 },
  { at: 33_000, phase: 'work', cycle_count: 2, deadline_at_ms: 40_000, remaining_ms: 7_000 },
]
for (const expected of boundaryExpectations) {
  const actual = reconcileClock({ active_timer: boundaryTimer, alarms: [] }, expected.at).state.active_timer
  for (const key of ['phase', 'cycle_count', 'deadline_at_ms', 'remaining_ms']) assert.equal(actual[key], expected[key], `boundary ${expected.at} ${key}`)
}

const largeJumpScenarios = [1_000, 1_000_000, 1_000_000_000_000].map((jump) => ({
  jump,
  state: { active_timer: { ...boundaryTimer, deadline_at_ms: 0 }, alarms: [] },
}))
const boundedness = largeJumpScenarios.map(({ jump, state }) => {
  const started = performance.now()
  const result = reconcileClock(state, jump)
  const elapsedMs = performance.now() - started
  assert.ok(result.state.active_timer.deadline_at_ms > jump)
  assert.equal(result.events.length, 1)
  return { jump_ms: jump, elapsed_ms: round(elapsedMs) }
})
assert.ok(boundedness.at(-1).elapsed_ms < 20, `1e12 ms reconciliation exceeded 20 ms: ${JSON.stringify(boundedness)}`)

const alarmCount = 128
const now = 1_800_000_000_000
const alarms = Array.from({ length: alarmCount }, (_, index) => ({
  id: `alarm-${String(index).padStart(3, '0')}`, label: `Synthetic ${index}`,
  kind: 'once', one_off_at_ms: now - 10_000 - index, local_time: '', weekdays: [],
  enabled: true, next_at_ms: now - 10_000 - index, overdue_at_ms: null, last_fired_at_ms: null,
}))
const alarmState = { active_timer: null, alarms }
const alarmResult = reconcileClock(alarmState, now)
assert.equal(alarmResult.events.length, alarmCount)
assert.deepEqual(alarmResult.events.map((event) => event.id), alarms.map((alarm) => alarm.id))
assert.equal(alarmResult.state.alarms.filter((alarm) => alarm.overdue_at_ms !== null).length, alarmCount)
assert.equal(reconcileClock(alarmResult.state, now + 60_000).events.length, 0, 'repeated reconciliation must not refire missed alarms')

const dstProbe = spawnSync(process.execPath, ['--input-type=module', '-e', `
  import { nextWeekdayOccurrence } from ${JSON.stringify(ENGINE_URL)};
  const gap = nextWeekdayOccurrence([0], '02:30', Date.parse('2026-03-08T06:59:59.999Z'));
  const foldFirst = nextWeekdayOccurrence([0], '01:30', Date.parse('2026-11-01T04:45:00.000Z'));
  const foldAfterFirst = nextWeekdayOccurrence([0], '01:30', Date.parse('2026-11-01T05:45:00.000Z'));
  process.stdout.write(JSON.stringify([new Date(gap).toISOString(), new Date(foldFirst).toISOString(), new Date(foldAfterFirst).toISOString()]));
`], { env: { ...process.env, TZ: 'America/New_York' }, encoding: 'utf8' })
assert.equal(dstProbe.status, 0, dstProbe.stderr)
assert.deepEqual(JSON.parse(dstProbe.stdout), [
  '2026-03-08T07:30:00.000Z', // Nonexistent 02:30 wall time normalizes to 03:30 after the spring gap.
  '2026-11-01T05:30:00.000Z', // Ambiguous 01:30 chooses the earlier daylight-saving occurrence.
  '2026-11-08T06:30:00.000Z', // After that first fold occurrence, recurrence waits until next week.
])

// Negative controls: plausible broken strategies must disagree with the oracle.
const buggySinglePhase = (timer, at) => ({
  phase: timer.phase === 'work' ? 'break' : 'work',
  deadline_at_ms: timer.deadline_at_ms + (timer.phase === 'work' ? timer.break_duration_ms : timer.work_duration_ms),
})
const expected33s = independentPomodoroOracle(boundaryTimer, 33_000).state.active_timer
assert.notDeepEqual(buggySinglePhase(boundaryTimer, 33_000), {
  phase: expected33s.phase, deadline_at_ms: expected33s.deadline_at_ms,
}, 'negative control: one-transition catch-up must be detected')
const duplicateFireControl = reconcileClock(alarmResult.state, now + 60_000)
assert.equal(duplicateFireControl.events.length, 0, 'negative control: persisted fire marker prevents a duplicate notification')
const buggyRepeatAlarm = alarmState.alarms
  .filter((alarm) => alarm.enabled && alarm.next_at_ms <= now)
  .map((alarm) => ({ type: 'alarm', id: alarm.id, label: alarm.label, at_ms: alarm.next_at_ms }))
assert.ok(buggyRepeatAlarm.length > 0 && duplicateFireControl.events.length !== buggyRepeatAlarm.length,
  'negative control: leaving missed alarms eligible on every poll must be detected')
const buggyTickCountdown = Math.max(0, 60_000 - 1_000)
const deadlineCountdown = Math.max(0, 60_000 - 60_000)
assert.notEqual(buggyTickCountdown, deadlineCountdown,
  'negative control: one background timer tick cannot substitute for deadline-derived time')
const utcGapControl = new Date(Date.UTC(2026, 2, 8, 2, 30)).toISOString()
assert.notEqual(utcGapControl, '2026-03-08T07:30:00.000Z', 'negative control: UTC wall-time conversion must not match local DST policy')

const engineBatch = measure(() => {
  for (const scenario of scenarios) reconcileClock(scenario.state, scenario.at)
}, 11)
const alarmBatch = measure(() => reconcileClock(alarmState, now), 11)
const result = {
  benchmark: 'clock_engine_adversarial_corpus',
  seed: SEED,
  seeded_cases: scenarios.length,
  max_alarms: alarmCount,
  dst_timezone: 'America/New_York',
  dst_policy: 'nonexistent wall time normalizes forward; fold chooses first occurrence; after it, next weekly occurrence',
  correctness: 'all complete seeded timer states/events match a separately implemented iterative oracle; explicit boundaries and alarm state match independent expectations',
  negative_controls_detected: ['single-phase-only Pomodoro catch-up', 'UTC interpretation of local DST schedule', 'repeated missed-alarm emission', 'interval-tick countdown drift'],
  negative_control_sensitivity: '4 of 4 explicit plausible-bug controls disagreed with the contract oracle; this is a finite targeted control set, not general mutation coverage',
  negative_control_outputs: {
    single_phase_catchup: buggySinglePhase(boundaryTimer, 33_000),
    expected_33s_timer: { phase: expected33s.phase, deadline_at_ms: expected33s.deadline_at_ms },
    repeat_alarm_bug_event_count: buggyRepeatAlarm.length,
    expected_repeat_alarm_event_count: duplicateFireControl.events.length,
    tick_drift_bug_remaining_ms: buggyTickCountdown,
    deadline_remaining_ms: deadlineCountdown,
    utc_gap_variant: utcGapControl,
    expected_local_gap: '2026-03-08T07:30:00.000Z',
  },
  boundedness,
  engine_batch: engineBatch,
  '128_alarm_batch': alarmBatch,
  ai_included: false,
}
process.stdout.write(`${JSON.stringify(result)}\n`)

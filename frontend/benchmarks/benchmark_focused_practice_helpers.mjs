import assert from 'node:assert/strict'
import dns from 'node:dns'
import dgram from 'node:dgram'
import http from 'node:http'
import https from 'node:https'
import net from 'node:net'
import tls from 'node:tls'
import { performance } from 'node:perf_hooks'

const SEED = 20261119
const SCENARIOS = 256
const DURATION_CASES = 4096
const REPEATS = 9
const WARMUPS = 2

function installNetworkTripwires() {
  let attempts = 0
  const block = () => {
    attempts += 1
    throw new Error('Network access is forbidden in this frontend helper benchmark.')
  }
  const originals = []
  const replace = (object, key) => {
    const descriptor = Object.getOwnPropertyDescriptor(object, key)
    if (!descriptor || typeof descriptor.value !== 'function' || !descriptor.writable) return
    originals.push([object, key, descriptor])
    Object.defineProperty(object, key, { ...descriptor, value: block })
  }
  for (const [object, key] of [
    [net.Socket.prototype, 'connect'], [net, 'connect'], [tls, 'connect'],
    [dgram.Socket.prototype, 'send'], [dgram.Socket.prototype, 'connect'],
    [dns, 'lookup'], [dns, 'resolve'], [dns, 'resolve4'], [dns, 'resolve6'],
    [http, 'request'], [https, 'request'],
  ]) replace(object, key)
  const fetchDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'fetch')
  if (fetchDescriptor?.configurable) {
    Object.defineProperty(globalThis, 'fetch', { ...fetchDescriptor, value: block })
    originals.push([globalThis, 'fetch', fetchDescriptor])
  }
  return {
    count: () => attempts,
    restore: () => {
      for (const [object, key, descriptor] of originals.reverse()) Object.defineProperty(object, key, descriptor)
    },
  }
}

function seededRandom(seed) {
  let value = seed >>> 0
  return (limit) => {
    value = (Math.imul(value, 1664525) + 1013904223) >>> 0
    return value % limit
  }
}

function profile(index) {
  return {
    profile_id: `fixture-${index % 5}`,
    version: 1 + index % 3,
    display_name: `Synthetic profile ${index % 5}`,
    country_label: `Synthetic region ${index % 4}`,
    scoring_rule: {
      correct_points: 1 + index % 4,
      wrong_penalty: (index % 3) / 4,
      blank_points: 0,
    },
  }
}

function createResolverCases() {
  const random = seededRandom(SEED)
  const cases = []
  for (let index = 0; index < SCENARIOS; index += 1) {
    const kind = index % 16
    const completionId = `completion-${index}`
    const scoringProfile = profile(index)
    const draft = {
      completion_id: completionId,
      date: `2026-${String(1 + index % 12).padStart(2, '0')}-${String(1 + index % 27).padStart(2, '0')}`,
      subject: `Subject ${index % 9}`,
      topic: `Topic ${index % 17}`,
      correct: random(80), incorrect: random(40), blank: random(25),
      scoring_profile: scoringProfile,
    }
    const timer = { kind: 'practice', practice_draft: draft }
    const target = {
      id: `practice_focus_${completionId}`,
      date: draft.date, subject: draft.subject, topic: draft.topic,
      correct: draft.correct, incorrect: draft.incorrect, blank: draft.blank,
      scoring_profile: structuredClone(scoringProfile),
      fixture_index: index,
    }
    const sessions = Array.from({ length: 32 }, (_, rowIndex) => ({
      id: `unrelated-${index}-${rowIndex}`, date: '2026-01-01', subject: 'Other', topic: 'Other',
      correct: 0, incorrect: 0, blank: 0, scoring_profile: profile(rowIndex + index + 100),
    }))
    if (kind <= 13) sessions[random(sessions.length)] = target
    if (kind === 1) target.date = '2025-12-31'
    if (kind === 2) target.subject = 'Wrong subject'
    if (kind === 3) target.topic = 'Wrong topic'
    if (kind === 4) target.correct += 1
    if (kind === 5) target.incorrect += 1
    if (kind === 6) target.blank += 1
    if (kind === 7) target.scoring_profile.profile_id = 'wrong-profile-id'
    if (kind === 8) target.scoring_profile.version += 1
    if (kind === 9) target.scoring_profile.display_name = 'Wrong profile name'
    if (kind === 10) target.scoring_profile.country_label = 'Wrong country label'
    if (kind === 11) target.scoring_profile.scoring_rule.correct_points += 1
    if (kind === 12) target.scoring_profile.scoring_rule.wrong_penalty += 1
    if (kind === 13) target.scoring_profile.scoring_rule.blank_points += 1
    if (kind === 15) draft.completion_payload = { frozen: true }
    cases.push({ timer, sessions, kind, target })
  }
  return cases
}

function expectedLegacyResult({ kind, target }) {
  if (kind === 0) return { kind: 'match', row: target }
  if (kind >= 1 && kind <= 13) return { kind: 'mismatch' }
  if (kind === 14) return { kind: 'missing' }
  return { kind: 'not-legacy' }
}

function createDurationCases() {
  const boundaries = [0, 1, 999, 1000, 1001, 59_999, 60_000, 60_001, 60_999, 3_599_999,
    3_600_000, Number.MAX_SAFE_INTEGER]
  const random = seededRandom(SEED ^ 0x5f3759df)
  const values = [...boundaries]
  while (values.length < DURATION_CASES) values.push(random(Number.MAX_SAFE_INTEGER))
  return values
}

function expectedDuration(elapsedMs) {
  const totalSeconds = BigInt(elapsedMs) / 1000n
  return { duration_minutes: Number(totalSeconds / 60n), duration_seconds: Number(totalSeconds % 60n) }
}

function measure(operation) {
  for (let index = 0; index < WARMUPS; index += 1) operation()
  const samples = []
  for (let index = 0; index < REPEATS; index += 1) {
    const started = performance.now()
    operation()
    samples.push(performance.now() - started)
  }
  samples.sort((left, right) => left - right)
  return {
    samples: REPEATS,
    warmups: WARMUPS,
    p50_ms: round(samples[Math.floor(REPEATS / 2)]),
    p95_ms: round(samples[Math.ceil(REPEATS * 0.95) - 1]),
    minimum_ms: round(samples[0]),
    maximum_ms: round(samples.at(-1)),
  }
}

function round(value) { return Number(value.toFixed(4)) }

const network = installNetworkTripwires()
try {
  const [{ findLegacyFocusedCompletion }, { practiceDurationFromElapsedMilliseconds }] = await Promise.all([
    import('../src/clock/completePractice.js'),
    import('../src/clock/practiceDuration.js'),
  ])
  const resolverCases = createResolverCases()
  const resolverCounts = { match: 0, mismatch: 0, missing: 0, 'not-legacy': 0 }
  for (const scenario of resolverCases) {
    const expected = expectedLegacyResult(scenario)
    const actual = findLegacyFocusedCompletion(scenario.timer, scenario.sessions)
    assert.equal(actual.kind, expected.kind, `legacy completion scenario ${scenario.target.fixture_index ?? scenario.timer.practice_draft.completion_id}`)
    resolverCounts[actual.kind] += 1
    if (expected.kind === 'match') assert.equal(actual.row, expected.row, 'matched row must be returned unchanged')
  }
  assert.deepEqual(resolverCounts, { match: 16, mismatch: 208, missing: 16, 'not-legacy': 16 })
  const durationCases = createDurationCases()
  for (const elapsedMs of durationCases) {
    assert.deepEqual(practiceDurationFromElapsedMilliseconds(elapsedMs), expectedDuration(elapsedMs), `duration ${elapsedMs}ms`)
  }

  const resolverTiming = measure(() => {
    let matched = 0
    let checksum = 0
    for (const scenario of resolverCases) {
      const result = findLegacyFocusedCompletion(scenario.timer, scenario.sessions)
      if (result.kind === 'match') matched += 1
      checksum += result.kind.length
    }
    assert.equal(matched, 16)
    assert.ok(checksum > 0)
  })
  const durationTiming = measure(() => {
    let checksum = 0
    for (const elapsedMs of durationCases) {
      const result = practiceDurationFromElapsedMilliseconds(elapsedMs)
      checksum += result.duration_minutes + result.duration_seconds
    }
    assert.ok(checksum > 0)
  })
  assert.equal(network.count(), 0, 'no network calls are allowed')
  process.stdout.write(`${JSON.stringify({
    benchmark: 'focused_practice_helpers',
    seed: SEED,
    resolver_scenarios_per_repeat: resolverCases.length,
    resolver_oracle_counts: { match: 16, mismatch: 208, missing: 16, not_legacy: 16 },
    duration_cases_per_repeat: durationCases.length,
    repeats: REPEATS,
    warmups: WARMUPS,
    timings: { legacy_completion_resolver: resolverTiming, practice_duration_conversion: durationTiming },
    provider_execution: false,
    model_execution: false,
    browser_used: false,
    network_attempts: network.count(),
    timing_thresholds_used: false,
  }, null, 2)}\n`)
} finally {
  network.restore()
}

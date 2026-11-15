import test from 'node:test'
import assert from 'node:assert/strict'
import { practiceDurationFromElapsedMilliseconds } from './practiceDuration.js'

test('elapsed milliseconds convert to practice minutes and seconds at truncation and carry boundaries', () => {
  const cases = [
    [0, { duration_minutes: 0, duration_seconds: 0 }],
    [999, { duration_minutes: 0, duration_seconds: 0 }],
    [1000, { duration_minutes: 0, duration_seconds: 1 }],
    [59_999, { duration_minutes: 0, duration_seconds: 59 }],
    [60_000, { duration_minutes: 1, duration_seconds: 0 }],
    [60_999, { duration_minutes: 1, duration_seconds: 0 }],
  ]
  for (const [elapsedMs, expected] of cases) {
    assert.deepEqual(practiceDurationFromElapsedMilliseconds(elapsedMs), expected, `${elapsedMs}ms`)
  }
})

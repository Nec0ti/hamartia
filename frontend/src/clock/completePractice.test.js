import test from 'node:test'
import assert from 'node:assert/strict'
import { completeFocusedPractice } from './completePractice.js'

const profile = {
  profile_id: 'profile_fixture', version: 3, display_name: 'Fixture thirds', country_label: 'Fixture',
  scoring_rule: { correct_points: '1/3', wrong_penalty: '1/5', blank_points: '1/7' },
}
const legacyProfile = {
  profile_id: 'legacy-yks', version: 1, display_name: 'YKS (legacy)', country_label: 'Türkiye',
  scoring_rule: { correct_points: '1/1', wrong_penalty: '1/4', blank_points: '0/1' },
}

function legacyIdOnlyTimer(completionId = '1df6e22f-aace-4ba3-81cc-a05fce1f3d99') {
  return {
    kind: 'practice', status: 'running', elapsed_ms: 9000, started_at_ms: 10_000,
    practice_draft: {
      date: '2026-11-15', subject: 'Mathematics', topic: 'Functions',
      correct: 2, incorrect: 1, blank: 0, completion_id: completionId,
      scoring_profile: legacyProfile, completion_payload: null,
    },
  }
}

test('legacy ID-only draft clears from an exact deterministic persisted row without recomputing duration', async () => {
  const timer = legacyIdOnlyTimer()
  const row = {
    id: `practice_focus_${timer.practice_draft.completion_id}`,
    date: '2026-11-15', subject: 'Mathematics', topic: 'Functions',
    correct: 2, incorrect: 1, blank: 0, duration_minutes: 42, duration_seconds: 17,
    scoring_profile: legacyProfile,
  }
  let clearCount = 0
  let freezeCount = 0
  const result = await completeFocusedPractice({
    timer,
    listPractice: async () => [row],
    updateClock: async () => { freezeCount += 1; throw new Error('must not freeze a completed legacy draft') },
    reloadClock: async () => null,
    createPractice: async () => { throw new Error('must not re-POST a completed legacy draft') },
    clearClock: async () => { clearCount += 1 },
  })
  assert.equal(result, row)
  assert.equal(clearCount, 1)
  assert.equal(freezeCount, 0)
})

test('legacy ID-only draft with a mismatched row is surfaced without freezing, posting, or clearing', async () => {
  const timer = legacyIdOnlyTimer()
  const wrongRow = {
    id: `practice_focus_${timer.practice_draft.completion_id}`,
    date: '2026-11-15', subject: 'Mathematics', topic: 'Functions',
    correct: 99, incorrect: 1, blank: 0, duration_minutes: 42, duration_seconds: 17,
    scoring_profile: legacyProfile,
  }
  let mutations = 0
  await assert.rejects(completeFocusedPractice({
    timer,
    listPractice: async () => [wrongRow],
    updateClock: async () => { mutations += 1 },
    reloadClock: async () => null,
    createPractice: async () => { mutations += 1 },
    clearClock: async () => { mutations += 1 },
  }), /does not match its timer draft/)
  assert.equal(mutations, 0)
})

test('retries recover an ambiguous freeze write and replay one frozen request after time advances', async () => {
  let state = {
    active_timer: {
      kind: 'practice', status: 'running', elapsed_ms: 59_900, started_at_ms: 10_000,
      practice_draft: {
        date: '2026-11-15', subject: 'Mathematics', topic: 'Fractions',
        correct: 2, incorrect: 1, blank: 3, completion_id: null,
        scoring_profile: profile, completion_payload: null,
      },
    },
  }
  const writes = []
  const persistedByKey = new Map()
  const clearAttempts = []
  let successfulClears = 0
  let clearFails = true
  let freezeResponseLost = true
  let serverState = structuredClone(state)
  let reloadCount = 0
  const updateClock = async (update) => {
    const next = update(state)
    writes.push(structuredClone(next))
    serverState = structuredClone(next)
    if (freezeResponseLost && next.active_timer?.practice_draft?.completion_payload) {
      freezeResponseLost = false
      throw new Error('simulated committed clock write with lost response')
    }
    state = structuredClone(next)
    return state
  }
  const reloadClock = async () => {
    reloadCount += 1
    state = structuredClone(serverState)
    return state
  }
  const createPractice = async (payload, key) => {
    if (persistedByKey.has(key)) {
      assert.deepEqual(payload, persistedByKey.get(key).payload)
      return persistedByKey.get(key).row
    }
    const row = { id: 'persisted-once', ...payload, scoring_profile: profile }
    persistedByKey.set(key, { payload: structuredClone(payload), row })
    return row // The simulated server commits, but the first UI attempt loses the clear step.
  }
  const clearClock = async () => {
    clearAttempts.push(true)
    if (clearFails) {
      clearFails = false
      throw new Error('simulated clock clear response loss')
    }
    successfulClears += 1
    return updateClock((current) => ({ ...current, active_timer: null }))
  }

  await assert.rejects(completeFocusedPractice({
    timer: state.active_timer, now: 10_999, updateClock, reloadClock, createPractice, clearClock,
  }), /simulated clock clear response loss/)

  const frozen = state.active_timer
  assert.equal(frozen.status, 'paused')
  assert.equal(frozen.started_at_ms, null)
  assert.equal(frozen.elapsed_ms, 60_899)
  const frozenDraft = frozen.practice_draft
  assert.ok(frozenDraft.completion_id)
  assert.deepEqual(frozenDraft.completion_payload, {
    date: '2026-11-15', subject: 'Mathematics', topic: 'Fractions',
    correct: 2, incorrect: 1, blank: 3, duration_minutes: 1, duration_seconds: 0,
    scoring_profile_id: profile.profile_id, scoring_profile_version: profile.version,
    scoring_profile: profile,
  })
  const immutablePayload = structuredClone(frozenDraft.completion_payload)

  const row = await completeFocusedPractice({
    timer: state.active_timer, now: 999_999, updateClock, reloadClock, createPractice, clearClock,
  })
  assert.equal(row.id, 'persisted-once')
  assert.deepEqual(state.active_timer, null)
  assert.equal(writes.filter((write) => write.active_timer?.practice_draft?.completion_payload).length, 1,
    'retry should not rewrite or recompute the frozen payload')
  assert.equal(writes.at(-1).active_timer, null, 'successful retry clears the focused timer')
  assert.equal(persistedByKey.size, 1, 'same completion key must persist exactly one row')
  assert.equal(reloadCount, 1, 'ambiguous freeze response reloads the committed authoritative payload')
  assert.deepEqual(persistedByKey.values().next().value.payload, Object.fromEntries(
    Object.entries(immutablePayload).filter(([key]) => key !== 'scoring_profile'),
  ))
  assert.equal(clearAttempts.length, 2, 'clear is retried after the first clear failure')
  assert.equal(successfulClears, 1, 'the persisted timer is cleared exactly once')
})

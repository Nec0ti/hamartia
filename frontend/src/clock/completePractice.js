import { elapsedMilliseconds } from './engine.js'
import { practiceDurationFromElapsedMilliseconds } from './practiceDuration.js'

function sameProfile(left, right) {
  return Boolean(left && right
    && left.profile_id === right.profile_id
    && left.version === right.version
    && left.display_name === right.display_name
    && left.country_label === right.country_label
    && left.scoring_rule?.correct_points === right.scoring_rule?.correct_points
    && left.scoring_rule?.wrong_penalty === right.scoring_rule?.wrong_penalty
    && left.scoring_rule?.blank_points === right.scoring_rule?.blank_points)
}

/** Resolve PR31's ID-only timer against its deterministic, already-persisted row. */
export function findLegacyFocusedCompletion(timer, sessions) {
  const draft = timer?.practice_draft
  if (!draft?.completion_id || draft.completion_payload) return { kind: 'not-legacy' }
  const rowId = `practice_focus_${draft.completion_id}`
  const row = sessions.find((item) => item.id === rowId)
  if (!row) return { kind: 'missing' }
  const matches = row.date === draft.date
    && row.subject === draft.subject
    && row.topic === draft.topic
    && row.correct === draft.correct
    && row.incorrect === draft.incorrect
    && row.blank === draft.blank
    && sameProfile(row.scoring_profile, draft.scoring_profile)
  return matches ? { kind: 'match', row } : { kind: 'mismatch' }
}

/** Freeze the exact session request in clock.json before any practice POST. */
export async function completeFocusedPractice({ timer, now = Date.now(), updateClock, reloadClock, listPractice, createPractice, clearClock }) {
  if (timer?.kind !== 'practice' || !timer.practice_draft) throw new TypeError('A focused practice timer is required.')

  let completionId = timer.practice_draft.completion_id
  let completionPayload = timer.practice_draft.completion_payload
  if (completionId && !completionPayload) {
    const existing = findLegacyFocusedCompletion(timer, await listPractice())
    if (existing.kind === 'mismatch') {
      const error = new Error('The saved focused-practice row does not match its timer draft.')
      error.code = 'practice.legacyCompletionMismatch'
      throw error
    }
    if (existing.kind === 'match') {
      await clearClock()
      return existing.row
    }
  }
  if (!completionPayload) {
    completionId ||= crypto.randomUUID()
    const elapsedMs = elapsedMilliseconds(timer, now)
    const request = {
      date: timer.practice_draft.date,
      subject: timer.practice_draft.subject,
      topic: timer.practice_draft.topic,
      correct: timer.practice_draft.correct,
      incorrect: timer.practice_draft.incorrect,
      blank: timer.practice_draft.blank,
      ...practiceDurationFromElapsedMilliseconds(elapsedMs),
      scoring_profile_id: timer.practice_draft.scoring_profile.profile_id,
      scoring_profile_version: timer.practice_draft.scoring_profile.version,
    }
    completionPayload = { ...request, scoring_profile: timer.practice_draft.scoring_profile }
    const frozenTimer = {
      ...timer,
      status: 'paused',
      elapsed_ms: elapsedMs,
      started_at_ms: null,
      practice_draft: {
        ...timer.practice_draft,
        completion_id: completionId,
        completion_payload: completionPayload,
      },
    }
    try {
      const saved = await updateClock((current) => ({ ...current, active_timer: frozenTimer }))
      completionId = saved.active_timer.practice_draft.completion_id
      completionPayload = saved.active_timer.practice_draft.completion_payload
    } catch (freezeError) {
      // A timeout may hide a successful clock write. Reload before retrying so
      // we never replace an authoritative frozen request with a new duration.
      const recovered = await reloadClock()
      const recoveredDraft = recovered?.active_timer?.practice_draft
      if (!recoveredDraft || recoveredDraft.completion_id !== completionId || !recoveredDraft.completion_payload) {
        throw freezeError
      }
      completionId = recoveredDraft.completion_id
      completionPayload = recoveredDraft.completion_payload
    }
  }

  const { scoring_profile: _snapshot, ...request } = completionPayload
  const result = await createPractice(request, completionId)
  await clearClock()
  return result
}

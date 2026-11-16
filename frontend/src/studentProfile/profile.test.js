import assert from 'node:assert/strict'
import test from 'node:test'
import { firstRunStage, STUDENT_AVATARS, validateStudentProfile } from './profile.js'

test('first run starts with language, then honors tutorial skip/completion and survey completion', () => {
  assert.equal(firstRunStage(null), null)
  assert.equal(firstRunStage({}), 'language')
  assert.equal(firstRunStage({ tutorial_completed: true }), 'survey')
  assert.equal(firstRunStage({ tutorial_skipped: true }), 'survey')
  assert.equal(firstRunStage({ survey_completed: true }), null)
})

test('profile accepts only optional user-entered fields and age in whole years', () => {
  const profile = { nickname: 'Study name', age_years: 17, grade_year: '11', curriculum: 'Custom', study_preferences: 'Short sessions', study_goals: '', avatar_preset: 'moon' }
  assert.equal(validateStudentProfile(profile), profile)
  assert.equal(STUDENT_AVATARS.length, 8)
  for (const age of [4, 121, 17.5, '17']) assert.throws(() => validateStudentProfile({ ...profile, age_years: age }))
  assert.throws(() => validateStudentProfile({ ...profile, birth_date: '2009-01-02' }), /Unexpected/)
  assert.throws(() => validateStudentProfile({ ...profile, gender: 'unspecified' }), /Unexpected/)
  assert.throws(() => validateStudentProfile({ ...profile, avatar_preset: 'https://example.test/avatar.png' }), /built-in/)
  assert.throws(() => validateStudentProfile({ ...profile, nickname: 'x'.repeat(81) }), /nickname/)
})

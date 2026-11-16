import assert from 'node:assert/strict'
import test from 'node:test'
import { AVATAR_PRESETS, emptyProfileDraft, profileDraftFromServer, validateProfileDraft } from './profileDraft.js'

test('new social profile drafts contain only requested fields and default every visibility flag to private', () => {
  const draft = emptyProfileDraft()
  assert.deepEqual(draft, {
    nickname: '', nickname_public: false,
    age: null, age_public: false,
    school_grade: '', school_grade_public: false,
    school_class: '', school_class_public: false,
    curriculum: '', curriculum_public: false,
    study_preferences: '', study_preferences_public: false,
    study_goals: '', study_goals_public: false,
    avatar_preset: 'sunrise', avatar_preset_public: false,
  })
  assert.equal('gender' in draft, false)
  assert.equal('birth_date' in draft, false)
  assert.equal('email' in draft, false)
  assert.equal('uid' in draft, false)
  assert.equal(AVATAR_PRESETS.length, 8)
})

test('profile hydration preserves explicit per-field settings and fills absent values privately', () => {
  const draft = profileDraftFromServer({ nickname: 'Aylin', nickname_public: true, age: 17 })
  assert.equal(draft.nickname, 'Aylin')
  assert.equal(draft.nickname_public, true)
  assert.equal(draft.age, 17)
  assert.equal(draft.age_public, false)
  assert.equal(draft.study_goals, '')
  assert.equal(draft.study_goals_public, false)
})

test('profile submission emits only the API allowlist and rejects invalid age, avatar, or text lengths', () => {
  const patch = validateProfileDraft({ ...emptyProfileDraft(), nickname: 'Aylin', age: 17 })
  assert.equal(patch.nickname, 'Aylin')
  assert.equal(patch.age, 17)
  assert.equal('uid' in patch, false)
  assert.equal('email' in patch, false)
  assert.equal('gender' in patch, false)
  assert.throws(() => validateProfileDraft({ ...emptyProfileDraft(), age: 17.5 }), /whole number/)
  assert.throws(() => validateProfileDraft({ ...emptyProfileDraft(), age: 121 }), /whole number/)
  assert.throws(() => validateProfileDraft({ ...emptyProfileDraft(), avatar_preset: 'https://example.test/avatar.png' }), /built-in avatar/)
  assert.throws(() => validateProfileDraft({ ...emptyProfileDraft(), nickname: 'x'.repeat(81) }), /too long/)
})

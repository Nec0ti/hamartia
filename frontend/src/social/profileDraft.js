export const SOCIAL_PROFILE_FIELDS = Object.freeze([
  ['nickname', 'nickname_public', 80],
  ['age', 'age_public'],
  ['school_grade', 'school_grade_public', 80],
  ['school_class', 'school_class_public', 80],
  ['curriculum', 'curriculum_public', 120],
  ['study_preferences', 'study_preferences_public', 2000],
  ['study_goals', 'study_goals_public', 2000],
  ['avatar_preset', 'avatar_preset_public'],
])

export const AVATAR_PRESETS = Object.freeze(['sunrise', 'moon', 'leaf', 'star', 'book', 'mountain', 'wave', 'lantern'])

export function emptyProfileDraft() {
  return Object.fromEntries(SOCIAL_PROFILE_FIELDS.flatMap(([field, visibility]) => [
    [field, field === 'age' ? null : field === 'avatar_preset' ? 'sunrise' : ''],
    [visibility, false],
  ]))
}

export function profileDraftFromServer(profile = {}) {
  const draft = emptyProfileDraft()
  for (const [field, visibility] of SOCIAL_PROFILE_FIELDS) {
    if (Object.hasOwn(profile, field) && profile[field] !== null) draft[field] = profile[field]
    if (Object.hasOwn(profile, visibility)) draft[visibility] = profile[visibility] === true
  }
  return draft
}

export function validateProfileDraft(draft) {
  const patch = {}
  for (const [field, visibility, limit] of SOCIAL_PROFILE_FIELDS) {
    const value = draft[field]
    const visible = draft[visibility]
    if (typeof visible !== 'boolean') throw new Error('Invalid profile visibility setting.')
    patch[visibility] = visible
    if (field === 'age') {
      if (value !== null && (!Number.isInteger(value) || value < 5 || value > 120)) throw new Error('Age must be a whole number from 5 to 120.')
    } else if (field === 'avatar_preset') {
      if (!AVATAR_PRESETS.includes(value)) throw new Error('Choose a built-in avatar.')
    } else if (typeof value !== 'string' || value.length > limit) {
      throw new Error('One or more profile fields are too long.')
    }
    patch[field] = value
  }
  return patch
}
